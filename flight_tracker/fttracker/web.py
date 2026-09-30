"""Shared helpers for the Vercel Python functions."""
from __future__ import annotations

import hmac
import json
import logging
import os
from typing import Any

from .config import load_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def settings():
    return load_settings()


def authorised(headers: Any) -> bool:
    secret = os.environ.get("CRON_SECRET", "")
    got = headers.get("Authorization") or headers.get("authorization") or ""
    return bool(secret) and hmac.compare_digest(got, f"Bearer {secret}")


def send(handler, status: int, body: str | dict | list, content_type: str | None = None) -> None:
    if not isinstance(body, str):
        body = json.dumps(body, default=str, indent=2)
        content_type = content_type or "application/json"
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", (content_type or "text/html") + "; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)
