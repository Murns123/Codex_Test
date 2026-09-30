"""GET /api/log – the one-line-per-run log as markdown."""
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fttracker.web import send, settings

from fttracker.runner import open_storage


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        storage = open_storage(settings(self.headers))
        try:
            lines = storage.log_lines(1000)
        finally:
            storage.close()
        body = "# MEL → ELS flight tracker – run log\n\n" + "".join(f"- {l}\n" for l in lines)
        send(self, 200, body, "text/markdown")
