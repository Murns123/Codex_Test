"""Provider interface. Add a new data source by subclassing FareProvider."""
from __future__ import annotations

import datetime as dt
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable

from ..config import Settings
from ..models import ProviderResult

# save_raw(label, payload) -> path of the stored JSON file
RawSaver = Callable[[str, Any], str]

log = logging.getLogger(__name__)


class FareProvider(ABC):
    name: str = "base"

    def __init__(self, settings: Settings, save_raw: RawSaver):
        self.settings = settings
        self.cfg: dict[str, Any] = settings.providers.get(self.name, {})
        self.save_raw = save_raw
        self.http_kwargs = {
            "retries": int(settings.http.get("retries", 3)),
            "backoff_base_s": float(settings.http.get("backoff_base_s", 2)),
            "retry_on_status": tuple(settings.http.get("retry_on_status", (429, 500, 502, 503, 504))),
            "timeout_s": float(self.cfg.get("timeout_s", 60)),
        }

    def is_configured(self) -> tuple[bool, str]:
        """(usable, reason_if_not). Unconfigured providers are skipped, not failed."""
        return True, ""

    @abstractmethod
    def search(self, pairs: list[tuple[dt.date, dt.date]]) -> ProviderResult:
        """Search every date pair. Must never raise: put failures in ProviderResult.errors."""
