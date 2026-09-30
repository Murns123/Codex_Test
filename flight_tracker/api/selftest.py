"""GET /api/selftest – checks configuration and does a put/list/get round trip on storage.

Touches only selftest/probe.json. Shows which settings are present (never their values).
"""
import datetime as dt
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fttracker.web import send, settings

from fttracker.runner import open_storage


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        s = settings()
        out = {"env_present": {k: bool(v) for k, v in s.env.items() if k != "VERCEL"}, "checks": {}}
        try:
            storage = open_storage(s)
            out["storage"] = type(storage).__name__
            store = getattr(storage, "store", None)
            if store is None:
                out["checks"]["blob"] = "not configured – connect a Blob store to the project"
            else:
                stamp = dt.datetime.now(dt.timezone.utc).isoformat()
                store.put_json("selftest/probe.json", {"written_at": stamp})
                out["checks"]["put"] = "ok"
                out["checks"]["list"] = store.list("selftest/")
                got = store.get_json("selftest/probe.json")
                out["checks"]["get"] = "ok" if got and got.get("written_at") == stamp else f"unexpected: {got}"
                out["checks"]["runs_indexed"] = len(storage.recent_runs(10_000))
            ok = all(v == "ok" for k, v in out["checks"].items() if k in ("put", "get"))
        except Exception as exc:
            out["error"] = f"{type(exc).__name__}: {exc}"
            ok = False
        out["ok"] = ok
        send(self, 200 if ok else 500, out)
