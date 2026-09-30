"""Renders a stored run report as a plain-text summary (CLI) or an HTML dashboard (Vercel)."""
from __future__ import annotations

import datetime as dt
import html
from typing import Any

from .jev import QUESTIONS

SUBJECT = "Flight analysis – MEL to ELS | Day {day} – {decision}"


def _money(x: float | None) -> str:
    return "–" if x is None else f"AUD {x:,.0f}"


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x:+.1f}%"


def flex_text(fs: dict[str, Any] | None) -> str:
    if not fs:
        return "none – the primary dates (21 Dec / 8 Jan) are the best value today"
    p = fs["price_saving"]
    price = f"AUD {p:,.0f} cheaper" if p > 0 else ("same price" if p == 0 else f"AUD {-p:,.0f} dearer but quicker")
    return f"{fs['dates']} – {fs['value_saving']:,.0f} better on value score ({price})"


def insights_text(gi: dict[str, Any] | None) -> str | None:
    if not gi:
        return None
    rng = gi.get("typical_price_range") or []
    level = (gi.get("price_level") or "").upper() or "n/a"
    typ = f", typical AUD {rng[0]:,.0f}–{rng[1]:,.0f}" if len(rng) == 2 else ""
    low = f", lowest now AUD {gi['lowest_price']:,.0f}" if gi.get("lowest_price") is not None else ""
    return f"{level}{typ}{low}"


def usage_text(u: dict[str, Any] | None) -> str | None:
    if not u:
        return None
    left = u.get("total_searches_left", u.get("plan_searches_left"))
    return (f"SerpApi: {u.get('this_month_usage', '?')} searches used this month, {left} left"
            + (f" ({u['plan_name']})" if u.get("plan_name") else ""))


def headline(r: dict[str, Any]) -> str:
    return SUBJECT.format(day=r.get("day") or "–", decision=r["decision"]["decision"])


def provider_problems(r: dict[str, Any]) -> list[str]:
    out = []
    for p in r.get("providers", []):
        if p["skipped"]:
            continue
        if not p["ok"]:
            out.append(f"{p['provider']} failed – no fares from it this run. " + "; ".join(p["errors"][:3]))
        elif p["errors"]:
            out.append(f"{p['provider']} worked, with issues: " + "; ".join(p["errors"][:3]))
    j = r.get("jev", {})
    if not j.get("skipped") and not j.get("ok"):
        out.append(f"JEV failed ({j.get('error')}) – decision is from the rules only.")
    return out


