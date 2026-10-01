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


def blob_diag(s):
    """Try the plausible ways of authenticating a Blob write and report each API answer."""
    import requests
    token = s.env.get("BLOB_READ_WRITE_TOKEN") or s.env.get("VERCEL_OIDC_TOKEN")
    store = s.env.get("BLOB_STORE_ID", "")
    if not token:
        return {"error": "no BLOB_READ_WRITE_TOKEN and no OIDC token on this request"}
    base = s.storage.get("blob", {}).get("base_url", "https://vercel.com/api/blob")
    common = {"authorization": f"Bearer {token}", "x-api-version": "11", "x-vercel-blob-access": "private",
              "x-add-random-suffix": "0", "x-allow-overwrite": "1", "x-content-type": "application/json"}
    variants = {
        "no_store_header": ({}, ""),
        "x-vercel-blob-store-id": ({"x-vercel-blob-store-id": store}, ""),
        "x-store-id": ({"x-store-id": store}, ""),
        "query_storeId": ({}, f"&storeId={store}"),
    }
    out = {"auth": "read_write_token" if s.env.get("BLOB_READ_WRITE_TOKEN") else "oidc", "store_id_set": bool(store)}
    for name, (extra, q) in variants.items():
        try:
            r = requests.put(f"{base}/?pathname=selftest/diag-{name}.json{q}", data=b"{}",
                             headers={**common, **extra}, timeout=20)
            out[name] = {"status": r.status_code, "body": r.text[:200]}
        except Exception as exc:
            out[name] = {"error": f"{type(exc).__name__}: {exc}"[:200]}
    return out


def brand_scan():
    """TEMPORARY: read brand colours/fonts from the fixed profserve.net site (no user-supplied URL)."""
    import re
    from collections import Counter
    from urllib.parse import urljoin

    import requests
    base = "https://profserve.net/"
    out = {}
    r = requests.get(base, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    html = r.text
    css_urls = re.findall(r'<link[^>]+rel=["\']?stylesheet["\']?[^>]*href=["\']([^"\']+)', html)[:8]
    css = html
    for u in css_urls:
        try:
            css += requests.get(urljoin(r.url, u), timeout=15).text[:400000]
        except Exception:
            pass
    hexes = Counter(h.lower() for h in re.findall(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", css))
    rgbs = Counter(re.findall(r"rgba?\([^)]{5,40}\)", css))
    out["status"] = r.status_code
    out["final_url"] = r.url
    out["title"] = (re.search(r"<title>(.*?)</title>", html, re.S) or [None, None])[1]
    out["theme_color"] = re.findall(r'name=["\']theme-color["\'][^>]*content=["\']([^"\']+)', html)
    out["css_vars"] = dict(re.findall(r"(--[\w-]*(?:color|colour|primary|secondary|accent|brand)[\w-]*)\s*:\s*([^;}{]+)", css)[:40])
    out["top_hex"] = hexes.most_common(25)
    out["top_rgb"] = rgbs.most_common(10)
    out["fonts"] = Counter(f.strip()[:80] for f in re.findall(r"font-family\s*:\s*([^;}{]+)", css)).most_common(8)
    out["google_fonts"] = re.findall(r"fonts.googleapis.com/css2?\?family=([^\"'&]+)", css)[:5]
    out["logos"] = [u for u in re.findall(r'<img[^>]+src=["\']([^"\']+)', html) if "logo" in u.lower()][:5]
    out["stylesheets"] = css_urls
    return out


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        s = settings(self.headers)
        q = parse_qs(urlparse(self.path).query)
        out = {"env_present": {k: bool(v) for k, v in s.env.items() if k != "VERCEL"}, "checks": {}}
        out["oidc_header_present"] = bool(self.headers.get("x-vercel-oidc-token"))
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
                probe = f"selftest/probe-{stamp[:10]}.json"   # fresh path: overwritten blobs can read stale
                store.put_json(probe, {"written_at": stamp})
                out["checks"]["put"] = "ok"
                out["checks"]["list"] = len(store.list("selftest/"))
                got = store.get_json(probe)
                if got and got.get("written_at") != stamp:
                    # same-day re-run hits an overwritten path – a stale read here is expected CDN behaviour
                    probe = f"selftest/probe-{stamp}.json".replace(":", "")
                    store.put_json(probe, {"written_at": stamp})
                    got = store.get_json(probe)
                out["checks"]["get"] = "ok" if got and got.get("written_at") == stamp else f"unexpected: {got}"
                out["checks"]["runs_indexed"] = len(storage.recent_runs(10_000))
                ok = out["checks"]["get"] == "ok"
        except Exception as exc:
            out["error"] = f"{type(exc).__name__}: {exc}"
            ok = False

        if q.get("brand") == ["1"]:
            try:
                out["brand"] = brand_scan()
            except Exception as exc:
                out["brand"] = {"error": f"{type(exc).__name__}: {exc}"}

        if q.get("blobdiag") == ["1"]:
            out["blob_diag"] = blob_diag(s)

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
