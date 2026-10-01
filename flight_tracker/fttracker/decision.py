"""Deterministic BUY/HOLD rules. JEV can only add a second opinion on top (see apply_jev)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from .config import DecisionConfig


@dataclass(frozen=True)
class Point:
    """One observation of the best single-ticket option."""
    date: dt.date
    value_score: float
    price: float


@dataclass
class Decision:
    decision: str                   # BUY | HOLD | STOP
    reason: str
    rule: str                       # machine-readable rule id
    day: int
    baseline: float | None = None
    vs_baseline_pct: float | None = None
    vs_previous_pct: float | None = None
    rising_streak: int = 0
    notes: list[str] = field(default_factory=list)


def pct_change(new: float, old: float) -> float:
    return (new - old) / old * 100 if old else 0.0


def rising_streak(series: list[float]) -> int:
    """How many consecutive increases end at the last element."""
    n = 0
    for i in range(len(series) - 1, 0, -1):
        if series[i] > series[i - 1]:
            n += 1
        else:
            break
    return n


def decide(today: dt.date, current: Point | None, history: list[Point], cfg: DecisionConfig) -> Decision:
    """`history` = earlier observations (oldest first, today excluded), one per day or per
    run depending on trend_basis. history[0] is the baseline. `current` = today's best
    single-ticket option, or None if nothing usable was retrieved."""
    day = len({p.date for p in history} | {today})
    baseline = history[0].value_score if history else (current.value_score if current else None)

    if today > cfg.hard_stop:
        return Decision("STOP", f"Tracking ended on {cfg.hard_stop:%-d %b %Y} (hard stop).", "hard_stop",
                        day, baseline)

    if current is None:
        if today >= cfg.book_by:
            reason = ("No single-ticket fares came back today and we're past the book-by date – "
                      "check the airline sites manually and book.")
        else:
            reason = "No usable single-ticket fares came back today, so there's nothing to judge – holding."
        return Decision("HOLD", reason, "no_data", day, baseline)

    prev = history[-1].value_score if history else None
    d = Decision("HOLD", "", "", day, baseline)
    d.vs_baseline_pct = pct_change(current.value_score, baseline) if baseline and history else 0.0
    d.vs_previous_pct = pct_change(current.value_score, prev) if prev else None
    d.rising_streak = rising_streak([p.value_score for p in history] + [current.value_score])

    if today >= cfg.book_by:
        final = " Today is the hard stop." if today == cfg.hard_stop else ""
        d.decision, d.rule = "BUY", "book_by"
        d.reason = f"It's {today:%-d %b} – past the {cfg.book_by:%-d %b} book-by date, so lock in the best single-ticket fare.{final}"
    elif current.price < cfg.buy_under_price:
        d.decision, d.rule = "BUY", "under_price"
        d.reason = f"Best single-ticket fare is AUD {current.price:,.0f}, under the AUD {cfg.buy_under_price:,.0f} buy line."
    elif history and d.vs_baseline_pct <= -cfg.buy_below_baseline_pct:
        d.decision, d.rule = "BUY", "below_baseline"
        d.reason = (f"Best option is {abs(d.vs_baseline_pct):.1f}% below the day-1 baseline "
                    f"(threshold {cfg.buy_below_baseline_pct:g}%).")
    elif d.rising_streak >= cfg.rising_runs_for_buy:
        d.decision, d.rule = "BUY", "rising"
        d.reason = (f"Best option has gone up {d.rising_streak} times in a row – "
                    "prices are climbing, better to book before they go higher.")
    elif not history:
        d.rule = "baseline"
        d.reason = f"Day 1 – baseline set at value score {current.value_score:,.0f} (AUD {current.price:,.0f})."
    elif d.vs_previous_pct is not None and abs(d.vs_previous_pct) < cfg.hold_movement_pct:
        d.rule = "small_move"
        d.reason = f"Moved {d.vs_previous_pct:+.1f}% since last check – within normal noise, holding."
    else:
        d.rule = "no_trigger"
        mv = f"{d.vs_previous_pct:+.1f}%" if d.vs_previous_pct is not None else "n/a"
        d.reason = f"Moved {mv} since last check but no buy trigger hit – holding."
    return d


def apply_jev(d: Decision, jev_buy_probability: float | None, threshold: float | None,
              min_day: int = 3) -> Decision:
    """JEV may upgrade HOLD -> BUY when confident enough. It never downgrades a BUY and
    never acts without data or before `min_day` days of history."""
    if (threshold is None or jev_buy_probability is None or d.decision != "HOLD"
            or d.rule in ("no_data", "baseline") or d.day < min_day):
        return d
    if jev_buy_probability >= threshold:
        d.notes.append(f"Rules said HOLD ({d.reason})")
        d.decision, d.rule = "BUY", "jev_upgrade"
        d.reason = (f"JEV puts a {jev_buy_probability:.0%} probability on 'book now' "
                    f"(threshold {threshold:.0%}) – upgrading HOLD to BUY.")
    return d
