"""One tracking run: search -> classify -> score -> decide -> (JEV) -> store -> report."""
from __future__ import annotations

import datetime as dt
import json
import time
import logging
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import jev as jevmod
from . import qantas
from .classify import classify
from .config import Settings
from .decision import Decision, Point, apply_jev, decide, pct_change
from .models import Itinerary, ProviderResult, search_link
from .providers import PROVIDERS
from .providers.fixture import FixtureProvider
from .scoring import best_single_ticket, score_all
from .stats import calendar_stats, history_stats, option_summary, today_stats
from .blobstore import VercelBlobStore
from .storage import DocStorage, SqliteStorage

Storage = SqliteStorage | DocStorage

log = logging.getLogger(__name__)


def open_storage(settings: Settings, dry_run: bool = False) -> Storage:
    token = settings.env.get("BLOB_READ_WRITE_TOKEN")
    store_id = ""
    if not token and settings.env.get("BLOB_STORE_ID") and settings.env.get("VERCEL_OIDC_TOKEN"):
        token, store_id = settings.env["VERCEL_OIDC_TOKEN"], settings.env["BLOB_STORE_ID"]
    if token:
        b = settings.storage.get("blob", {})
        store = VercelBlobStore(
            token, store_id=store_id, store_id_header=b.get("store_id_header", "x-vercel-blob-store-id"),
            base_url=b.get("base_url", "https://vercel.com/api/blob"),
            api_version=str(b.get("api_version", "11")), access=b.get("access", "private"),
            cache_max_age=int(b.get("cache_max_age", 60)),
            http_kwargs={"retries": int(settings.http.get("retries", 3)),
                         "backoff_base_s": float(settings.http.get("backoff_base_s", 2)), "timeout_s": 30})
        return DocStorage(store, dry_run=dry_run)
    if settings.env.get("VERCEL"):
        if settings.env.get("BLOB_STORE_ID"):
            raise RuntimeError("Blob store is connected (BLOB_STORE_ID) but this request carried no OIDC token – "
                               "enable OIDC in Project Settings -> Security, or add BLOB_READ_WRITE_TOKEN.")
        raise RuntimeError("No Blob store connected: in Vercel, Storage -> Create -> Blob (private), connect it "
                           "to this project, then redeploy.")
    return SqliteStorage(sqlite_path=settings.paths.get("db"), dry_run=dry_run)


def _dedupe(its: list[Itinerary]) -> list[Itinerary]:
    best: dict[str, Itinerary] = {}
    for it in its:
        k = it.key()
        if k not in best or it.price < best[k].price:
            best[k] = it
    return list(best.values())


def _history(storage: Storage, run_id: int, today: dt.date, basis: str) -> tuple[list[Point], list[float]]:
    rows = storage.scored_runs(exclude_run_id=run_id)
    runs_today = [r["best_value"] for r in rows if r["run_date"] == today.isoformat()]
    if basis == "run":
        return [Point(dt.date.fromisoformat(r["run_date"]), r["best_value"], r["best_price"]) for r in rows], runs_today
    closes: dict[str, dict[str, Any]] = {}
    for r in rows:                     # rows are oldest first, so the last one per date wins
        if r["run_date"] != today.isoformat():
            closes[r["run_date"]] = r
    pts = [Point(dt.date.fromisoformat(d), r["best_value"], r["best_price"]) for d, r in sorted(closes.items())]
    return pts, runs_today


