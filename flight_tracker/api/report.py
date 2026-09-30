"""GET /api/report – latest run as JSON."""
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fttracker.web import send, settings

from fttracker.runner import open_storage


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        storage = open_storage(settings())
        try:
            report = storage.latest_report()
        finally:
            storage.close()
        send(self, 200 if report else 404, report or {"error": "no runs yet"})