def to_text(r: dict[str, Any]) -> str:
    d, t = r["decision"], r["trend"]
    lines = [headline(r), "=" * len(headline(r)), ""]
    if r.get("fixture_data"):
        lines += ["*** FIXTURE DATA – these are test fares, not real prices ***", ""]
    lines += [f"{d['decision']}: {d['reason']}", ""]
    for p in provider_problems(r):
        lines.append(f"! {p}")
    lines.append("")
    lines.append("Top options:")
    if not r["top3"]:
        lines.append("  (none – no fares were retrieved, so nothing is shown rather than guessing)")
    for i, o in enumerate(r["top3"], 1):
        lines.append(f"  {i}. {_money(o['price_aud'])}  route {o['route']} ({o['route_label']})  "
                     f"{'/'.join(o['carriers'])}  {o['dates']}  "
                     f"{o['hours_out']}h out ({o['stops_out']} stops) / {o['hours_back']}h back ({o['stops_back']} stops)  "
                     f"longest layover {o['longest_layover_h']}h  value {o['value_score']:,.0f}"
                     f"{'  TOO LONG' if o['too_long'] else ''}{'' if o['single_ticket'] else '  SELF-TRANSFER'}")
        if o.get("price_note"):
            lines.append(f"     ({o['price_note']})")
        if o.get("booking_link"):
            lines.append(f"     {o['booking_link']}")
    lines.append("")
    prev = t.get("previous")
    lines.append(f"Trend vs yesterday: {_pct(t.get('vs_previous_pct'))}"
                 + (f" ({_money(t.get('vs_previous_price'))} on price)" if prev else " (no earlier day yet)"))
    lines.append(f"Trend vs baseline:  {_pct(t.get('vs_baseline_pct'))}")
    fs = r.get("flex_saving")
    lines.append(f"Best flex-date saving: {flex_text(fs)}")
    if insights_text(r.get("google_insights")):
        lines.append(f"Google price level: {insights_text(r['google_insights'])}")
    if r.get("flex_checked_at") and not r.get("flex_searched"):
        lines.append(f"(flex dates last checked {r['flex_checked_at'][:16].replace('T', ' ')})")
    j = r.get("jev", {})
    if j.get("ok"):
        lines.append(f"JEV: P(book today) = {j['buy_probability']:.0%}" if j.get("buy_probability") is not None
                     else "JEV: answered, no action probability")
    lines += ["", "Suggestions:"] + [f"  - {s}" for s in r.get("suggestions", [])]
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------
CSS = """
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1f;--muted:#6b6b70;--line:#e3e3e0;--buy:#0a7d3b;--hold:#8a5a00;
--stop:#555;--warn-bg:#fff4e5;--warn:#8a4b00;--bar:#3867d6;--fix-bg:#ffe8e8;--fix:#a30000}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--card:#1e1e21;--ink:#ececef;--muted:#9a9aa2;
--line:#303035;--buy:#3ccf7a;--hold:#f0b44c;--stop:#aaa;--warn-bg:#3a2a12;--warn:#f5c27a;--bar:#6c8ff0;
--fix-bg:#4a1717;--fix:#ff9c9c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1000px;margin:0 auto;padding:20px 16px 60px;overflow-wrap:anywhere}
h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 8px}
.muted{color:var(--muted)}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
.banner{display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.pill{font-weight:700;font-size:22px;padding:6px 16px;border-radius:8px;color:#fff}
.BUY{background:var(--buy)}.HOLD{background:var(--hold)}.STOP{background:var(--stop)}
.warn{background:var(--warn-bg);color:var(--warn);border-radius:8px;padding:10px 12px;margin:10px 0}
.fixture{background:var(--fix-bg);color:var(--fix);font-weight:700;border-radius:8px;padding:10px 12px;margin:10px 0}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top;white-space:nowrap}
th{color:var(--muted);font-weight:600}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(160px,100%),1fr));gap:12px}
.kpi .s{color:var(--muted);font-size:12px;margin-top:2px}
.kpi .v{font-size:20px;font-weight:700;font-variant-numeric:tabular-nums}.kpi .l{color:var(--muted);font-size:13px}
.bar{height:8px;background:var(--line);border-radius:4px;overflow:hidden;min-width:80px}
.bar>span{display:block;height:100%;background:var(--bar)}
a{color:var(--bar)}ul{margin:6px 0;padding-left:20px}code{font-size:13px}
svg{max-width:100%;height:auto}
"""


def _e(x: Any) -> str:
    return html.escape("" if x is None else str(x))


def _options_table(opts: list[dict[str, Any]]) -> str:
    if not opts:
        return "<p class='muted'>No fares were retrieved this run, so none are shown.</p>"
    rows = []
    for i, o in enumerate(opts, 1):
        link = f"<a href='{_e(o['booking_link'])}' target='_blank' rel='noopener'>book</a>" if o.get("booking_link") else "–"
        flags = []
        if o["too_long"]:
            flags.append("too long")
        if not o["single_ticket"]:
            flags.append("self-transfer")
        rows.append(
            f"<tr><td>{i}</td><td class='num'>{_money(o['price_aud'])}"
            + (f"<div class='muted' style='font-size:11px'>{_e(o['price_note'])}</div>" if o.get("price_note") else "")
            + f"</td><td>{_e(o['route'])} · {_e(o['route_label'])}</td>"
            f"<td>{_e('/'.join(o['carriers']))}</td><td>{_e(o['dates'])}</td>"
            f"<td class='num'>{o['hours_out']}h · {o['stops_out']} stop(s)</td>"
            f"<td class='num'>{o['hours_back']}h · {o['stops_back']} stop(s)</td>"
            f"<td class='num'>{o['longest_layover_h']}h</td><td>{'yes' if o['single_ticket'] else 'no'}</td>"
            f"<td class='num'>{o['value_score']:,.0f}</td><td>{_e(', '.join(flags)) or '–'}</td><td>{link}</td></tr>")
    return ("<div class='scroll'><table><thead><tr><th>#</th><th class='num'>Price</th><th>Route</th><th>Carriers</th>"
            "<th>Dates</th><th class='num'>Out</th><th class='num'>Back</th><th class='num'>Longest layover</th>"
            "<th>Single ticket</th><th class='num'>Value score</th><th>Flags</th><th>Link</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table></div>")