def suggestions(best: Itinerary | None, its: list[Itinerary], tstats: dict[str, Any],
                cal: dict[str, Any], jev_answers: dict[str, Any],
                insights: dict[str, Any] | None = None) -> list[str]:
    out: list[str] = []
    if best is None:
        return ["No usable fares today – check Qantas, SAA and Emirates directly before relying on this tracker."]
    level = (insights or {}).get("price_level")
    rng = (insights or {}).get("typical_price_range") or []
    if level and len(rng) == 2:
        if level == "low":
            out.append(f"Google Flights rates today's prices as LOW for these dates (typical AUD {rng[0]:,.0f}–"
                       f"{rng[1]:,.0f}) – a good moment if the rules are close to a BUY.")
        elif level == "high":
            out.append(f"Google Flights rates today's prices as HIGH (typical AUD {rng[0]:,.0f}–{rng[1]:,.0f}) – "
                       "unless the book-by date forces it, waiting a few days is reasonable.")
    fs = tstats.get("flex_saving")
    if fs and fs["price_saving"] and fs["price_saving"] >= 100:
        out.append(f"Flying {fs['dates']} instead is AUD {fs['price_saving']:,.0f} cheaper – worth it if your leave can move.")
    st_cheapest = tstats.get("self_transfer_cheapest")
    if st_cheapest is not None and best.price - st_cheapest >= 300:
        out.append(f"A self-transfer combo is AUD {best.price - st_cheapest:,.0f} cheaper, but over Christmas a missed "
                   "connection on separate tickets is your problem, not the airline's – I'd stick with one ticket.")
    if best.longest_layover_min >= 8 * 60:
        out.append(f"The top pick has a {best.longest_layover_min / 60:.0f}h layover – check whether you'd need to "
                   "leave the airport or re-check bags, and whether a lounge day pass is worth it.")
    alt = [i for i in its if i.single_ticket and not i.too_long and i.route != best.route
           and i.price - best.price <= 150 and (i.outbound.hours + i.inbound.hours) <
           (best.outbound.hours + best.inbound.hours) - 3]
    if alt:
        a = min(alt, key=lambda i: i.price)
        diff = a.price - best.price
        cost = f"AUD {abs(diff):,.0f} cheaper" if diff < 0 else ("the same price" if diff == 0 else f"only AUD {diff:,.0f} more")
        out.append(f"Route {a.route} is {cost} and about "
                   f"{(best.outbound.hours + best.inbound.hours) - (a.outbound.hours + a.inbound.hours):.0f}h "
                   "quicker in total – worth a look.")
    risk = jev_answers.get("connection_risk_high")
    if isinstance(risk, (int, float)) and risk >= 0.6:
        out.append("JEV flags the top option's connections as risky – check minimum connection times, "
                   "especially the regional hop into East London.")
    if 0 <= cal["days_to_book_by"] <= 5:
        out.append(f"Book-by date is {cal['days_to_book_by']} day(s) away – have passport details ready.")
    out.append("When booking, make sure the East London leg is on the same booking reference, so a delay "
               "into Johannesburg is the airline's problem to fix.")
    return out[:3]


def _flex_saving(by_pair: dict[str, Any], settings: Settings) -> dict[str, Any] | None:
    """Best flex pair vs the primary pair, from a by_date_pair map (best_price/best_value)."""
    key = f"{settings.trip.outbound}_{settings.trip.return_date}"
    prim = by_pair.get(key)
    flex = [(k, v) for k, v in by_pair.items() if k != key and v.get("best_value") is not None]
    if not prim or not flex:
        return None
    k, v = min(flex, key=lambda kv: kv[1]["best_value"])
    if v["best_value"] >= prim["best_value"]:
        return None
    o, r = (dt.date.fromisoformat(x) for x in k.split("_"))
    return {"dates": f"{o:%-d %b}–{r:%-d %b}", "value_saving": round(prim["best_value"] - v["best_value"], 2),
            "price_saving": round(prim["best_price"] - v["best_price"], 2)}


FLEX_SLOTS = {"morning": (0, 10), "midday": (10, 15), "evening": (15, 24)}


def _flex_slot_now(now: dt.datetime, slot: str | None, default_from_hour: int) -> bool:
    """Is this run the one where a section searches its flex dates? slot = morning/midday/evening;
    unset = same rule as the main trip (hour >= flex_from_hour)."""
    if slot in FLEX_SLOTS:
        lo, hi = FLEX_SLOTS[slot]
        return lo <= now.hour < hi
    return now.hour >= default_from_hour


def run(settings: Settings, *, now: dt.datetime | None = None, dry_run: bool = False,
        fixtures: Path | None = None, storage: Storage | None = None) -> dict[str, Any]:
    tz = ZoneInfo(settings.timezone)
    now = (now or dt.datetime.now(tz)).astimezone(tz)
    today = now.date()
    own_storage = storage is None
    storage = storage or open_storage(settings, dry_run=dry_run)
    on_vercel = bool(settings.env.get("VERCEL"))
    try:
        return _run(settings, storage, now, today, dry_run, fixtures, on_vercel)
    finally:
        if own_storage:
            storage.close()


