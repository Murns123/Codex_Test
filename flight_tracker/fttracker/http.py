"""HTTP with retries and exponential backoff."""
from __future__ import annotations

import logging
import time
from typing import Any, Callable

import requests

log = logging.getLogger(__name__)


class HttpError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def request_json(
    method: str,
    url: str,
    *,
    retries: int = 3,
    backoff_base_s: float = 2,
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504),
    timeout_s: float = 60,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] = time.sleep,
    **kwargs: Any,
) -> Any:
    """Return parsed JSON, retrying transient failures. Raises HttpError when out of attempts.

    Only network errors and the configured status codes are retried; a 400/401/403
    fails immediately because retrying will not fix a bad request or a bad key.
    """
    http = session or requests
    last_err = ""
    last_status: int | None = None
    for attempt in range(retries + 1):
        try:
            resp = http.request(method, url, timeout=timeout_s, **kwargs)
            if resp.status_code in retry_on_status:
                last_status = resp.status_code
                last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
            elif resp.status_code >= 400:
                raise HttpError(f"HTTP {resp.status_code}: {resp.text[:300]}", resp.status_code)
            else:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise HttpError(f"Response was not JSON: {resp.text[:300]}") from exc
        except requests.RequestException as exc:
            last_err = f"{type(exc).__name__}: {exc}"
        if attempt < retries:
            wait = backoff_base_s * (2 ** attempt)
            log.warning("%s %s failed (%s); retry %d/%d in %.0fs",
                        method, url, last_err, attempt + 1, retries, wait)
            sleep(wait)
    raise HttpError(f"gave up after {retries + 1} attempts – {last_err}", last_status)
