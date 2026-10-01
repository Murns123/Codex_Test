"""Qantas SYD <-> JNB section.

Tracks three fare series on Qantas only, on the trip's dates:
  qf_rt    – best SYD-JNB-SYD return (21 Dec / 8 Jan)
  qf_out   – best one-way SYD -> JNB on 21 Dec
  qf_back  – best one-way JNB -> SYD on 8 Jan
plus, on the daily flex run, every date combination (return matrix and one-ways by date).

Each series gets the same statistics as the main tracker (baseline, daily closes, slope,
volatility, z-score, percentile, streaks) plus Qantas-specific ones: return vs two one-ways,
nonstop premium, fare step-jumps (a sign of a fare bucket closing), cheapest date
combination and the gap to the main MEL -> ELS best. Deterministic rules decide; JEV answers a
dedicated question set and may only upgrade HOLD -> BUY, as in the main tracker.
Fares come only from Ignav responses – nothing is estimated.
"""
from __future__ import annotations

import datetime as dt
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Any, Callable

from . import jev as jevmod
from .config import DecisionConfig, Settings
from .decision import Point, apply_jev, decide
from .http import HttpError
from .models import Itinerary, Leg, OneWay, search_link
from .providers.ignav import IgnavProvider, parse_oneway, parse_response
from .stats import _quantiles, _r, history_stats

log = logging.getLogger(__name__)

# fetch(kind, body) -> raw payload. kind is "rt" or "ow". Raises HttpError on failure.
Fetch = Callable[[str, dict[str, Any]], Any]
SERIES = ("qf_rt", "qf_out", "qf_back")
LABELS = {"qf_rt": "SYD ⇄ JNB return", "qf_out": "SYD → JNB one-way", "qf_back": "JNB → SYD one-way"}


# --- filtering ---------------------------------------------------------------------------
def _all_carrier(leg: Leg, carrier: str) -> bool:
    return bool(leg.segments) and all(
        carrier in {s.carrier, s.operating_carrier} for s in leg.segments)


def _flights(leg: Leg) -> str:
    return " / ".join(f"{s.carrier}{(s.flight_number or '').replace(s.carrier, '').strip()}" for s in leg.segments)


def _leg_summary(leg: Leg) -> dict[str, Any]:
    return {"route": "-".join(leg.airports), "flights": _flights(leg), "stops": leg.stops,
            "nonstop": leg.stops == 0, "hours": _r(leg.hours, 1),
            "departs": leg.segments[0].departure if leg.segments else None,
            "arrives": leg.segments[-1].arrival if leg.segments else None}


def rt_summary(it: Itinerary) -> dict[str, Any]:
    return {"dates": f"{it.outbound_date:%-d %b}–{it.return_date:%-d %b}",
            "out_date": str(it.outbound_date), "ret_date": str(it.return_date),
            "price_aud": it.price, "out": _leg_summary(it.outbound), "back": _leg_summary(it.inbound),
            "nonstop_both": it.outbound.stops == 0 and it.inbound.stops == 0,
            "price_note": next((n for n in it.notes if n.startswith("converted")), None),
            "booking_link": it.booking_link or search_link(it.outbound.airports[0], it.outbound.airports[-1],
                                                            it.outbound_date, it.return_date, "Qantas"),
            "link_kind": "book" if it.booking_link else "search"}


def ow_summary(o: OneWay) -> dict[str, Any]:
    return {"date": str(o.date), "price_aud": o.price, **_leg_summary(o.leg),
            "price_note": next((n for n in o.notes if n.startswith("converted")), None),
            "booking_link": o.booking_link or search_link(o.leg.airports[0], o.leg.airports[-1], o.date,
                                                          None, "Qantas"),
            "link_kind": "book" if o.booking_link else "search"}


# --- statistics ---------------------------------------------------------------------------
def daily_closes(rows: list[dict[str, Any]], series: str, today: dt.date) -> tuple[list[tuple[dt.date, float]], list[float]]:
    """(earlier daily closes, values from earlier runs today) for one series."""
    closes: dict[str, float] = {}
    today_vals: list[float] = []
    for r in rows:   # oldest first
        v = (r.get("series") or {}).get(series)
        if v is None:
            continue
        if r["run_date"] == today.isoformat():
            today_vals.append(v)
        else:
            closes[r["run_date"]] = v
    return [(dt.date.fromisoformat(d), v) for d, v in sorted(closes.items())], today_vals