def _run(settings: Settings, storage: Storage, now: dt.datetime, today: dt.date, dry_run: bool,
         fixtures: Path | None, on_vercel: bool) -> dict[str, Any]:
    dcfg = settings.decision
    if today > dcfg.hard_stop:
        d = decide(today, None, [], dcfg)
        log.info("Past hard stop – no searches.")
        return {"run_at": now.isoformat(), "status": "stopped", "decision": d.__dict__, "day": None}

    t0 = time.monotonic()
    run_id = storage.start_run(now)
    raw_dir = settings.paths.get("raw_dir", Path("data/raw")) / today.isoformat()

    def save_raw(label: str, payload: Any) -> str:
        storage.save_raw(run_id, label, payload)
        if on_vercel or dry_run:
            return f"db:raw_responses/{run_id}/{label}"
        raw_dir.mkdir(parents=True, exist_ok=True)
        path = raw_dir / f"run{run_id}_{now:%H%M}_{label}.json"
        path.write_text(json.dumps(payload, indent=2, default=str))
        return str(path)

    # Flex dates once a day (first run at/after flex_from_hour); primary dates every run.
    flex_this_run = now.hour >= settings.trip.flex_from_hour
    all_pairs = settings.trip.date_pairs()
    pairs = all_pairs if flex_this_run else all_pairs[:1]
    results: list[ProviderResult] = []
    if fixtures:
        results.append(FixtureProvider(settings, save_raw, fixtures).search(pairs))
    else:
        for cls in PROVIDERS:
            p = cls(settings, save_raw)
            usable, why = p.is_configured()
            if not usable:
                log.info("%s skipped: %s", p.name, why)
                results.append(ProviderResult(provider=p.name, ok=False, skipped=True, errors=[why]))
                continue
            try:
                results.append(p.search(pairs))
            except Exception as exc:  # a provider bug must not kill the run
                log.exception("%s crashed", p.name)
                results.append(ProviderResult(provider=p.name, ok=False, errors=[f"crashed: {exc}"]))

    its = _dedupe([it for r in results for it in r.itineraries])
    primary = (settings.trip.outbound, settings.trip.return_date)
    for it in its:
        it.route = classify(it)
        if (it.outbound_date, it.return_date) == primary:
            it.notes.append("primary")
    its = score_all(its, settings.scoring)
    # The tracked "best option" is on the primary dates (21 Dec / 8 Jan) so that the trend is
    # comparable run to run; flex dates are reported separately as a possible saving.
    rank_key = lambda i: (not i.single_ticket, i.too_long, i.value_score, i.price)  # noqa: E731
    ranked = sorted(its, key=rank_key)
    ranked_primary = [i for i in ranked if "primary" in i.notes]
    best = best_single_ticket(ranked_primary)

    history, runs_today = _history(storage, run_id, today, dcfg.trend_basis)
    current = Point(today, best.value_score, best.price) if best else None
    decision: Decision = decide(today, current, history, dcfg)

    tstats = today_stats(its, settings)
    flex_checked_at = now.isoformat() if flex_this_run else None
    if not flex_this_run:
        # carry the last flex-date check forward so the dashboard always shows one
        prev = storage.latest_report()
        if prev and prev.get("flex_checked_at"):
            tstats["by_date_pair"] = {**prev.get("stats", {}).get("today", {}).get("by_date_pair", {}),
                                      **tstats["by_date_pair"]}
            # re-measure the saving against today's primary fare, not the one from the flex run
            tstats["flex_saving"] = _flex_saving(tstats["by_date_pair"], settings)
            flex_checked_at = prev["flex_checked_at"]
    extras: dict[str, Any] = {}
    for r in results:
        for k, v in r.extras.items():
            extras.setdefault(k, v)
    cal = calendar_stats(today, settings)
    hstats = history_stats([(p.date, p.value_score, p.price) for p in history],
                           best.value_score if best else None, runs_today)
    provider_status = [{"provider": r.provider, "ok": r.ok, "skipped": r.skipped, "calls": r.calls,
                        "itineraries": len(r.itineraries), "errors": r.errors[:10]} for r in results]

    # --- JEV second opinion -----------------------------------------------------------
    jcfg = settings.jev
    jev_result: dict[str, Any] = {"ok": False, "skipped": True, "answers": {}, "buy_probability": None,
                                  "error": None}
    if not jcfg.get("enabled", True):
        jev_result["error"] = "disabled in config.yaml"
    elif not settings.env.get("JEV_API_KEY"):
        jev_result["error"] = "JEV_API_KEY not set"
    elif best is None:
        jev_result["error"] = "no fares to evaluate"
    elif fixtures:
        jev_result["error"] = "not called for fixture data"
    else:
        state = jevmod.build_state(
            {"trip": {"origin": settings.trip.origin, "destination": settings.trip.destination,
                      "outbound": str(settings.trip.outbound), "return": str(settings.trip.return_date),
                      "adults": settings.trip.adults, "cabin": settings.trip.cabin,
                      "currency": settings.trip.currency},
             "calendar": cal, "today": tstats, "history": hstats,
             "google_price_insights": extras.get("price_insights")},
            {"decision": decision.decision, "reason": decision.reason, "rule": decision.rule,
             "vs_baseline_pct": decision.vs_baseline_pct, "vs_previous_pct": decision.vs_previous_pct,
             "rising_streak": decision.rising_streak},
            [option_summary(i) for i in ranked_primary[:10]],
            {k: str(v) for k, v in dcfg.__dict__.items()},
            provider_status,
        )
        http_kwargs = {"retries": int(settings.http.get("retries", 3)),
                       "backoff_base_s": float(settings.http.get("backoff_base_s", 2)),
                       "timeout_s": 90}
        model = settings.env.get("JEV_MODEL") or jcfg.get("model", "jev-latest")
        jev_result = jevmod.evaluate(state, settings.env["JEV_API_KEY"], model, http_kwargs)
        jev_result["skipped"] = False
        save_raw("jev", {"request": {"model": model, "state": state}, "response": jev_result.pop("raw", None)})
        decision = apply_jev(decision, jev_result.get("buy_probability"),
                             jcfg.get("upgrade_hold_threshold"), int(jcfg.get("min_days_before_upgrade", 3)))

    # --- report -------------------------------------------------------------------------
    configured = [r for r in results if not r.skipped]
    if not configured:
        status = "failed"
    elif all(r.ok and not r.errors for r in configured):
        status = "ok"
    elif any(r.ok for r in configured):
        status = "partial"
    else:
        status = "failed"
    if fixtures:
        status = "fixture"

    prev = history[-1] if history else None
    baseline = history[0] if history else current
    trend = {
        "previous": {"date": str(prev.date), "value_score": prev.value_score, "price": prev.price} if prev else None,
        "baseline": {"date": str(baseline.date), "value_score": baseline.value_score, "price": baseline.price}
        if baseline else None,
        "vs_previous_pct": decision.vs_previous_pct,
        "vs_previous_price": round(best.price - prev.price, 2) if best and prev else None,
        "vs_baseline_pct": pct_change(best.value_score, baseline.value_score) if best and baseline else None,
        "vs_baseline_price": round(best.price - baseline.price, 2) if best and baseline else None,
    }
    report: dict[str, Any] = {
        "run_id": run_id,
        "run_at": now.isoformat(),
        "status": status,
        "fixture_data": bool(fixtures),
        "dry_run": dry_run,
        "day": decision.day,
        "decision": {k: v for k, v in decision.__dict__.items()},
        "best": (_with_link(best, settings) if best else None),
        "top3": [_with_link(i, settings) for i in ranked_primary[:3]],
        "flex_searched": flex_this_run,
        "flex_checked_at": flex_checked_at,
        "google_insights": extras.get("price_insights"),
        "api_usage": extras.get("account"),
        "fx": extras.get("fx") if (extras.get("fx") or {}).get("rates") else None,
        "trend": trend,
        "flex_saving": tstats["flex_saving"],
        "suggestions": suggestions(best, its, tstats, cal, jev_result.get("answers", {}),
                                   extras.get("price_insights")),
        "providers": provider_status,
        "jev": jev_result,
        "stats": {"today": tstats, "history": hstats, "calendar": cal},
        "api_calls": {r.provider: r.calls for r in results},
    }

    # --- route sections: generic MEL <-> JNB first, then Qantas SYD <-> JNB ----------------
    # (isolated: a failure in one never breaks the main run or another section)
    sections: list[tuple[str, dict[str, Any], str]] = [
        (name, cfg, cfg.get("prefix", name[:2])) for name, cfg in settings.routes.items() if cfg.get("enabled")]
    if settings.qantas.get("enabled"):
        sections.append(("qantas", settings.qantas, "qf"))
    report["series"] = {}
    report["routes"] = {}
    history_rows = storage.series_rows(exclude_run_id=run_id) if sections else []
    payload = json.loads(fixtures.read_text()) if fixtures else None
    report["timings"] = {"main_s": round(time.monotonic() - t0, 1)}
    budget = float(settings.trip.flex_time_budget_s)
    prev_report = storage.latest_report() or {}
    for name, cfg, prefix in sections:
        prev_sec = prev_report.get("qantas") if name == "qantas" else (prev_report.get("routes") or {}).get(name)
        # each section searches its flex grid at its own run of the day (spreads the Ignav load)
        flex_this_run = _flex_slot_now(now, cfg.get("flex_run"), settings.trip.flex_from_hour)
        # Vercel stops a function at 300s: once past the budget, later sections check the
        # primary dates only rather than risk the whole run being killed.
        sec_flex = flex_this_run and (time.monotonic() - t0) < budget
        if flex_this_run and not sec_flex:
            log.warning("%s: past the %.0fs time budget – primary dates only this run", name, budget)
        ts = time.monotonic()
        try:
            section = qantas.run_section(
                settings, now=now, flex_this_run=sec_flex, history_rows=history_rows, save_raw=save_raw,
                fetch=qantas.fixture_fetch(payload, prefix) if payload is not None else None,
                main_best=report["best"], fixture=bool(fixtures),
                cfg=None if name == "qantas" else cfg, prefix=prefix, prev=prev_sec)
        except Exception as exc:
            log.exception("%s section failed", name)
            section = {"enabled": True, "status": "failed", "errors": [f"crashed: {exc}"], "calls": 0,
                       "title": cfg.get("title", name), "prefix": prefix}
        if name == "qantas":
            report["qantas"] = section
        else:
            report["routes"][name] = section
        if flex_this_run and not sec_flex:
            section.setdefault("errors", []).append("flex dates skipped this run (time budget)")
        report["timings"][f"{name}_s"] = round(time.monotonic() - ts, 1)
        report["series"].update(section.get("series") or {})
        report["api_calls"][f"ignav_{name}"] = section.get("calls", 0)
    report["timings"]["total_s"] = round(time.monotonic() - t0, 1)
    line = summary_line(report)
    report["summary_line"] = line
    storage.finish_run(run_id, status, report, ranked)
    storage.append_log(run_id, today, line)
    if not on_vercel and not dry_run:
        path = settings.paths.get("daily_log", Path("logs/daily_log.md"))
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists()
        with path.open("a") as fh:
            if new:
                fh.write("# MEL → ELS flight tracker – run log\n\n")
            fh.write(f"- {line}\n")
    log.info(line)
    return report


