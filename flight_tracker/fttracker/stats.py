"""Descriptive statistics over today's fares and the run history.

Used for the dashboard and as the `state` sent to JEV. Everything here is computed
from fares actually returned by providers – nothing is projected or filled in.
"""
from __future__ import annotations

import datetime as dt
import statistics as st
from collections import defaultdict
from typing import Any

from .classify import route_label
from .config import Settings
from .models import Itinerary


def _r(x: float | None, nd: int = 2) -> float | None:
    return None if x is None else round(x, nd)


def _quantiles(xs: list[float]) -> dict[str, float | None]:
    if not xs:
        return {"min": None, "p25": None, "median": None, "p75": None, "max": None}
    xs = sorted(xs)
    if len(xs) == 1:
        q = [xs[0]] * 3
    else:
        q = st.quantiles(xs, n=4, method="inclusive")
    return {"min": xs[0], "p25": _r(q[0]), "median": _r(q[1]), "p75": _r(q[2]), "max": xs[-1]}


def _slope(ys: list[float]) -> float | None:
    """Least-squares slope per step (AUD per day when ys are daily closes)."""
    n = len(ys)
    if n < 2:
        return None
    xbar, ybar = (n - 1) / 2, sum(ys) / n
    den = sum((i - xbar) ** 2 for i in range(n))
    return sum((i - xbar) * (y - ybar) for i, y in enumerate(ys)) / den


def option_summary(it: Itinerary) -> dict[str, Any]:
    return {
        "route": it.route,
        "route_label": route_label(it.route),
        "provider": it.provider,
        "dates": f"{it.outbound_date:%d %b}–{it.return_date:%d %b}",
        "price_aud": it.price,
        "value_score": it.value_score,
        "carriers": it.carriers,
        "stops_out": it.outbound.stops,
        "stops_back": it.inbound.stops,
        "hours_out": _r(it.outbound.hours, 1),
        "hours_back": _r(it.inbound.hours, 1),
        "longest_layover_h": _r(it.longest_layover_min / 60, 1),
        "via_out": it.outbound.airports[1:-1],
        "via_back": it.inbound.airports[1:-1],
        "single_ticket": it.single_ticket,
        "too_long": it.too_long,
        "price_note": next((n for n in it.notes if n.startswith("converted")), None),
    }


def today_stats(its: list[Itinerary], settings: Settings) -> dict[str, Any]:
    trip = settings.trip
    single = [i for i in its if i.single_ticket]
    ok = [i for i in single if not i.too_long] or single
    primary = (trip.outbound, trip.return_date)

    by_route: dict[str, list[Itinerary]] = defaultdict(list)
    for i in single:
        by_route[i.route].append(i)
    by_pair: dict[str, list[Itinerary]] = defaultdict(list)
    for i in ok:
        by_pair[f"{i.outbound_date}_{i.return_date}"].append(i)

    pair_best = {k: min(v, key=lambda i: i.value_score) for k, v in by_pair.items()}
    primary_key = f"{primary[0]}_{primary[1]}"
    primary_best = pair_best.get(primary_key)
    flex = [v for k, v in pair_best.items() if k != primary_key]
    best_flex = min(flex, key=lambda i: i.value_score, default=None)
    flex_saving = None
    if primary_best and best_flex and best_flex.value_score < primary_best.value_score:
        flex_saving = {
            "dates": f"{best_flex.outbound_date:%d %b}–{best_flex.return_date:%d %b}",
            "value_saving": _r(primary_best.value_score - best_flex.value_score),
            "price_saving": _r(primary_best.price - best_flex.price),
        }

    prices = [i.price for i in ok]
    return {
        "counts": {
            "itineraries": len(its),
            "single_ticket": len(single),
            "self_transfer": len(its) - len(single),
            "too_long": sum(i.too_long for i in single),
            "by_provider": {p: sum(i.provider == p for i in its) for p in sorted({i.provider for i in its})},
            "date_pairs_with_fares": len(by_pair),
        },
        "price_distribution": _quantiles(prices),
        "value_distribution": _quantiles([i.value_score for i in ok]),
        "price_spread_aud": _r(max(prices) - min(prices)) if prices else None,
        "by_route": {
            r: {
                "label": route_label(r),
                "options": len(v),
                "cheapest_price": min(i.price for i in v),
                "best_value": min(i.value_score for i in v),
                "fastest_hours_out": _r(min(i.outbound.hours for i in v), 1),
                "fastest_hours_back": _r(min(i.inbound.hours for i in v), 1),
            }
            for r, v in sorted(by_route.items())
        },
        "by_date_pair": {
            k: {"best_price": v.price, "best_value": v.value_score, "route": v.route}
            for k, v in sorted(pair_best.items())
        },
        "primary_dates_best": option_summary(primary_best) if primary_best else None,
        "flex_saving": flex_saving,
        "self_transfer_cheapest": min((i.price for i in its if not i.single_ticket), default=None),
    }