def step_jumps(values: list[float], threshold_pct: float) -> dict[str, Any]:
    """Day-on-day moves larger than threshold – airline fares move in buckets, so a big
    single step up usually means a cheaper bucket sold out."""
    ups = downs = 0
    largest = 0.0
    for a, b in zip(values, values[1:]):
        if not a:
            continue
        ch = (b - a) / a * 100
        largest = max(largest, abs(ch))
        if ch >= threshold_pct:
            ups += 1
        elif ch <= -threshold_pct:
            downs += 1
    return {"threshold_pct": threshold_pct, "step_ups": ups, "step_downs": downs, "largest_step_pct": _r(largest)}


# --- the section -------------------------------------------------------------------------
def default_fetch(settings: Settings) -> Fetch:
    p = IgnavProvider(settings, lambda *_: "")
    endpoints = {"rt": settings.providers.get("ignav", {}).get("endpoint", "/fares/round-trip"),
                 "ow": settings.qantas.get("one_way_endpoint", "/fares/one-way")}

    def fetch(kind: str, body: dict[str, Any]) -> Any:
        return p.post(endpoints[kind], body)
    return fetch


def run_section(settings: Settings, *, now: dt.datetime, flex_this_run: bool, history_rows: list[dict[str, Any]],
                save_raw: Callable[[str, Any], str], fetch: Fetch | None = None,
                main_best: dict[str, Any] | None = None, fixture: bool = False) -> dict[str, Any]:
    q = settings.qantas
    out: dict[str, Any] = {"enabled": True, "status": "ok", "errors": [], "calls": 0,
                           "origin": q.get("origin", "SYD"), "destination": q.get("destination", "JNB"),
                           "carrier": q.get("carrier", "QF"), "flex_searched": flex_this_run,
                           "fixture_data": fixture}
    if not fixture and not settings.env.get("IGNAV_API_KEY"):
        return {**out, "status": "skipped", "errors": ["IGNAV_API_KEY is not set"]}
    fetch = fetch or default_fetch(settings)
    ignav = IgnavProvider(settings, save_raw)
    t = settings.trip
    org, dst, carrier = out["origin"], out["destination"], out["carrier"]
    airlines = [carrier] if q.get("airline_filter_in_request", True) else None

    pairs = t.date_pairs() if flex_this_run else t.date_pairs()[:1]
    out_dates = [t.outbound, *t.flex_outbound] if flex_this_run else [t.outbound]
    back_dates = [t.return_date, *t.flex_return] if flex_this_run else [t.return_date]
    jobs: list[tuple[str, str, dict[str, Any], Any]] = []   # (label, kind, body, date-key)
    for o, r in pairs:
        jobs.append((f"qf_rt_{o:%m%d}_{r:%m%d}", "rt", ignav.route_body(org, dst, o, r, airlines), (o, r)))
    if q.get("one_way", True):
        for d in out_dates:
            jobs.append((f"qf_ow_{org}{dst}_{d:%m%d}", "ow", ignav.route_body(org, dst, d, None, airlines), ("out", d)))
        for d in back_dates:
            jobs.append((f"qf_ow_{dst}{org}_{d:%m%d}", "ow", ignav.route_body(dst, org, d, None, airlines), ("back", d)))

    def call(job):
        label, kind, body, _ = job
        try:
            return body, fetch(kind, body), None
        except HttpError as exc:
            # if Ignav rejects the airline filter, retry once without it and filter locally
            if "airlines_include" in str(exc) and "airlines_include" in body:
                body = {k: v for k, v in body.items() if k != "airlines_include"}
                try:
                    return body, fetch(kind, body), "airline filter rejected by Ignav – filtered locally"
                except HttpError as exc2:
                    return body, None, str(exc2)
            return body, None, str(exc)

    with ThreadPoolExecutor(max_workers=int(q.get("concurrency", 4))) as pool:
        results = list(pool.map(call, jobs))

    from .models import ProviderResult
    fxres = ProviderResult(provider="ignav", ok=True)
    rts: list[Itinerary] = []
    ows: dict[str, list[OneWay]] = {"out": [], "back": []}
    dropped_other_carrier = 0
    for (label, kind, _, key), (body, payload, err) in zip(jobs, results):
        out["calls"] += 1
        if payload is None:
            out["errors"].append(f"{label}: {err}")
            save_raw(label + "_error", {"request": body, "error": err})
            continue
        if err:
            out["errors"].append(f"{label}: {err}")
        save_raw(label, {"request": body, "response": payload})
        fx = ignav._fx(payload, fxres)
        if kind == "rt":
            its, problems = parse_response(payload, key[0], key[1], t.currency, fx)
            keep = [i for i in its if _all_carrier(i.outbound, carrier) and _all_carrier(i.inbound, carrier)]
            dropped_other_carrier += len(its) - len(keep)
            rts += keep
        else:
            opts, problems = parse_oneway(payload, key[1], t.currency, fx)
            keep = [o for o in opts if _all_carrier(o.leg, carrier)]
            dropped_other_carrier += len(opts) - len(keep)
            ows[key[0]] += keep
        out["errors"] += [f"{label}: {p}" for p in problems]
    out["errors"] += fxres.errors
    if dropped_other_carrier:
        out["note"] = f"{dropped_other_carrier} non-{carrier} itineraries ignored"
    if fxres.extras.get("fx", {}).get("rates"):
        out["fx"] = fxres.extras["fx"]

    if not rts and not ows["out"] and not ows["back"]:
        out["status"] = "failed" if out["errors"] else "no_fares"

    # --- current values per series (primary dates) -------------------------------------
    prim_rt = [i for i in rts if (i.outbound_date, i.return_date) == (t.outbound, t.return_date)]
    prim_out = [o for o in ows["out"] if o.date == t.outbound]
    prim_back = [o for o in ows["back"] if o.date == t.return_date]
    best_rt = min(prim_rt, key=lambda i: i.price, default=None)
    best_out = min(prim_out, key=lambda o: o.price, default=None)
    best_back = min(prim_back, key=lambda o: o.price, default=None)
    current = {"qf_rt": best_rt.price if best_rt else None,
               "qf_out": best_out.price if best_out else None,
               "qf_back": best_back.price if best_back else None}
    out["series"] = current

    # --- options ---------------------------------------------------------------------------
    out["options"] = {
        "rt": [rt_summary(i) for i in sorted(prim_rt, key=lambda i: i.price)[:5]],
        "out": [ow_summary(o) for o in sorted(prim_out, key=lambda o: o.price)[:5]],
        "back": [ow_summary(o) for o in sorted(prim_back, key=lambda o: o.price)[:5]],
    }
    if flex_this_run:
        matrix: dict[str, float] = {}
        for i in rts:
            k = f"{i.outbound_date}_{i.return_date}"
            matrix[k] = min(matrix.get(k, i.price), i.price)
        out["rt_matrix"] = dict(sorted(matrix.items()))
        out["ow_by_date"] = {
            side: {str(d): min(o.price for o in ows[side] if o.date == d)
                   for d in sorted({o.date for o in ows[side]})} for side in ("out", "back")}
        if matrix:
            k, v = min(matrix.items(), key=lambda kv: kv[1])
            out["cheapest_combo"] = {"dates": k.replace("_", " → "), "price_aud": v,
                                     "saving_vs_primary": _r(current["qf_rt"] - v) if current["qf_rt"] else None}

    # --- statistics ---------------------------------------------------------------------------
    today = now.date()
    stats: dict[str, Any] = {}
    closes_by_series: dict[str, list[tuple[dt.date, float]]] = {}
    for sname in SERIES:
        closes, today_vals = daily_closes(history_rows, sname, today)
        closes_by_series[sname] = closes
        stats[sname] = history_stats([(d, v, v) for d, v in closes], current[sname], today_vals)
        vals = [v for _, v in closes] + ([current[sname]] if current[sname] is not None else [])
        stats[sname]["steps"] = step_jumps(vals, float(q.get("step_jump_pct", 8)))
    extra: dict[str, Any] = {}
    if best_out and best_back:
        two = best_out.price + best_back.price
        extra["two_one_ways_aud"] = _r(two)
        if best_rt:
            extra["return_vs_two_one_ways_aud"] = _r(two - best_rt.price)   # >0: return is cheaper
    if prim_rt:
        ns = [i.price for i in prim_rt if i.outbound.stops == 0 and i.inbound.stops == 0]
        conn = [i.price for i in prim_rt if not (i.outbound.stops == 0 and i.inbound.stops == 0)]
        extra["nonstop_options"] = len(ns)
        extra["connecting_options"] = len(conn)
        if ns and conn:
            extra["nonstop_premium_aud"] = _r(min(ns) - min(conn))
        extra["rt_price_distribution"] = _quantiles([i.price for i in prim_rt])
    if main_best and best_rt:
        extra["main_trip_best_aud"] = main_best.get("price_aud")
        extra["qf_rt_vs_main_best_aud"] = _r(best_rt.price - main_best["price_aud"])
    out["stats"] = {**stats, "extra": extra}

    # --- deterministic decision (on the return fare) --------------------------------------------
    dq = q.get("decision", {})
    base = settings.decision
    dcfg = replace(base,
                   buy_below_baseline_pct=float(dq.get("buy_below_baseline_pct", base.buy_below_baseline_pct)),
                   buy_under_price=float(dq.get("buy_under_price") or 0),   # 0 = rule off
                   rising_runs_for_buy=int(dq.get("rising_runs_for_buy", base.rising_runs_for_buy)),
                   hold_movement_pct=float(dq.get("hold_movement_pct", base.hold_movement_pct)))
    hist_pts = [Point(d, v, v) for d, v in closes_by_series["qf_rt"]]
    cur_pt = Point(today, best_rt.price, best_rt.price) if best_rt else None
    decision = decide(today, cur_pt, hist_pts, dcfg)

    # --- JEV ------------------------------------------------------------------------------------
    jev_res: dict[str, Any] = {"ok": False, "skipped": True, "answers": {}, "buy_probability": None, "error": None}
    jcfg = settings.jev
    if fixture:
        jev_res["error"] = "not called for fixture data"
    elif not jcfg.get("enabled", True) or not settings.env.get("JEV_API_KEY"):
        jev_res["error"] = "JEV not configured"
    elif not (best_rt or best_out or best_back):
        jev_res["error"] = "no Qantas fares to evaluate"
    else:
        state = {
            "task": f"Decide when to book Qantas {org}-{dst} for a trip (outbound {t.outbound}, return {t.return_date}), "
                    "1 adult economy, prices AUD. Compare booking the return vs two one-ways.",
            "current": current, "options": out["options"], "rt_matrix": out.get("rt_matrix"),
            "ow_by_date": out.get("ow_by_date"), "cheapest_combo": out.get("cheapest_combo"),
            "statistics": out["stats"], "rules_engine_decision": {k: decision.__dict__[k] for k in (
                "decision", "reason", "rule", "vs_baseline_pct", "vs_previous_pct", "rising_streak")},
            "calendar": {"today": str(today), "days_to_book_by": (base.book_by - today).days,
                         "days_to_departure": (t.outbound - today).days},
            "data_quality": {"errors": out["errors"][:10], "calls": out["calls"]},
            "note": "All prices are real Ignav quotes (USD converted at the ECB rate where noted).",
        }
        http_kwargs = {"retries": int(settings.http.get("retries", 3)),
                       "backoff_base_s": float(settings.http.get("backoff_base_s", 2)), "timeout_s": 90}
        model = settings.env.get("JEV_MODEL") or jcfg.get("model", "jev-latest")
        questions = qantas_questions([str(d) for d in sorted({*out_dates})], [str(d) for d in sorted({*back_dates})])
        jev_res = jevmod.evaluate(state, settings.env["JEV_API_KEY"], model, http_kwargs, questions,
                                  buy_choices=("book_return_now", "book_one_ways_now"))
        jev_res["skipped"] = False
        save_raw("qf_jev", {"request": {"model": model, "state": state}, "response": jev_res.pop("raw", None)})
        qj = q.get("jev", {})
        decision = apply_jev(decision, jev_res.get("buy_probability"),
                             qj.get("upgrade_hold_threshold", jcfg.get("upgrade_hold_threshold")),
                             int(qj.get("min_days_before_upgrade", jcfg.get("min_days_before_upgrade", 3))))
    out["decision"] = decision.__dict__
    out["jev"] = jev_res
    return out