def _with_link(it: Itinerary, settings: Settings) -> dict[str, Any]:
    """Option summary plus a link: the provider's booking URL, else a labelled search link."""
    if it.booking_link:
        return {**option_summary(it), "booking_link": it.booking_link, "link_kind": "book"}
    return {**option_summary(it), "link_kind": "search",
            "booking_link": search_link(settings.trip.origin, settings.trip.destination,
                                        it.outbound_date, it.return_date)}


def summary_line(r: dict[str, Any]) -> str:
    d = r["decision"]
    b = r.get("best")
    parts = [dt.datetime.fromisoformat(r["run_at"]).strftime("%Y-%m-%d %H:%M"), f"Day {r['day']}", d["decision"]]
    if b:
        parts.append(f"best AUD {b['price_aud']:,.0f} (route {b['route']}, {'/'.join(b['carriers'])}, "
                     f"value {b['value_score']:,.0f})")
    else:
        parts.append("no usable fares")
    t = r["trend"]
    if t.get("vs_previous_pct") is not None:
        parts.append(f"vs prev {t['vs_previous_pct']:+.1f}%")
    if t.get("vs_baseline_pct") is not None:
        parts.append(f"vs base {t['vs_baseline_pct']:+.1f}%")
    parts.append("providers: " + ", ".join(
        f"{p['provider']} {'skipped' if p['skipped'] else ('ok' if p['ok'] else 'FAILED')}" for p in r["providers"]))
    bp = r["jev"].get("buy_probability")
    if bp is not None:
        parts.append(f"JEV p(book)={bp:.2f}")
    for sec in (r.get("routes") or {}).values():
        v = (sec.get("series") or {}).get(f"{sec.get('prefix')}_rt")
        if v is not None:
            parts.append(f"{sec.get('origin')}-{sec.get('destination')} return AUD {v:,.0f} "
                         f"({sec.get('decision', {}).get('decision')})")
    qs = r.get("qantas") or {}
    if qs.get("series", {}).get("qf_rt") is not None:
        parts.append(f"QF SYD-JNB return AUD {qs['series']['qf_rt']:,.0f} ({qs.get('decision', {}).get('decision')})")
    elif qs.get("enabled"):
        parts.append(f"QF SYD-JNB: {qs.get('status')}")
    if r.get("fixture_data"):
        parts.append("FIXTURE DATA")
    parts.append(d["reason"])
    return " | ".join(parts)
