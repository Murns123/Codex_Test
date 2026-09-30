"""Dashboard – GET / (rewritten to /api/index)."""
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fttracker.web import send, settings

from fttracker.report import to_html
from fttracker.runner import open_storage


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            storage = open_storage(settings())
        except Exception as exc:
            send(self, 500, f"<h1>Database not reachable</h1><p>{exc}</p><p>Set DATABASE_URL.</p>")
            return
        try:
            html = to_html(storage.latest_report(), storage.recent_runs(30), storage.log_lines(60))
        finally:
            storage.close()
        send(self, 200, html)
