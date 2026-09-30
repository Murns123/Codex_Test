"""Scheduled run. Vercel Cron calls GET /api/cron with Authorization: Bearer $CRON_SECRET."""
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fttracker.web import authorised, send, settings

from fttracker.runner import run


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not authorised(self.headers):
            send(self, 401, {"ok": False, "error": "unauthorised"})
            return
        try:
            report = run(settings())
        except Exception as exc:  # surface the failure in Vercel logs and to the caller
            import logging
            logging.exception("run failed")
            send(self, 500, {"ok": False, "error": str(exc)})
            return
        send(self, 200, {"ok": report.get("status") != "failed", "status": report.get("status"),
                         "summary": report.get("summary_line") or report["decision"]["reason"]})
