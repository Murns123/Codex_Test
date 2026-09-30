"""Google Flights via SerpApi – second fare source alongside Ignav.

Round trips on Google Flights are two-step: the first call lists outbound
options (price = full round-trip price), and each outbound option's
`departure_token` must be sent back to get its matching return flights.
To keep cost down we only expand the cheapest N outbound options
(3 on the primary dates, 1 on each flex pair by default).
Docs: https://serpapi.com/google-flights-api
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..http import HttpError, request_json
from ..models import Itinerary, Leg, ProviderResult, Segment
from .base import FareProvider

log = logging.getLogger(__name__)

TRAVEL_CLASS = {"economy": 1, "premium_economy": 2, "business": 3, "first": 4}
SELF_TRANSFER_HINTS = ("self transfer", "self-transfer", "separate ticket")


def _carrier(flight: dict[str, Any]) -> str:
    m = re.match(r"^\s*([A-Z0-9]{2})\s*\d", str(flight.get("flight_number") or "").upper())
    return m.group(1) if m else str(flight.get("airline") or "").strip()


def parse_leg(option: dict[str, Any]) -> Leg | None:
    flights = option.get("flights") or []
    if not flights or option.get("total_duration") is None:
        return None
    segments = [
        Segment(
            origin=str(f.get("departure_airport", {}).get("id", "")).upper(),
            destination=str(f.get("arrival_airport", {}).get("id", "")).upper(),
            carrier=_carrier(f),
            flight_number=f.get("flight_number"),
            departure=f.get("departure_airport", {}).get("time"),
            arrival=f.get("arrival_airport", {}).get("time"),
            duration_min=f.get("duration"),
        )
        for f in flights
    ]
    layovers = [int(l["duration"]) for l in option.get("layovers") or [] if l.get("duration") is not None]
    return Leg(segments=segments, duration_min=int(option["total_duration"]), layovers_min=layovers)


def is_self_transfer(option: dict[str, Any]) -> bool:
    blob = json.dumps(option).lower()
    return any(h in blob for h in SELF_TRANSFER_HINTS)


def options(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return list(payload.get("best_flights") or []) + list(payload.get("other_flights") or [])


class SerpApiProvider(FareProvider):
    name = "serpapi"

    def is_configured(self) -> tuple[bool, str]:
        if not self.cfg.get("enabled", True):
            return False, "disabled in config.yaml"
        if not self.settings.env.get("SERPAPI_KEY"):
            return False, "SERPAPI_KEY is not set"
        return True, ""

    def _params(self, out_date: dt.date, ret_date: dt.date) -> dict[str, Any]:
        t = self.settings.trip
        return {
            "engine": "google_flights",
            "departure_id": t.origin,
            "arrival_id": t.destination,
            "outbound_date": out_date.isoformat(),
            "return_date": ret_date.isoformat(),
            "type": 1,
            "adults": t.adults,
            "travel_class": TRAVEL_CLASS.get(t.cabin, 1),
            "currency": t.currency,
            "hl": "en",
            "gl": "au",
        }

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        url = self.cfg.get("base_url", "https://serpapi.com/search.json")
        payload = request_json("GET", url, params={**params, "api_key": self.settings.env["SERPAPI_KEY"]},
                               **self.http_kwargs)
        if isinstance(payload, dict) and payload.get("error"):
            raise HttpError(f"SerpApi error: {payload['error']}")
        return payload

    def account(self) -> dict[str, Any] | None:
        """Remaining searches on the SerpApi plan (this endpoint is free)."""
        try:
            a = request_json("GET", "https://serpapi.com/account.json",
                             params={"api_key": self.settings.env["SERPAPI_KEY"]}, **{**self.http_kwargs, "retries": 0})
        except HttpError:
            return None
        keys = ("plan_name", "searches_per_month", "plan_searches_left", "total_searches_left", "this_month_usage")
        return {k: a.get(k) for k in keys if k in a}

    def _search_pair(self, pair: tuple[dt.date, dt.date], top_n: int) -> dict[str, Any]:
        """All HTTP for one date pair. Runs in a worker thread, so it only returns data;
        storing raw JSON and building itineraries happens on the main thread."""
        out_date, ret_date = pair
        params = self._params(out_date, ret_date)
        result: dict[str, Any] = {"params": params, "first": None, "error": None, "returns": []}
        try:
            result["first"] = self._get(params)
        except HttpError as exc:
            result["error"] = str(exc)
            return result
        outs = sorted((o for o in options(result["first"]) if o.get("price") is not None and o.get("departure_token")),
                      key=lambda o: o["price"])[:top_n]
        for out_opt in outs:
            try:
                second = self._get({**params, "departure_token": out_opt["departure_token"]})
                result["returns"].append((out_opt, second, None))
            except HttpError as exc:
                result["returns"].append((out_opt, None, str(exc)))
        return result

    def search(self, pairs: list[tuple[dt.date, dt.date]]) -> ProviderResult:
        res = ProviderResult(provider=self.name, ok=False)
        if self.cfg.get("primary_dates_only", False):
            pairs = pairs[:1]
        primary = pairs[0] if pairs else None
        top_primary = int(self.cfg.get("return_legs_primary", 3))
        top_flex = int(self.cfg.get("return_legs_flex", 1))

        # Budget guard: never run the plan dry – skip Google (and say so) below the reserve.
        usage = self.account()
        if usage:
            res.extras["account"] = usage
            left = usage.get("total_searches_left", usage.get("plan_searches_left"))
            needed = sum(1 + (top_primary if p == primary else top_flex) for p in pairs)
            reserve = int(self.cfg.get("reserve_searches", 10))
            if isinstance(left, int) and left - needed < reserve:
                res.skipped = True
                res.errors.append(f"skipped to protect the SerpApi allowance: {left} searches left, this run "
                                  f"needs {needed}, reserve {reserve}")
                return res
        workers = max(1, int(self.cfg.get("concurrency", 4)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            fetched = list(pool.map(lambda p: self._search_pair(p, top_primary if p == primary else top_flex), pairs))

        succeeded = 0
        for (out_date, ret_date), r in zip(pairs, fetched):
            label = f"serpapi_{out_date:%m%d}_{ret_date:%m%d}"
            res.calls += 1 + len(r["returns"])
            if r["error"]:
                res.errors.append(f"{out_date:%d %b}–{ret_date:%d %b}: {r['error']}")
                res.raw_files.append(self.save_raw(label + "_error", {"request": r["params"], "error": r["error"]}))
                continue
            first = r["first"]
            res.raw_files.append(self.save_raw(label + "_outbound", {"request": r["params"], "response": first}))
            succeeded += 1
            if (out_date, ret_date) == primary and first.get("price_insights"):
                res.extras["price_insights"] = first["price_insights"]
            if not options(first):
                res.errors.append(f"{out_date:%d %b}–{ret_date:%d %b}: Google returned no flights")
            for i, (out_opt, second, err) in enumerate(r["returns"], 1):
                if err:
                    res.errors.append(f"{out_date:%d %b}–{ret_date:%d %b} return legs: {err}")
                    continue
                res.raw_files.append(self.save_raw(f"{label}_return{i}", {"request": r["params"], "response": second}))
                out_leg = parse_leg(out_opt)
                if out_leg is None:
                    continue
                link = (second.get("search_metadata") or {}).get("google_flights_url") or \
                    (first.get("search_metadata") or {}).get("google_flights_url")
                for ret_opt in options(second):
                    ret_leg = parse_leg(ret_opt)
                    if ret_leg is None or ret_opt.get("price") is None:
                        continue
                    res.itineraries.append(Itinerary(
                        provider=self.name,
                        outbound_date=out_date,
                        return_date=ret_date,
                        price=float(ret_opt["price"]),
                        currency=self.settings.trip.currency,
                        outbound=out_leg,
                        inbound=ret_leg,
                        single_ticket=not (is_self_transfer(out_opt) or is_self_transfer(ret_opt)),
                        booking_link=link,
                    ))
        res.ok = succeeded > 0
        return res
