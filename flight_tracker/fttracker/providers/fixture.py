"""Offline provider that replays a stored Ignav-shaped JSON file.

For testing the pipeline only. Every itinerary it returns is marked as fixture
data and the report says so loudly, so it can never be mistaken for a real fare.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from ..models import ProviderResult
from .base import FareProvider
from .ignav import parse_response


class FixtureProvider(FareProvider):
    name = "fixture"

    def __init__(self, settings, save_raw, path: Path):
        super().__init__(settings, save_raw)
        self.path = path

    def search(self, pairs: list[tuple[dt.date, dt.date]]) -> ProviderResult:
        res = ProviderResult(provider=self.name, ok=True)
        payload = json.loads(self.path.read_text())
        for out_date, ret_date in pairs:
            # the fixture keys responses by "YYYY-MM-DD_YYYY-MM-DD"; missing pairs = no results
            key = f"{out_date}_{ret_date}"
            if key not in payload:
                continue
            its, problems = parse_response(payload[key], out_date, ret_date, self.settings.trip.currency)
            for it in its:
                it.provider = "fixture"
            res.itineraries += its
            res.errors += problems
            res.calls += 1
        return res
