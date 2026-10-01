"""Renders a stored run report as a plain-text summary (CLI) or an HTML dashboard (Vercel)."""
from __future__ import annotations

import datetime as dt
import html
from typing import Any
from zoneinfo import ZoneInfo

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
    for sec in (r.get("routes") or {}).values():
        pre = sec.get("prefix", "mj")
        lines += ["", f"{sec.get('title')}: {sec.get('status')}"
                  + (f" – {sec['decision']['decision']}: {sec['decision']['reason']}" if sec.get("decision") else "")]
        lines.append(f"  return {_money((sec.get('series') or {}).get(pre + '_rt'))}")
        for o in (sec.get("options") or {}).get("rt", [])[:3]:
            lines.append(f"  - {_money(o['price_aud'])} {o['dates']} {o['out']['flights']} / {o['back']['flights']}")
    q = r.get("qantas")
    if q:
        cur = q.get("series") or {}
        lines += ["", f"Qantas SYD ⇄ JNB: {q.get('status')}"
                  + (f" – {q['decision']['decision']}: {q['decision']['reason']}" if q.get("decision") else "")]
        lines.append(f"  return {_money(cur.get('qf_rt'))} · SYD→JNB {_money(cur.get('qf_out'))} · "
                     f"JNB→SYD {_money(cur.get('qf_back'))}")
        for o in (q.get("options") or {}).get("rt", [])[:3]:
            lines.append(f"  - {_money(o['price_aud'])} {o['dates']} {o['out']['flights']} / {o['back']['flights']}"
                         + (" (nonstop)" if o["nonstop_both"] else ""))
        qj = q.get("jev") or {}
        if qj.get("ok") and qj.get("buy_probability") is not None:
            lines.append(f"  JEV P(book Qantas today) = {qj['buy_probability']:.0%}")
        for e in (q.get("errors") or [])[:3]:
            lines.append(f"  ! {e}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------
CSS = """
:root{
 --navy:#2b2996;--brand:#2d4399;--blue:#008dff;--mid:#4278dd;--steel:#5188cc;--sky:#96baff;
 --bg:#f3f6fc;--card:#fff;--ink:#141a33;--muted:#5d6687;--line:#e3e8f5;--soft:#eef3ff;
 --buy:#12a150;--hold:#e08a00;--stop:#6b7280;--bar:var(--blue);
 --warn-bg:#fff6e6;--warn:#8a5300;--fix-bg:#ffe9ec;--fix:#b4002a;
 --shadow:0 1px 2px rgba(20,26,51,.06),0 6px 20px rgba(45,67,153,.08)}
@media (prefers-color-scheme:dark){:root{
 --bg:#0b1030;--card:#131a45;--ink:#e9edff;--muted:#a3acd6;--line:#232d66;--soft:#1a2357;
 --buy:#2fd27a;--hold:#ffb02e;--stop:#9ca3af;--bar:#4aa8ff;--warn-bg:#3a2a0e;--warn:#ffc874;
 --fix-bg:#4a1020;--fix:#ff9fb0;--shadow:0 1px 2px rgba(0,0,0,.3),0 8px 24px rgba(0,0,0,.35)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.55 Roboto,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
.hero{background:linear-gradient(120deg,var(--navy) 0%,var(--brand) 45%,var(--blue) 100%);color:#fff;
 padding:26px 16px 58px;position:relative;overflow:hidden}
.hero:after{content:"";position:absolute;right:-80px;top:-120px;width:420px;height:420px;border-radius:50%;
 background:radial-gradient(circle,rgba(150,186,255,.35),rgba(150,186,255,0) 70%)}
.hero .in{max-width:1008px;margin:0 auto;position:relative;z-index:1}
.brandrow{display:flex;align-items:center;gap:14px;flex-wrap:wrap}.clocks{margin-left:auto;display:flex;gap:10px}.clock{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);border-radius:12px;padding:6px 14px;min-width:128px}.clock .t{font-size:22px;font-weight:500;font-variant-numeric:tabular-nums;line-height:1.2}.clock .z{font-size:11px;text-transform:uppercase;letter-spacing:.8px;opacity:.8}.clock .d{font-size:12px;opacity:.75}.brandrow>div:nth-child(2){flex:1 1 240px;min-width:0}
.logo{width:46px;height:46px;border-radius:12px;background:rgba(255,255,255,.14);display:grid;place-items:center;
 box-shadow:inset 0 0 0 1px rgba(255,255,255,.25);flex-shrink:0}
.hero h1{font-weight:300;font-size:26px;letter-spacing:.2px;margin:0;line-height:1.2}
.hero h1 b{font-weight:700}
.hero .sub{opacity:.85;font-size:14px;margin-top:2px}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.chip{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.22);border-radius:999px;
 padding:4px 12px;font-size:13px;white-space:nowrap}
nav{display:flex;gap:6px;flex-wrap:wrap;margin-top:14px}
nav a{color:#fff;text-decoration:none;font-size:13px;font-weight:500;padding:6px 12px;border-radius:999px;
 background:rgba(11,16,48,.25)}nav a:hover{background:rgba(255,255,255,.22)}
main{max-width:1040px;margin:0 auto;padding:8px 16px 60px;overflow-wrap:anywhere}
h2{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;color:var(--brand);
 margin:40px 0 12px;display:flex;align-items:center;gap:10px}
h2:after{content:"";flex:1;height:1px;background:var(--line)}
@media (prefers-color-scheme:dark){h2{color:var(--sky)}}
h3{font-size:15px;font-weight:500;margin:26px 0 8px}
.lead{color:var(--muted);margin:-4px 0 14px;font-size:14px}
.muted{color:var(--muted)}.small{font-size:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;box-shadow:var(--shadow)}
.banner{display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.pill{font-weight:700;font-size:15px;letter-spacing:1px;padding:7px 14px;border-radius:999px;color:#fff;
 white-space:nowrap;overflow-wrap:normal;flex-shrink:0}
.BUY{background:var(--buy)}.HOLD{background:var(--hold)}.STOP{background:var(--stop)}
.warn{background:var(--warn-bg);color:var(--warn);border-radius:12px;padding:10px 14px;margin:12px 0;font-size:14px}
.fixture{background:var(--fix-bg);color:var(--fix);font-weight:700;border-radius:12px;padding:10px 14px;margin:12px 0}
.answers{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(290px,100%),1fr));gap:14px;margin-top:-34px;
 position:relative;z-index:2}
a.answer{color:inherit;text-decoration:none;display:block;border-top:4px solid var(--mid);
 transition:transform .15s ease,box-shadow .15s ease}
a.answer:hover{transform:translateY(-2px);box-shadow:0 2px 4px rgba(20,26,51,.08),0 14px 30px rgba(45,67,153,.16)}
a.answer.dBUY{border-top-color:var(--buy)}a.answer.dHOLD{border-top-color:var(--hold)}
.answer .l{color:var(--muted);font-size:12px;font-weight:500;text-transform:uppercase;letter-spacing:.8px;margin-bottom:10px}
.answer .row{display:flex;gap:12px;align-items:center;margin-bottom:10px}
.answer .v{font-size:26px;font-weight:700;letter-spacing:-.3px;font-variant-numeric:tabular-nums}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(170px,100%),1fr));gap:12px;margin-top:12px}
.kpi{padding:14px 16px}.kpi .l{color:var(--muted);font-size:12px;font-weight:500}
.kpi .v{font-size:22px;font-weight:700;color:var(--brand);font-variant-numeric:tabular-nums;margin-top:2px}
@media (prefers-color-scheme:dark){.kpi .v{color:#fff}}
.kpi .s{color:var(--muted);font-size:12px;margin-top:2px}
.scroll{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top;white-space:nowrap}
tbody tr:last-child td,tbody tr:last-child th{border-bottom:0}
thead th{color:var(--muted);font-weight:500;font-size:11px;text-transform:uppercase;letter-spacing:.8px;background:var(--soft)}
tbody tr:hover{background:var(--soft)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}td.wrap{white-space:normal;min-width:160px}
td.best{font-weight:700;color:var(--buy)}
.bar{height:8px;background:var(--soft);border-radius:4px;overflow:hidden;min-width:90px}
.bar>span{display:block;height:100%;border-radius:4px;background:linear-gradient(90deg,var(--mid),var(--blue))}
details{margin-top:14px}summary{cursor:pointer;font-weight:500;color:var(--brand)}
@media (prefers-color-scheme:dark){summary{color:var(--sky)}}
details[open] summary{margin-bottom:10px}details .scroll{box-shadow:none}
a{color:var(--blue)}ul{margin:6px 0;padding-left:20px}ul li{margin:4px 0}code{font-size:12.5px}
.suggest{list-style:none;padding:0;display:grid;gap:8px}
.suggest li{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--blue);border-radius:10px;
 padding:10px 14px;box-shadow:var(--shadow);margin:0}
svg{max-width:100%;height:auto;display:block}
footer{max-width:1040px;margin:0 auto;padding:22px 16px 40px;color:var(--muted);font-size:13px;border-top:1px solid var(--line)}
footer b{color:var(--ink);font-weight:500}
@media (max-width:600px){.hero{padding-bottom:46px}.clocks{margin-left:0;width:100%}.clock{flex:1;min-width:0}.hero h1{font-size:21px}.chip{white-space:normal}.answers{margin-top:-24px}.answer .v{font-size:22px}}
"""


def _e(x: Any) -> str:
    return html.escape("" if x is None else str(x))


def _d(iso: str | None) -> str:
    """'2026-12-22' -> '22 Dec' (consistent date style across the page)."""
    if not iso:
        return "–"
    try:
        return dt.date.fromisoformat(str(iso)[:10]).strftime("%-d %b")
    except ValueError:
        return str(iso)


def _num(v: Any, kind: str) -> str:
    if v is None:
        return "–"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if kind == "money":
        return _money(v)
    if kind == "pct":
        return f"{v:+.1f}%" if isinstance(v, (int, float)) else str(v)
    if kind == "slope":
        return f"{v:+,.0f} AUD/day"
    if kind == "pctile":
        return f"{v:.0f}%"
    if kind == "z":
        return f"{v:+.2f}"
    return f"{v:,}" if isinstance(v, int) else str(v)


# (key, label, kind) – statistics shown in the collapsible "Detailed statistics" boxes
STAT_ROWS = [
    ("days_observed", "Days observed", "int"), ("baseline_value", "Day-1 baseline", "money"),
    ("all_time_low_value", "Lowest seen", "money"), ("all_time_high_value", "Highest seen", "money"),
    ("mean_value", "Average", "money"), ("stdev_value", "Standard deviation", "money"),
    ("current_zscore", "Today vs average (z-score)", "z"), ("current_percentile", "Today's percentile", "pctile"),
    ("is_all_time_low", "Today is the lowest seen", "bool"), ("days_since_low", "Days since the low", "int"),
    ("slope_7d_aud_per_day", "7-day trend", "slope"), ("slope_all_aud_per_day", "Trend since day 1", "slope"),
    ("vs_7d_mean_pct", "Today vs 7-day average", "pct"), ("volatility_daily_pct", "Day-to-day volatility", "pct"),
    ("up_days", "Days up", "int"), ("down_days", "Days down", "int"),
    ("largest_daily_rise_pct", "Biggest daily rise", "pct"), ("largest_daily_drop_pct", "Biggest daily drop", "pct"),
]

JEV_LABELS = {
    # main trip
    "book_now_is_right": "Booking today is the right call", "likely_rise_next_7d": "Price higher in 7 days",
    "likely_drop_5pct_before_book_by": "Drop of 5%+ before 14 Oct", "trend_is_upward": "Genuine upward trend",
    "current_is_good_price": "Today's price is a good price", "volatility_high": "Volatile enough to risk a jump",
    "best_option_good_value": "Top option is good overall value", "connection_risk_high": "Top option has risky connections",
    "flex_dates_worth_it": "Flex dates worth switching to", "self_transfer_worth_considering": "Self-transfer worth the risk",
    "data_quality_concern": "Data-quality concern (short history, gaps)", "action": "Recommended action",
    "preferred_route": "Preferred route", "urgency": "Urgency",
    # Qantas
    "rt_rise_next_7d": "Return higher in 7 days", "rt_drop_5pct_before_book_by": "Return drops 5%+ before 14 Oct",
    "rt_good_price": "Return is a good price", "fare_bucket_closing": "Cheaper fare buckets selling out",
    "one_ways_better_than_return": "Two one-ways beat the return", "nonstop_worth_premium": "Nonstop worth the premium",
    "outbound_scarcity_risk": "SYD → JNB sell-out risk", "return_scarcity_risk": "JNB → SYD sell-out risk",
    "qantas_beats_main_best": "Qantas plan beats the MEL → ELS best",
    "beats_main_best": "This route + own connection beats the MEL → ELS best", "preferred_airline": "Preferred airline", "value_rating": "Value for money",
    "best_outbound_date": "Best SYD → JNB date", "best_return_date": "Best JNB → SYD date",
}
CHOICE_LABELS = {"hold": "Hold", "buy_now": "Book now", "buy_flex": "Book on flex dates",
                 "book_return_now": "Book the return", "book_one_ways_now": "Book two one-ways",
                 "A": "A · Qantas via PER", "B": "B · Qantas via SYD", "C": "C · SAA via PER",
                 "D": "D · Gulf/Asia hub", "other": "Other"}


def _choice_label(v: str) -> str:
    if v in CHOICE_LABELS:
        return CHOICE_LABELS[v]
    return _d(v) if len(v) == 10 and v[4] == "-" else v


def _options_table(opts: list[dict[str, Any]]) -> str:
    if not opts:
        return "<p class='muted'>No fares were retrieved this run, so none are shown.</p>"
    rows = []
    for i, o in enumerate(opts, 1):
        link = (f"<a href='{_e(o['booking_link'])}' target='_blank' rel='noopener'>{_e(o.get('link_kind') or 'book')}</a>"
                if o.get("booking_link") else "–")
        flags = []
        if o["too_long"]:
            flags.append("over 30h one way")
        if not o["single_ticket"]:
            flags.append("self-transfer")
        note = ""   # prices are shown in AUD only; the USD source amount stays in /api/report
        rows.append(
            f"<tr><td>{i}</td><td class='num'>{_money(o['price_aud'])}{note}</td>"
            f"<td>{_e(o['route'])} · {_e(o['route_label'])}<div class='muted small'>{_e('/'.join(o['carriers']))}</div></td>"
            f"<td class='num'>{o['hours_out']}h · {o['stops_out']} stop{'s' if o['stops_out'] != 1 else ''}</td>"
            f"<td class='num'>{o['hours_back']}h · {o['stops_back']} stop{'s' if o['stops_back'] != 1 else ''}</td>"
            f"<td class='num'>{o['longest_layover_h']}h</td><td class='num'>{o['value_score']:,.0f}</td>"
            f"<td class='wrap'>{_e(', '.join(flags)) or '–'}</td><td>{link}</td></tr>")
    return ("<div class='scroll'><table><thead><tr><th>#</th><th class='num'>Price</th><th>Route</th>"
            "<th class='num'>Out</th><th class='num'>Back</th><th class='num'>Longest layover</th>"
            "<th class='num'>Value score</th><th>Flags</th><th>Link</th></tr></thead><tbody>"
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
    dots = "".join(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='3.5' fill='var(--card)' stroke='var(--bar)' stroke-width='2'><title>{_e(d)}: {v:,.0f}</title></circle>"
                   for (d, v), x, y in zip(points, xs, ys))
    gid = f"g{abs(hash(tuple(vals))) % 10**6}"
    area = path + f" L{xs[-1]:.1f},{h - pad} L{xs[0]:.1f},{h - pad} Z"
    return (f"<svg viewBox='0 0 {w} {h}' role='img' aria-label='Trend by day'>"
            f"<defs><linearGradient id='{gid}' x1='0' y1='0' x2='0' y2='1'>"
            "<stop offset='0' stop-color='#008dff' stop-opacity='.28'/><stop offset='1' stop-color='#008dff' stop-opacity='0'/>"
            f"</linearGradient></defs><path d='{area}' fill='url(#{gid})'/>"
            f"<path d='{path}' fill='none' stroke='var(--bar)' stroke-width='2.5' stroke-linejoin='round'/>{dots}"
            f"<text x='{pad}' y='14' fill='var(--muted)' font-size='11'>{hi:,.0f}</text>"
            f"<text x='{pad}' y='{h - 6}' fill='var(--muted)' font-size='11'>{lo:,.0f}</text></svg>")


def _jev_panel(j: dict[str, Any], order: list[str] | None = None, org: str = "SYD", dst: str = "JNB") -> str:
    if j.get("skipped"):
        return f"<p class='muted'>JEV not used this run ({_e(j.get('error'))}).</p>"
    if not j.get("ok"):
        return f"<div class='warn'>JEV failed: {_e(j.get('error'))}. The decision above is from the rules only.</div>"
    a = j.get("answers", {})
    keys = list(dict.fromkeys([k for k in (order or []) if k in a] + list(a)))   # ordered, no repeats
    choices, probs = [], []
    for key in keys:
        v = a[key]
        label = _e(JEV_LABELS.get(key, key.replace("_", " "))
                   .replace("SYD → JNB", f"{org} → {dst}").replace("JNB → SYD", f"{dst} → {org}"))
        if isinstance(v, dict) and "probabilities" in v:
            ps = ", ".join(f"{_choice_label(k)} {p:.0%}" for k, p in sorted((v.get("probabilities") or {}).items(),
                                                                       key=lambda kv: -kv[1]) if p >= 0.01)
            choices.append(f"<tr><td>{label}</td><td><b>{_e(_choice_label(str(v.get('choice'))))}</b></td>"
                           f"<td class='wrap muted'>{_e(ps)}</td></tr>")
        elif isinstance(v, dict) and "score" in v:
            sc = v.get("score")
            choices.append(f"<tr><td>{label}</td><td><b>{sc:.1f}</b> / 5</td>"
                           f"<td class='muted'>confidence {v.get('confidence') or 0:.0%}</td></tr>")
        elif isinstance(v, (int, float)):
            probs.append(f"<tr><td>{label}</td><td class='num'>{v:.0%}</td>"
                         f"<td><div class='bar'><span style='width:{v * 100:.0f}%'></span></div></td></tr>")
    bp = j.get("buy_probability")
    head = (f"<p><b>Probability that booking today is right: {bp:.0%}</b> "
            f"<span class='muted'>(model {_e(j.get('model'))})</span></p>") if bp is not None else ""
    return (head + "<div class='scroll'><table><tbody>" + "".join(choices) + "</tbody></table></div>"
            + ("<h3>Probabilities</h3><div class='scroll'><table><tbody>" + "".join(probs) + "</tbody></table></div>"
               if probs else ""))


def _jev_line(j: dict[str, Any] | None) -> str:
    j = j or {}
    if not j.get("ok"):
        return "JEV: not available this run"
    act = (j.get("answers") or {}).get("action") or {}
    bp = j.get("buy_probability")
    return (f"JEV: {_choice_label(str(act.get('choice', '–')))}"
            + (f" · {bp:.0%} that booking today is right" if bp is not None else ""))


def _stats_details(series: list[tuple[str, dict[str, Any]]], extra_rows: str = "") -> str:
    head = "".join(f"<th class='num'>{_e(n)}</th>" for n, _ in series)
    body = "".join("<tr><td>" + _e(label) + "</td>" + "".join(
        f"<td class='num'>{_e(_num((h or {}).get(k), kind))}</td>" for _, h in series) + "</tr>"
        for k, label, kind in STAT_ROWS)
    return ("<details class='card'><summary>Detailed statistics</summary><div class='scroll'><table><thead><tr><th></th>"
            f"{head}</tr></thead><tbody>{body}{extra_rows}</tbody></table></div></details>")


def _decision_card(title: str, anchor: str, d: dict[str, Any] | None, price: str, price_label: str,
                   j: dict[str, Any] | None) -> str:
    if not d:
        return (f"<a class='card answer' href='#{anchor}'><div class='l'>{_e(title)}</div>"
                "<div class='muted'>Not run.</div></a>")
    return (f"<a class='card answer d{_e(d['decision'])}' href='#{anchor}'><div class='l'>{_e(title)}</div>"
            f"<div class='row'><span class='pill {_e(d['decision'])}'>{_e(d['decision'])}</span>"
            f"<div><div class='v'>{_e(price)}</div><div class='muted small'>{_e(price_label)}</div></div></div>"
            f"<div class='small'>{_e(d['reason'])}</div><div class='muted small'>{_e(_jev_line(j))}</div></a>")


def _kpis(tiles: list[tuple[str, Any, str]]) -> str:
    return "<div class='grid'>" + "".join(
        f"<div class='card kpi'><div class='l'>{_e(a)}</div><div class='v'>{_e(b)}</div><div class='s'>{_e(c)}</div></div>"
        for a, b, c in tiles) + "</div>"


def to_html(r: dict[str, Any] | None, recent_runs: list[dict[str, Any]] | None = None,
            log_lines: list[str] | None = None) -> str:
    if r is None:
        body = ("<h1>MEL → ELS flight tracker</h1><p class='muted'>No runs yet. The first scheduled run will "
                "set the baseline.</p>")
        return _page(body)
    d, t, s = r["decision"], r["trend"], r.get("stats", {})
    q = r.get("qantas") or {}
    run_at = dt.datetime.fromisoformat(r["run_at"])
    b = r.get("best")
    cal0 = (r.get("stats") or {}).get("calendar", {})
    hero = (f"<header class='hero'><div class='in'><div class='brandrow'><div class='logo'>{LOGO}</div>"
            f"<div><h1>Murn's <b>Melbourne SA</b> Flight Tracker</h1>"
            "<div class='sub'>Melbourne → East London · 21 Dec 2026 – 8 Jan 2027 · 1 adult economy</div></div>"
            f"{_clocks()}</div>"
            "<div class='chips'>"
            f"<span class='chip'>Day {_e(r.get('day') or '–')} of tracking</span>"
            f"<span class='chip'>Last run {run_at:%a %-d %b, %H:%M}</span>"
            f"<span class='chip'>{_e(cal0.get('days_to_book_by', '–'))} days to book-by (14 Oct)</span>"
            "<span class='chip'>Runs 07:00 · 12:00 · 17:00</span></div>"
            "<nav><a href='#trip'>MEL → ELS trip</a>"
            + "".join(f"<a href='#route-{_e(n)}'>{_e(_section_meta(sec)[5])}</a>" for n, sec in (r.get("routes") or {}).items())
            + ("<a href='#qantas'>Qantas SYD ⇄ JNB</a>" if q else "") + "<a href='#data'>Data &amp; runs</a></nav>"
            "</div></header>")
    parts: list[str] = []
    if r.get("fixture_data"):
        parts.append("<div class='fixture'>FIXTURE DATA – these are test fares, not real prices.</div>")

    # --- today's answers ---------------------------------------------------------------------
    routes = r.get("routes") or {}

    def route_card(sec: dict[str, Any], anchor: str) -> str:
        prefix, S, org, dst, airline, title = _section_meta(sec)
        return _decision_card(f"{title} return", anchor, sec.get("decision"),
                              _money((sec.get("series") or {}).get(S[0])),
                              f"{airline + ' only' if airline else 'any airline'} · 21 Dec / 8 Jan · "
                              f"excludes the domestic leg", sec.get("jev"))
    parts.append("<div class='answers'>"
                 + _decision_card("MEL → ELS trip (21 Dec / 8 Jan)", "trip", d,
                                  _money(b["price_aud"]) if b else "no fares",
                                  f"best single ticket · route {b['route']}" if b else "", r.get("jev"))
                 + "".join(route_card(sec, f"route-{name}") for name, sec in routes.items())
                 + (route_card(q, "qantas") if q else "")
                 + "</div>")
    for p in provider_problems(r):
        parts.append(f"<div class='warn'>{_e(p)}</div>")

    # --- main trip ---------------------------------------------------------------------------
    fs = r.get("flex_saving")
    cal = s.get("calendar", {})
    gi = r.get("google_insights") or {}
    flex_sub = flex_text(fs).split(" – ", 1)[-1] if fs else "the primary dates are best"
    if r.get("flex_checked_at") and not r.get("flex_searched"):
        flex_sub += f" · checked {_d(r['flex_checked_at'])} {r['flex_checked_at'][11:16]}"
    parts.append("<h2 id='trip'>MEL → East London trip</h2>")
    parts.append(f"<div class='card banner'><span class='pill {_e(d['decision'])}'>{_e(d['decision'])}</span>"
                 f"<div>{_e(d['reason'])}" + "".join(f"<div class='muted'>{_e(n)}</div>" for n in d.get("notes", []))
                 + "</div></div>")
    parts.append(_kpis([
        ("Best single-ticket fare", _money(b["price_aud"]) if b else "–",
         f"route {b['route']} · {'/'.join(b['carriers'])}" if b else "no fares retrieved"),
        ("vs yesterday", _pct(t.get("vs_previous_pct")), "change in value score"),
        ("vs day 1", _pct(t.get("vs_baseline_pct")), "change in value score"),
        ("Google price level", (gi.get("price_level") or "–").upper(),
         (insights_text(gi) or "no insight returned").split(", ", 1)[-1]),
        ("Best flex dates", fs["dates"] if fs else "none", flex_sub),
        ("Days to book-by", cal.get("days_to_book_by", "–"), "14 Oct 2026"),
    ]))
    parts.append("<h3>Top 3 options – 21 Dec / 8 Jan</h3>" + _options_table(r.get("top3", [])))
    parts.append("<h3>Suggestions</h3><ul class='suggest'>" + "".join(f"<li>{_e(x)}</li>" for x in r.get("suggestions", [])) + "</ul>")
    parts.append("<h3>JEV second opinion</h3>" + _jev_panel(r.get("jev", {}), list(QUESTIONS)))

    by_pair = s.get("today", {}).get("by_date_pair", {})
    if by_pair:
        outs = sorted({k.split("_")[0] for k in by_pair}); rets = sorted({k.split("_")[1] for k in by_pair})
        top = min(v["best_value"] for v in by_pair.values())

        def cell(o: str, b_: str) -> str:
            v = by_pair.get(f"{o}_{b_}")
            if not v:
                return "<td class='num muted'>–</td>"
            cls = "num best" if v["best_value"] == top else "num"
            prim = " <span class='muted small'>(primary)</span>" if (o, b_) == ("2026-12-21", "2027-01-08") else ""
            return (f"<td class='{cls}'>{_money(v['best_price'])}{prim}<div class='muted small'>value "
                    f"{v['best_value']:,.0f} · {_e(v['route'])}</div></td>")
        parts.append("<h3>Flex dates – best fare by date (±2 days)</h3><p class='muted small'>Rows: outbound from MEL · "
                     "columns: return from ELS · best value score highlighted.</p><div class='scroll'><table><thead><tr>"
                     "<th></th>" + "".join(f"<th class='num'>{_d(r_)}</th>" for r_ in rets) + "</tr></thead><tbody>"
                     + "".join(f"<tr><th>{_d(o)}</th>" + "".join(cell(o, r_) for r_ in rets) + "</tr>" for o in outs)
                     + "</tbody></table></div>")
    by_route = s.get("today", {}).get("by_route", {})
    if by_route:
        parts.append("<h3>By route</h3><div class='scroll'><table><thead><tr><th>Route</th><th class='num'>Options</th>"
                     "<th class='num'>Cheapest</th><th class='num'>Best value</th><th class='num'>Fastest out</th>"
                     "<th class='num'>Fastest back</th></tr></thead><tbody>" + "".join(
                         f"<tr><td>{_e(k)} · {_e(v['label'])}</td><td class='num'>{v['options']}</td>"
                         f"<td class='num'>{_money(v['cheapest_price'])}</td><td class='num'>{v['best_value']:,.0f}</td>"
                         f"<td class='num'>{v['fastest_hours_out']}h</td><td class='num'>{v['fastest_hours_back']}h</td></tr>"
                         for k, v in sorted(by_route.items(), key=lambda kv: kv[1]['best_value'])) + "</tbody></table></div>")

    hist = s.get("history", {})
    closes = [(c["date"], c["value"]) for c in hist.get("recent_closes", [])]
    if b:
        closes.append((run_at.date().isoformat(), b["value_score"]))
    parts.append("<h3>Best value score by day</h3><div class='card'>" + _sparkline(closes) + "</div>")
    gh = gi.get("price_history") or []
    if len(gh) >= 2:
        pts = [(dt.datetime.fromtimestamp(t_, dt.timezone.utc).date().isoformat(), float(p)) for t_, p in gh
               if isinstance(t_, (int, float)) and isinstance(p, (int, float))]
        parts.append("<h3>Google's price history for 21 Dec / 8 Jan</h3><div class='card'>" + _sparkline(pts) + "</div>")
    tdist = s.get("today", {}).get("price_distribution", {})
    extra = "".join(f"<tr><td>Today's fares – {_e(k)}</td><td class='num'>{_money(v)}</td></tr>" for k, v in tdist.items())
    parts.append(_stats_details([("Best value score", hist)], extra))

    # --- Qantas --------------------------------------------------------------------------------
    for name, sec in routes.items():
        parts.append(route_html(sec, f"route-{name}"))
    if q:
        parts.append(qantas_html(q))

    # --- data & runs ------------------------------------------------------------------------------
    parts.append("<h2 id='data'>Data &amp; run details</h2>")
    ut = usage_text(r.get("api_usage"))
    prov = list(r.get("providers", []))
    for sec in list(routes.values()) + ([q] if q else []):
        prov.append({"provider": f"ignav ({_section_meta(sec)[5]})", "skipped": sec.get("status") == "skipped",
                     "ok": sec.get("status") == "ok", "calls": sec.get("calls", 0),
                     "itineraries": sum(len(v) for v in (sec.get("options") or {}).values()),
                     "errors": sec.get("errors", [])})
    notes = [ut] if ut else []
    parts.append("<h3>Sources this run</h3>" + "".join(f"<p class='muted'>{_e(n)}</p>" for n in notes)
                 + "<div class='scroll'><table><thead><tr><th>Source</th><th>Status</th>"
                 "<th class='num'>API calls</th><th class='num'>Fares</th><th>Notes</th></tr></thead><tbody>" + "".join(
                     f"<tr><td>{_e(p['provider'])}</td><td>{'skipped' if p['skipped'] else ('ok' if p['ok'] else 'FAILED')}</td>"
                     f"<td class='num'>{p['calls']}</td><td class='num'>{p['itineraries']}</td>"
                     f"<td class='wrap'>{_e('; '.join(p['errors'][:3])) or '–'}</td></tr>"
                     for p in prov) + "</tbody></table></div>")
    if recent_runs:
        parts.append("<h3>Recent runs</h3><div class='scroll'><table><thead><tr><th>When</th><th>Decision</th>"
                     "<th class='num'>Best MEL→ELS</th><th class='num'>MEL⇄JNB</th><th class='num'>Qantas SYD⇄JNB</th>"
                     "<th>Reason</th></tr></thead><tbody>"
                     + "".join(f"<tr><td>{_d(str(x['run_at']))} {str(x['run_at'])[11:16]}</td><td>{_e(x['decision'])}</td>"
                               f"<td class='num'>{_money(x['best_price'])}</td>"
                               f"<td class='num'>{_money((x.get('series') or {}).get('mj_rt'))}</td>"
                               f"<td class='num'>{_money((x.get('series') or {}).get('qf_rt'))}</td>"
                               f"<td class='wrap'>{_e(x['reason'])}</td></tr>"
                               for x in recent_runs) + "</tbody></table></div>")
    if log_lines:
        parts.append("<details class='card'><summary>Run log</summary><div class='scroll'><code>"
                     + "<br>".join(_e(line) for line in log_lines[-30:]) + "</code></div></details>")
    parts.append("<p class='muted small' style='margin-top:24px'>Fares come only from provider responses; if a "
                 "source fails, it says so above and nothing is filled in. Raw data: <a href='/api/report'>/api/report</a>"
                 " · log: <a href='/api/log'>/api/log</a></p>")
    return _page("".join(parts), hero)


BRAND = "Murn's Melbourne SA Flight Tracker"
LOGO = ("<svg width='26' height='26' viewBox='0 0 24 24' fill='none' aria-hidden='true'>"
        "<path d='M2.5 19h19' stroke='#96baff' stroke-width='1.6' stroke-linecap='round'/>"
        "<path d='M21 8.5c-.4-1-1.7-1.3-2.7-.8L13.6 10 6.9 6.3 4.8 7.2l4.6 4.2-3.3 1.6-2.2-1.2-1.4.6 2.4 3"
        " .9.4 4-1.7 4.6-2 4.8-2.1c1-.5 1.3-1.4.8-2.3z' fill='#fff'/></svg>")


SA_TZ = "Africa/Johannesburg"
HOME_TZ = "Australia/Melbourne"


def _clocks(now: dt.datetime | None = None) -> str:
    """Two live clocks: the viewer's own time (browser zone) and South Africa. Server-rendered
    with Melbourne/SAST so they read sensibly before the script runs."""
    now = now or dt.datetime.now(dt.timezone.utc)

    def one(cid: str, label: str, t: dt.datetime) -> str:
        return (f"<div class='clock' id='{cid}'><div class='z'>{label}</div>"
                f"<div class='t'>{t:%H:%M:%S}</div><div class='d'>{t:%a %-d %b} · {t:%Z}</div></div>")
    return ("<div class='clocks'>" + one("clk-local", "Your time", now.astimezone(ZoneInfo(HOME_TZ)))
            + one("clk-sa", "South Africa", now.astimezone(ZoneInfo(SA_TZ))) + "</div>")


CLOCK_JS = """<script>(function(){
function zone(tz){try{return new Intl.DateTimeFormat('en-AU',{timeZone:tz,timeZoneName:'short'}).formatToParts(new Date())
.find(function(p){return p.type==='timeZoneName'}).value}catch(e){return ''}}
function put(id,tz){var el=document.getElementById(id);if(!el)return;var n=new Date(),o=tz?{timeZone:tz}:{};
el.querySelector('.t').textContent=n.toLocaleTimeString('en-GB',Object.assign({hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false},o));
el.querySelector('.d').textContent=n.toLocaleDateString('en-AU',Object.assign({weekday:'short',day:'numeric',month:'short'},o))
+' · '+(tz==='Africa/Johannesburg'?'SAST':zone(tz||Intl.DateTimeFormat().resolvedOptions().timeZone));}
function tick(){put('clk-local');put('clk-sa','Africa/Johannesburg');}
function loop(){tick();setTimeout(loop,1000-new Date().getMilliseconds()+5);}loop();})();</script>"""


def _page(body: str, hero: str = "", footer: str = "") -> str:
    hero = hero or (f"<header class='hero'><div class='in'><div class='brandrow'><div class='logo'>{LOGO}</div>"
                    f"<div><h1>{_e(BRAND)}</h1><div class='sub'>Melbourne → East London fare intelligence</div>"
                    f"</div>{_clocks()}</div></div></header>")
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{_e(BRAND)}</title><meta name='theme-color' content='#2d4399'>"
            "<link rel='icon' href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E"
            "%3Crect width='24' height='24' rx='6' fill='%232d4399'/%3E%3Cpath d='M20 9c-.4-1-1.6-1.2-2.5-.8L13 10.3 "
            "7 7l-2 .8 4.3 3.9-3 1.5-2-1.1-1.3.6 2.2 2.8.9.4 3.7-1.6 4.3-1.9 4.4-1.9c.9-.4 1.2-1.3.7-2.2z' "
            "fill='white'/%3E%3C/svg%3E\">"
            "<link rel='preconnect' href='https://fonts.googleapis.com'>"
            "<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
            "<link href='https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap' rel='stylesheet'>"
            f"<style>{CSS}</style></head><body>{hero}<main>{body}</main>"
            + (footer or f"<footer><b>{_e(BRAND)}</b> · fares from Ignav and Google Flights · decisions by rules with a "
                         "JEV second opinion</footer>")
            + CLOCK_JS + "</body></html>")


# --- Qantas SYD <-> JNB section ---------------------------------------------------------------
def _qf_options(rows: list[dict[str, Any]], kind: str, empty: str, show_airline: bool = False) -> str:
    if not rows:
        return f"<p class='muted'>{_e(empty)}</p>"
    body = []
    for i, o in enumerate(rows, 1):
        link = (f"<a href='{_e(o['booking_link'])}' target='_blank' rel='noopener'>{_e(o.get('link_kind') or 'book')}</a>"
                if o.get("booking_link") else "–")
        note = ""   # prices are shown in AUD only; the USD source amount stays in /api/report
        if kind == "rt":
            air = f"<td>{_e('/'.join(o.get('carriers') or []))}</td>" if show_airline else ""
            body.append(f"<tr><td>{i}</td><td class='num'>{_money(o['price_aud'])}{note}</td>{air}"
                        f"<td>{_e(o['out']['flights'])}<div class='muted small'>{_e(o['out']['route'])} · {o['out']['hours']}h</div></td>"
                        f"<td>{_e(o['back']['flights'])}<div class='muted small'>{_e(o['back']['route'])} · {o['back']['hours']}h</div></td>"
                        f"<td>{'both ways' if o['nonstop_both'] else ('out only' if o['out']['nonstop'] else ('back only' if o['back']['nonstop'] else 'no'))}</td>"
                        f"<td>{link}</td></tr>")
        else:
            body.append(f"<tr><td>{i}</td><td class='num'>{_money(o['price_aud'])}{note}</td><td>{_d(o['date'])}</td>"
                        f"<td>{_e(o['flights'])}<div class='muted small'>{_e(o['route'])} · {o['hours']}h</div></td>"
                        f"<td>{'yes' if o['nonstop'] else 'no'}</td><td>{link}</td></tr>")
    head = ("<th>#</th><th class='num'>Price</th>" + ("<th>Airline</th>" if show_airline else "") + "<th>Out (21 Dec)</th><th>Back (8 Jan)</th><th>Nonstop</th><th>Link</th>"
            if kind == "rt" else
            "<th>#</th><th class='num'>Price</th><th>Date</th><th>Flights</th><th>Nonstop</th><th>Link</th>")
    return f"<div class='scroll'><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"


def _section_meta(q: dict[str, Any]) -> tuple[str, list[str], str, str, str, str]:
    """(prefix, series names, origin, destination, airline phrase, title) – works for reports stored
    before the sections were generalised (Qantas only, no metadata)."""
    prefix = q.get("prefix") or "qf"
    org, dst = q.get("origin", "SYD"), q.get("destination", "JNB")
    airline = q.get("airline") if "airline" in q else "Qantas"
    title = q.get("title") or f"{airline + ' ' if airline else ''}{org} ⇄ {dst}"
    return prefix, q.get("series_names") or [f"{prefix}_rt", f"{prefix}_out", f"{prefix}_back"], org, dst, \
        (airline or ""), title


def route_html(q: dict[str, Any], anchor: str) -> str:
    from .qantas import route_questions
    prefix, S, org, dst, airline, title = _section_meta(q)
    al = f"{airline} " if airline else ""
    scope = (f"{airline}-only fares" if airline else "Fares on any airline")
    parts = [f"<h2 id='{_e(anchor)}'>{_e(title)}</h2>",
             f"<p class='lead'>{scope} between {_e(org)} and {_e(dst)} on the trip dates – the domestic "
             "connection to East London is not included. Tracked separately from the MEL → ELS trip, with its "
             "own rules and JEV evaluation.</p>"]
    if q.get("fixture_data"):
        parts.append("<div class='fixture'>FIXTURE DATA – test fares.</div>")
    if q.get("status") in ("skipped", "failed", "no_fares"):
        parts.append(f"<div class='warn'>{_e(title)}: {_e(q.get('status'))}. " + _e("; ".join(q.get("errors", [])[:3])) + "</div>")
    elif q.get("errors"):
        parts.append(f"<div class='warn'>{_e(title)} – issues: " + _e("; ".join(q["errors"][:3])) + "</div>")
    d = q.get("decision")
    if d:
        parts.append(f"<div class='card banner'><span class='pill {_e(d['decision'])}'>{_e(d['decision'])}</span>"
                     f"<div>{_e(d['reason'])}" + "".join(f"<div class='muted'>{_e(n)}</div>" for n in d.get("notes", []))
                     + f"<div class='muted small'>Rules applied to the {_e(al)}{_e(org)}–{_e(dst)} return fare.</div></div></div>")
    cur = q.get("series") or {}
    st = q.get("stats") or {}
    ex = st.get("extra") or {}

    def sub(sname):
        h = st.get(sname) or {}
        b, c = h.get("baseline_value"), cur.get(sname)
        if c is None:
            return f"no {al}fare that day"
        return f"{(c - b) / b * 100:+.1f}% vs day 1" if b and h.get("days_observed", 0) > 1 else "day-1 baseline"
    names = {S[0]: "Return 21 Dec / 8 Jan", S[1]: f"{org} → {dst} one-way, 21 Dec", S[2]: f"{dst} → {org} one-way, 8 Jan"}
    shown = S if q.get("one_way", True) else S[:1]
    tiles = [(names[sn], _money(cur.get(sn)), sub(sn)) for sn in shown]
    if q.get("cheapest_combo"):
        cc = q["cheapest_combo"]
        a_, b_ = cc["dates"].split(" → ")
        tiles.append(("Cheapest return dates", _money(cc["price_aud"]), f"{_d(a_)} → {_d(b_)}"))
    if "return_vs_two_one_ways_aud" in ex:
        v = ex["return_vs_two_one_ways_aud"]
        tiles.append(("Return vs two one-ways", _money(abs(v)),
                      "the return is cheaper" if v > 0 else ("two one-ways are cheaper" if v < 0 else "same price")))
    if "nonstop_premium_aud" in ex:
        tiles.append(("Nonstop premium", _money(ex["nonstop_premium_aud"]), f"over connecting {al}flights"))
    if ex.get("fastest_return_hours") is not None and not airline:
        tiles.append(("Fastest return", f"{ex['fastest_return_hours']}h", "out + back flying time"))
    v = ex.get("rt_vs_main_best_aud", ex.get("qf_rt_vs_main_best_aud"))
    if v is not None:
        not_incl = "JNB–ELS not included" if org == "MEL" else f"MEL–{org} and JNB–ELS not included"
        tiles.append((f"{airline} return vs best MEL → ELS" if airline else "Return vs best MEL → ELS",
                      f"{_money(abs(v))} {'less' if v < 0 else 'more'}",
                      f"{org}–{dst} only – {not_incl}"))
    parts.append(_kpis(tiles))
    opts = q.get("options") or {}
    parts.append("<h3>Return – best options</h3>" + _qf_options(opts.get("rt", []), "rt", f"No {al}return fares this run.",
                                                                 show_airline=not airline))
    if q.get("one_way", True):
        parts.append(f"<h3>{_e(org)} → {_e(dst)} one-way – 21 Dec</h3>"
                     + _qf_options(opts.get("out", []), "ow", f"No {al}one-way fare on 21 Dec this run – see other dates below."))
        parts.append(f"<h3>{_e(dst)} → {_e(org)} one-way – 8 Jan</h3>"
                     + _qf_options(opts.get("back", []), "ow", f"No {al}one-way fare on 8 Jan this run – see other dates below."))
    if ex.get("cheapest_by_airline") and not airline:
        parts.append("<h3>Cheapest return by airline – 21 Dec / 8 Jan</h3><div class='scroll'><table><tbody>" + "".join(
            f"<tr><td>{_e(k)}</td><td class='num'>{_money(v_)}</td></tr>" for k, v_ in ex["cheapest_by_airline"].items())
            + "</tbody></table></div>")
    out_dates = sorted((q.get("ow_by_date") or {}).get("out", {}) or [])
    back_dates = sorted((q.get("ow_by_date") or {}).get("back", {}) or [])
    parts.append(f"<h3>JEV – {_e(title)} evaluation</h3>"
                 + _jev_panel(q.get("jev") or {"skipped": True, "error": "not run"},
                              ["action", "preferred_airline", "best_outbound_date", "best_return_date", "urgency",
                               "value_rating"]
                              + list(route_questions(out_dates or ["x"], back_dates or ["x"], org, dst, airline or None)),
                              org, dst))
    if q.get("rt_matrix"):
        m = q["rt_matrix"]
        outs = sorted({k.split("_")[0] for k in m}); rets = sorted({k.split("_")[1] for k in m})
        best = min(m.values())
        rows = "".join(f"<tr><th>{_d(o)}</th>" + "".join(
            f"<td class='num{' best' if m.get(f'{o}_{r}') == best else ''}'>{_money(m.get(f'{o}_{r}'))}</td>" for r in rets)
            + "</tr>" for o in outs)
        parts.append(f"<h3>Return fare by dates</h3><p class='muted small'>Rows: {_e(org)} → {_e(dst)} date · columns: {_e(dst)} → {_e(org)} date · "
                     "cheapest highlighted.</p><div class='scroll'><table><thead><tr><th></th>"
                     + "".join(f"<th class='num'>{_d(r)}</th>" for r in rets) + f"</tr></thead><tbody>{rows}</tbody></table></div>")
    obd = q.get("ow_by_date") or {}
    if obd.get("out") or obd.get("back"):
        def owrow(side):
            vals = obd.get(side) or {}
            return "".join(f"<td>{_d(k)}: <b>{_money(v)}</b></td>" for k, v in vals.items()) or "<td class='muted'>none</td>"
        parts.append("<h3>One-way fares by date</h3><div class='scroll'><table><tbody>"
                     f"<tr><th>SYD → JNB</th>{owrow('out')}</tr><tr><th>JNB → SYD</th>{owrow('back')}</tr></tbody></table></div>")
    h = st.get(S[0]) or {}
    closes = [(c["date"], c["value"]) for c in h.get("recent_closes", [])]
    if cur.get(S[0]) is not None:
        closes.append(("today", cur[S[0]]))
    parts.append(f"<h3>{_e(al)}{_e(org)} ⇄ {_e(dst)} return – daily closes</h3><div class='card'>" + _sparkline(closes) + "</div>")
    steps = "<tr><td>Fare steps ≥8% (up / down)</td>" + "".join(
        f"<td class='num'>{(st.get(sn) or {}).get('steps', {}).get('step_ups', '–')} / "
        f"{(st.get(sn) or {}).get('steps', {}).get('step_downs', '–')}</td>" for sn in shown) + "</tr>"
    labels = q.get("labels") or {S[0]: f"{org} ⇄ {dst} return", S[1]: f"{org} → {dst} one-way", S[2]: f"{dst} → {org} one-way"}
    parts.append(_stats_details([(labels.get(sn, sn), st.get(sn) or {}) for sn in shown], steps))
    if q.get("note"):
        parts.append(f"<p class='muted small'>{_e(q['note'])}.</p>")
    parts.append(f"<p class='muted small'>{q.get('calls', 0)} Ignav calls this run.</p>")
    return "".join(parts)


def qantas_html(q: dict[str, Any]) -> str:
    return route_html(q, "qantas")