def _sparkline(points: list[tuple[str, float]], w: int = 640, h: int = 140) -> str:
    if len(points) < 2:
        return "<p class='muted'>The chart appears once there are two days of data.</p>"
    vals = [v for _, v in points]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    pad = 24
    xs = [pad + i * (w - 2 * pad) / (len(vals) - 1) for i in range(len(vals))]
    ys = [h - pad - (v - lo) / span * (h - 2 * pad) for v in vals]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(zip(xs, ys)))
    dots = "".join(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='3' fill='var(--bar)'><title>{_e(d)}: {v:,.0f}</title></circle>"
                   for (d, v), x, y in zip(points, xs, ys))
    return (f"<svg viewBox='0 0 {w} {h}' role='img' aria-label='Best value score by day'>"
            f"<path d='{path}' fill='none' stroke='var(--bar)' stroke-width='2'/>{dots}"
            f"<text x='{pad}' y='14' fill='var(--muted)' font-size='11'>{hi:,.0f}</text>"
            f"<text x='{pad}' y='{h - 6}' fill='var(--muted)' font-size='11'>{lo:,.0f}</text></svg>")


def _jev_panel(j: dict[str, Any]) -> str:
    if j.get("skipped"):
        return f"<p class='muted'>JEV not used this run ({_e(j.get('error'))}).</p>"
    if not j.get("ok"):
        return f"<div class='warn'>JEV failed: {_e(j.get('error'))}. The decision above is from the rules only.</div>"
    a = j.get("answers", {})
    rows = []
    for key, q in QUESTIONS.items():
        v = a.get(key)
        if v is None:
            continue
        if q["type"] == "noul" and isinstance(v, (int, float)):
            rows.append(f"<tr><td>{_e(key.replace('_', ' '))}</td><td class='num'>{v:.0%}</td>"
                        f"<td><div class='bar'><span style='width:{v * 100:.0f}%'></span></div></td></tr>")
        elif q["type"] == "choice" and isinstance(v, dict):
            probs = ", ".join(f"{k} {p:.0%}" for k, p in sorted((v.get("probabilities") or {}).items(),
                                                              key=lambda kv: -kv[1]))
            rows.append(f"<tr><td>{_e(key.replace('_', ' '))}</td><td class='num'><b>{_e(v.get('choice'))}</b></td>"
                        f"<td>{_e(probs)}</td></tr>")
        elif q["type"] == "score" and isinstance(v, dict):
            rows.append(f"<tr><td>{_e(key)}</td><td class='num'><b>{_e(v.get('score'))}</b> / 5</td>"
                        f"<td>confidence {v.get('confidence') or 0:.0%}</td></tr>")
    bp = j.get("buy_probability")
    head = f"<p><b>P(book today) = {bp:.0%}</b> <span class='muted'>(model {_e(j.get('model'))})</span></p>" \
        if bp is not None else ""
    return head + "<div class='scroll'><table><tbody>" + "".join(rows) + "</tbody></table></div>"