def qantas_questions(out_dates: list[str], back_dates: list[str]) -> dict[str, dict[str, Any]]:
    n = jevmod._noul
    qs: dict[str, dict[str, Any]] = {
        "rt_rise_next_7d": n("Is the best Qantas SYD-JNB return fare likely to be higher in 7 days than today?"),
        "rt_drop_5pct_before_book_by": n("Is a drop of 5% or more in the best Qantas return fare likely before the "
                                         "book-by date?"),
        "rt_good_price": n("Relative to its own history, the date matrix and one-way prices, is today's best Qantas "
                           "return a good price for the Christmas peak?"),
        "trend_is_upward": n("Do the daily closes, slopes and streaks of the Qantas return fare show a genuine "
                             "upward trend rather than noise?"),
        "fare_bucket_closing": n("Do the step-jumps and recent moves suggest the cheaper Qantas fare buckets are "
                                 "selling out (prices stepping up and not coming back)?"),
        "volatility_high": n("Is day-to-day volatility on these Qantas fares high enough that waiting risks a "
                             "large jump?"),
        "one_ways_better_than_return": n("Is booking two one-ways better value than the return fare once price, "
                                         "flexibility and the date options are considered?"),
        "nonstop_worth_premium": n("Is the nonstop QF option worth its premium over connecting Qantas options?"),
        "outbound_scarcity_risk": n("Is there a meaningful risk that SYD->JNB around the outbound date sells out "
                                    "or jumps sharply (peak Christmas demand)?"),
        "return_scarcity_risk": n("Is there a meaningful risk that JNB->SYD around the return date sells out or "
                                  "jumps sharply (early-January peak)?"),
        "flex_dates_worth_it": n("Is the cheapest date combination saving large enough to justify moving dates?"),
        "qantas_beats_main_best": n("Compared with the best through-ticket MEL->ELS option, is building the trip "
                                    "around the Qantas SYD-JNB fare the better choice (price, time, reliability)?"),
        "data_quality_concern": n("Is there a data-quality concern (failed calls, few options, short history) that "
                                  "should make us cautious about today's Qantas reading?"),
        "action": {"type": "choice", "instructions": "Best action for the Qantas SYD-JNB booking today.",
                   "criteria": {"book_return_now": "Book the Qantas return today.",
                                "book_one_ways_now": "Book the two Qantas one-ways today.",
                                "hold": "Wait for the next check."}},
        "urgency": {"type": "score", "instructions": "How urgent is booking the Qantas fare? 1 = no rush, 5 = now.",
                    "criteria": ["1 – no rush", "2 – low: watch a few more days", "3 – moderate: this week",
                                 "4 – high: fares turning against us", "5 – book immediately"]},
        "value_rating": {"type": "score", "instructions": "Rate today's best Qantas return as value for money.",
                         "criteria": ["1 – poor", "2 – below average", "3 – fair", "4 – good", "5 – excellent"]},
    }
    if len(out_dates) > 1:
        qs["best_outbound_date"] = {"type": "choice", "instructions": "Which SYD->JNB date is the best choice?",
                                    "criteria": {d: f"Fly SYD->JNB on {d}" for d in out_dates}}
    if len(back_dates) > 1:
        qs["best_return_date"] = {"type": "choice", "instructions": "Which JNB->SYD date is the best choice?",
                                  "criteria": {d: f"Fly JNB->SYD on {d}" for d in back_dates}}
    return qs


def fixture_fetch(payload: dict[str, Any]) -> Fetch:
    """Offline fetch for --fixtures runs: keys 'qf_rt:<out>_<ret>' and 'qf_ow:<ORG><DST>_<date>'."""
    def fetch(kind: str, body: dict[str, Any]) -> Any:
        if kind == "rt":
            key = f"qf_rt:{body['departure_date']}_{body['return_date']}"
        else:
            key = f"qf_ow:{body['origin']}{body['destination']}_{body['departure_date']}"
        return payload.get(key, {"itineraries": []})
    return fetch


__all__ = ["run_section", "SERIES", "LABELS", "DecisionConfig"]
