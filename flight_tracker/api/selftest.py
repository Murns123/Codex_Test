"""GET /api/selftest – configuration and storage check.

Touches only selftest/probe.json and shows which settings are present (never their values).

GET /api/selftest?probe=ignav&secret=<CRON_SECRET> additionally makes ONE Ignav search on
the primary dates and reports the response structure (field names) next to what the parser
extracted, so the adapter can be checked against the real API. Costs one Ignav call.
"""
import datetime as dt
import hmac
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fttracker.web import send, settings

from fttracker.runner import open_storage


def _shape(obj, depth=0):
    """Field names and types only – enough to check the parser, no bulky values."""
    if depth > 7:
        return type(obj).__name__
    if isinstance(obj, dict):
        return {k: _shape(v, depth + 1) for k, v in list(obj.items())[:40]}
    if isinstance(obj, list):
        return [f"{len(obj)} items", _shape(obj[0], depth + 1)] if obj else []
    return type(obj).__name__ if not isinstance(obj, (int, float, str, bool)) or depth == 0 else repr(obj)[:60]


def probe_ignav(s):
    from fttracker.providers.ignav import IgnavProvider, parse_response
    kept = {}
    p = IgnavProvider(s, lambda label, payload: kept.setdefault(label, payload) and label)
    ok, why = p.is_configured()
    if not ok:
        return {"ok": False, "error": why}
    out_date, ret_date = s.trip.date_pairs()[0]
    res = p.search([(out_date, ret_date)])
    payload = next(iter(kept.values()), {})
    response = payload.get("response")
    parsed, problems = parse_response(response, out_date, ret_date, s.trip.currency) if response else ([], [])
    return {
        "ok": res.ok, "errors": res.errors, "request_body": payload.get("request"),
        "response_shape": _shape(response) if response is not None else None,
        "parsed_itineraries": len(parsed), "parse_problems": problems,
        "parsed_sample": [{
            "price": i.price, "out": "-".join(i.outbound.airports), "back": "-".join(i.inbound.airports),
            "hours": [round(i.outbound.hours, 1), round(i.inbound.hours, 1)], "carriers": i.carriers,
            "single_ticket": i.single_ticket, "booking_link": bool(i.booking_link)} for i in parsed[:3]],
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        s = settings()
        q = parse_qs(urlparse(self.path).query)
        out = {"env_present": {k: bool(v) for k, v in s.env.items() if k != "VERCEL"}, "checks": {}}
        ok = True
        try:
            storage = open_storage(s)
            out["storage"] = type(storage).__name__
            store = getattr(storage, "store", None)
            if store is None:
                out["checks"]["blob"] = "not configured – connect a Blob store to the project"
                ok = False
            else:
                stamp = dt.datetime.now(dt.timezone.utc).isoformat()
                store.put_json("selftest/probe.json", {"written_at": stamp})
                out["checks"]["put"] = "ok"
                out["checks"]["list"] = store.list("selftest/")
                got = store.get_json("selftest/probe.json")
                out["checks"]["get"] = "ok" if got and got.get("written_at") == stamp else f"unexpected: {got}"
                out["checks"]["runs_indexed"] = len(storage.recent_runs(10_000))
                ok = out["checks"]["get"] == "ok"
        except Exception as exc:
            out["error"] = f"{type(exc).__name__}: {exc}"
            ok = False

        if q.get("probe") == ["ignav"]:
            secret = os.environ.get("CRON_SECRET", "")
            if not secret or not hmac.compare_digest(q.get("secret", [""])[0], secret):
                out["ignav_probe"] = {"ok": False, "error": "add &secret=<CRON_SECRET> to run the Ignav probe"}
            else:
                try:
                    out["ignav_probe"] = probe_ignav(s)
                except Exception as exc:
                    out["ignav_probe"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        out["ok"] = ok
        send(self, 200 if ok else 500, out)