def to_html(r: dict[str, Any] | None, recent_runs: list[dict[str, Any]] | None = None,
            log_lines: list[str] | None = None) -> str:
    if r is None:
        body = ("<h1>MEL → ELS flight tracker</h1><p class='muted'>No runs yet. The first scheduled run will "
                "set the baseline.</p>")
        return _page(body)
    d, t, s = r["decision"], r["trend"], r.get("stats", {})
    run_at = dt.datetime.fromisoformat(r["run_at"])
    parts = [f"<h1>{_e(headline(r))}</h1>",
             f"<p class='muted'>Last run {run_at:%a %d %b %Y, %H:%M} Melbourne time · status {_e(r['status'])}</p>"]
    if r.get("fixture_data"):
        parts.append("<div class='fixture'>FIXTURE DATA – these are test fares, not real prices.</div>")
    parts.append(f"<div class='card banner'><span class='pill {_e(d['decision'])}'>{_e(d['decision'])}</span>"
                 f"<div>{_e(d['reason'])}" + "".join(f"<div class='muted'>{_e(n)}</div>" for n in d.get("notes", []))
                 + "</div></div>")
    for p in provider_problems(r):
        parts.append(f"<div class='warn'>{_e(p)}</div>")

    b = r.get("best")
    fs = r.get("flex_saving")
    cal = s.get("calendar", {})
    flex_sub = flex_text(fs).split(" – ", 1)[-1] if fs else "primary dates are best"
    parts.append("<h2>At a glance</h2><div class='grid'>" + "".join(
        f"<div class='card kpi'><div class='l'>{_e(label)}</div><div class='v'>{_e(val)}</div>"
        f"<div class='s'>{_e(sub)}</div></div>" for label, val, sub in [
            ("Best single-ticket fare", _money(b["price_aud"]) if b else "–",
             f"route {b['route']} · {'/'.join(b['carriers'])}" if b else "no fares retrieved"),
            ("vs yesterday", _pct(t.get("vs_previous_pct")), "value score"),
            ("vs baseline (day 1)", _pct(t.get("vs_baseline_pct")), "value score"),
            ("Best flex dates", fs["dates"] if fs else "none",
             flex_sub + (f" · checked {r['flex_checked_at'][11:16]} {r['flex_checked_at'][8:10]}/{r['flex_checked_at'][5:7]}"
                         if r.get("flex_checked_at") and not r.get("flex_searched") else "")),
            ("Google price level", ((r.get("google_insights") or {}).get("price_level") or "–").upper(),
             (insights_text(r.get("google_insights")) or "no insight returned").split(", ", 1)[-1]),
            ("Days to book-by", cal.get("days_to_book_by", "–"), "14 Oct 2026"),
            ("Days to departure", cal.get("days_to_departure", "–"), "21 Dec 2026"),
        ]) + "</div>")

    parts.append("<h2>Top 3 options – 21 Dec / 8 Jan</h2>" + _options_table(r.get("top3", [])))
    parts.append("<h2>Suggestions</h2><ul>" + "".join(f"<li>{_e(x)}</li>" for x in r.get("suggestions", [])) + "</ul>")

    hist = s.get("history", {})
    closes = [(c["date"], c["value"]) for c in hist.get("recent_closes", [])]
    if b:
        closes.append((run_at.date().isoformat(), b["value_score"]))
    parts.append("<h2>Best value score by day</h2><div class='card'>" + _sparkline(closes) + "</div>")

    gh = (r.get("google_insights") or {}).get("price_history") or []
    if len(gh) >= 2:
        pts = [(dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat(), float(p)) for t, p in gh
               if isinstance(t, (int, float)) and isinstance(p, (int, float))]
        parts.append("<h2>Google's price history for the primary dates</h2><div class='card'>"
                     + _sparkline(pts) + "</div>")

    stat_rows = [(k.replace("_", " "), v) for k, v in hist.items()
                 if k not in ("recent_closes", "daily_change_pct", "intraday") and not isinstance(v, (list, dict))]
    tdist = s.get("today", {}).get("price_distribution", {})
    stat_rows += [(f"today price {k}", _money(v)) for k, v in tdist.items()]
    parts.append("<h2>Statistics</h2><div class='scroll'><table><tbody>" + "".join(
        f"<tr><td>{_e(k)}</td><td class='num'>{_e('–' if v is None else v)}</td></tr>" for k, v in stat_rows) + "</tbody></table></div>")

    by_route = s.get("today", {}).get("by_route", {})
    if by_route:
        parts.append("<h2>By route</h2><div class='scroll'><table><thead><tr><th>Route</th><th class='num'>Options</th>"
                     "<th class='num'>Cheapest</th><th class='num'>Best value</th><th class='num'>Fastest out</th>"
                     "<th class='num'>Fastest back</th></tr></thead><tbody>" + "".join(
                         f"<tr><td>{_e(k)} · {_e(v['label'])}</td><td class='num'>{v['options']}</td>"
                         f"<td class='num'>{_money(v['cheapest_price'])}</td><td class='num'>{v['best_value']:,.0f}</td>"
                         f"<td class='num'>{v['fastest_hours_out']}h</td><td class='num'>{v['fastest_hours_back']}h</td></tr>"
                         for k, v in by_route.items()) + "</tbody></table></div>")
    by_pair = s.get("today", {}).get("by_date_pair", {})
    if by_pair:
        parts.append("<h2>By date pair</h2><div class='scroll'><table><thead><tr><th>Out → Back</th>"
                     "<th class='num'>Best price</th><th class='num'>Best value</th><th>Route</th></tr></thead><tbody>"
                     + "".join(f"<tr><td>{_e(k.replace('_', ' → '))}</td><td class='num'>{_money(v['best_price'])}</td>"
                               f"<td class='num'>{v['best_value']:,.0f}</td><td>{_e(v['route'])}</td></tr>"
                               for k, v in by_pair.items()) + "</tbody></table></div>")

    parts.append("<h2>JEV second opinion</h2>" + _jev_panel(r.get("jev", {})))

    ut = usage_text(r.get("api_usage"))
    parts.append("<h2>Providers this run</h2>" + (f"<p class='muted'>{_e(ut)}</p>" if ut else "") + "<div class='scroll'><table><thead><tr><th>Provider</th><th>Status</th>"
                 "<th class='num'>API calls</th><th class='num'>Itineraries</th><th>Notes</th></tr></thead><tbody>" + "".join(
                     f"<tr><td>{_e(p['provider'])}</td><td>{'skipped' if p['skipped'] else ('ok' if p['ok'] else 'FAILED')}</td>"
                     f"<td class='num'>{p['calls']}</td><td class='num'>{p['itineraries']}</td>"
                     f"<td style='white-space:normal'>{_e('; '.join(p['errors'][:3]))}</td></tr>"
                     for p in r.get("providers", [])) + "</tbody></table></div>")

    if recent_runs:
        parts.append("<h2>Recent runs</h2><div class='scroll'><table><thead><tr><th>When</th><th>Status</th>"
                     "<th>Decision</th><th class='num'>Best price</th><th>Route</th><th>Reason</th></tr></thead><tbody>"
                     + "".join(f"<tr><td>{_e(str(x['run_at'])[:16].replace('T', ' '))}</td><td>{_e(x['status'])}</td>"
                               f"<td>{_e(x['decision'])}</td><td class='num'>{_money(x['best_price'])}</td>"
                               f"<td>{_e(x['best_route'])}</td><td style='white-space:normal'>{_e(x['reason'])}</td></tr>"
                               for x in recent_runs) + "</tbody></table></div>")
    if log_lines:
        parts.append("<h2>Run log</h2><div class='card scroll'><code>" +
                     "<br>".join(_e(line) for line in log_lines[-30:]) + "</code></div>")
    parts.append("<p class='muted' style='margin-top:30px'>Fares come only from provider responses; if a provider "
                 "fails, it says so above and nothing is filled in. JSON: <a href='/api/report'>/api/report</a> · "
                 "log: <a href='/api/log'>/api/log</a></p>")
    return _page("".join(parts))


def _page(body: str) -> str:
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>MEL → ELS tracker</title>"
            f"<style>{CSS}</style></head><body><main>{body}</main></body></html>")