def history_stats(series: list[tuple[dt.date, float, float]], current_value: float | None,
                  runs_today: list[float]) -> dict[str, Any]:
    """series = earlier daily closes [(date, value_score, price)], oldest first, today excluded."""
    values = [v for _, v, _ in series]
    full = values + ([current_value] if current_value is not None else [])
    out: dict[str, Any] = {"days_observed": len(full)}
    if not full:
        return out
    changes = [(b - a) / a * 100 for a, b in zip(full, full[1:]) if a]
    mean = st.fmean(full)
    sd = st.pstdev(full) if len(full) > 1 else 0.0
    out.update({
        "baseline_value": full[0],
        "all_time_low_value": min(full),
        "all_time_high_value": max(full),
        "mean_value": _r(mean),
        "stdev_value": _r(sd),
        "current_zscore": _r((current_value - mean) / sd, 3) if sd and current_value is not None else None,
        "current_percentile": _r(sum(v <= current_value for v in full) / len(full) * 100, 1)
        if current_value is not None else None,
        "is_all_time_low": current_value is not None and current_value <= min(full),
        "days_since_low": (len(full) - 1 - max(i for i, v in enumerate(full) if v == min(full))),
        "slope_all_aud_per_day": _r(_slope(full)),
        "slope_7d_aud_per_day": _r(_slope(full[-7:])),
        "mean_7d_value": _r(st.fmean(full[-7:])),
        "vs_7d_mean_pct": _r((current_value - st.fmean(full[-7:])) / st.fmean(full[-7:]) * 100)
        if current_value is not None else None,
        "daily_change_pct": [_r(c) for c in changes[-14:]],
        "volatility_daily_pct": _r(st.pstdev(changes)) if len(changes) > 1 else None,
        "up_days": sum(c > 0 for c in changes),
        "down_days": sum(c < 0 for c in changes),
        "flat_days": sum(c == 0 for c in changes),
        "largest_daily_rise_pct": _r(max(changes)) if changes else None,
        "largest_daily_drop_pct": _r(min(changes)) if changes else None,
        "recent_closes": [{"date": d.isoformat(), "value": v, "price": p} for d, v, p in series[-14:]],
    })
    if runs_today:
        out["intraday"] = {"runs": len(runs_today), "min": min(runs_today), "max": max(runs_today),
                           "range_pct": _r((max(runs_today) - min(runs_today)) / min(runs_today) * 100)}
    return out


def calendar_stats(today: dt.date, settings: Settings) -> dict[str, Any]:
    t, d = settings.trip, settings.decision
    return {
        "today": today.isoformat(),
        "days_to_book_by": (d.book_by - today).days,
        "days_to_hard_stop": (d.hard_stop - today).days,
        "days_to_departure": (t.outbound - today).days,
        "weeks_to_departure": _r((t.outbound - today).days / 7, 1),
        "trip_length_days": (t.return_date - t.outbound).days,
        "travel_season": "Southern-hemisphere Christmas / New Year peak; Australian and South African "
                         "school holidays; heavy VFR demand to South Africa",
    }
