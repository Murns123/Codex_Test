"""Ignav fare search – round-trip endpoint.

Docs: https://ignav.com/docs/round-trip  (POST {base_url}/fares/round-trip, header X-Api-Key)

The parser is deliberately tolerant about field names: it accepts the common
variants for each value (e.g. `price` as a number or as {"amount", "currency"}).
Anything it cannot read with confidence – a missing price or a leg with no
duration – is dropped and reported, never guessed. Run
`python tracker.py probe` once with a real key and check the stored raw JSON
against this parser before relying on it (see README).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..http import HttpError, request_json
from ..models import Itinerary, Leg, OneWay, ProviderResult, Segment
from .base import FareProvider

log = logging.getLogger(__name__)

CABIN = {"economy": "economy", "premium_economy": "premium_economy",
         "business": "business", "first": "first"}


def _first(d: Any, *keys: str, default: Any = None) -> Any:
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _code(v: Any) -> str:
    """Airport / airline code from a string or a nested object."""
    if isinstance(v, dict):
        v = _first(v, "iata", "code", "id", "iata_code")
    return str(v or "").strip().upper()


def _minutes(v: Any) -> int | None:
    """Accept 1234, "1234", "PT20H35M", or {"minutes": ...}."""
    if v is None:
        return None
    if isinstance(v, dict):
        return _minutes(_first(v, "minutes", "total_minutes"))
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip()
    if s.isdigit():
        return int(s)
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:\d+S)?", s)
    if m and any(m.groups()):
        d, h, mi = (int(x or 0) for x in m.groups())
        return d * 1440 + h * 60 + mi
    return None


def _iso_diff_minutes(start: str | None, end: str | None) -> int | None:
    """Duration from two ISO timestamps – only when both carry a UTC offset."""
    try:
        a, b = dt.datetime.fromisoformat(str(start)), dt.datetime.fromisoformat(str(end))
    except (TypeError, ValueError):
        return None
    if a.tzinfo is None or b.tzinfo is None:
        return None  # local times in different zones – cannot compute honestly
    return int((b - a).total_seconds() // 60)


def _local_diff_minutes(start: str | None, end: str | None) -> int | None:
    try:
        a, b = dt.datetime.fromisoformat(str(start)), dt.datetime.fromisoformat(str(end))
    except (TypeError, ValueError):
        return None
    if (a.tzinfo is None) != (b.tzinfo is None):
        return None
    mins = int((b - a).total_seconds() // 60)
    return mins if mins >= 0 else None


def _parse_segment(s: dict[str, Any]) -> Segment:
    carrier = _code(_first(s, "marketing_carrier_code", "marketing_carrier", "carrier", "airline", "marketing_airline",
                           "airline_code", "carrier_code"))
    fn = _first(s, "flight_number", "number", "flight")
    fn = str(fn) if fn is not None else None
    if not carrier and fn:
        m = re.match(r"^([A-Z0-9]{2})\s*\d", fn.upper())
        carrier = m.group(1) if m else ""
    return Segment(
        origin=_code(_first(s, "origin", "from", "departure_airport", "departure", "origin_airport")),
        destination=_code(_first(s, "destination", "to", "arrival_airport", "arrival",
                                 "destination_airport")),
        carrier=carrier,
        operating_carrier=_code(_first(s, "operating_carrier_code", "operating_carrier", "operating_airline")) or None,
        flight_number=fn,
        departure=_first(s, "departure_time_local", "departure_time", "departure_at", "departs_at",
                         "departure_datetime"),
        arrival=_first(s, "arrival_time_local", "arrival_time", "arrival_at", "arrives_at", "arrival_datetime"),
        duration_min=_minutes(_first(s, "duration_minutes", "duration")),
    )


def _parse_leg(leg: dict[str, Any]) -> Leg | None:
    segs_raw = _first(leg, "segments", "flights") or []
    segments = [_parse_segment(s) for s in segs_raw if isinstance(s, dict)]
    if not segments:
        return None
    duration = _minutes(_first(leg, "duration_minutes", "total_duration", "duration"))
    if duration is None:
        duration = _iso_diff_minutes(segments[0].departure, segments[-1].arrival)
    if duration is None:
        return None
    layovers = [
        m for m in (_minutes(_first(l, "duration_minutes", "duration"))
                    for l in (_first(leg, "layovers", "connections") or []))
        if m is not None
    ]
    if not layovers and len(segments) > 1:
        for a, b in zip(segments, segments[1:]):
            gap = _iso_diff_minutes(a.arrival, b.departure)
            if gap is None and a.destination == b.origin:
                # both times are local to the same connecting airport, so they are comparable
                gap = _local_diff_minutes(a.arrival, b.departure)
            if gap is not None:
                layovers.append(gap)
    return Leg(segments=segments, duration_min=duration, layovers_min=layovers)


def _is_self_transfer(it: dict[str, Any]) -> bool:
    for k in ("self_transfer", "is_self_transfer", "separate_tickets", "virtual_interlining",
              "multi_ticket"):
        if it.get(k) is True:
            return True
    tickets = _first(it, "tickets", "ticket_count", "num_tickets")
    if isinstance(tickets, int) and tickets > 1:
        return True
    if isinstance(tickets, list) and len(tickets) > 1:
        return True
    if it.get("single_ticket") is False:
        return True
    return False


def _items(payload: Any) -> list[Any]:
    items = payload if isinstance(payload, list) else _first(
        payload, "itineraries", "results", "data", "fares", "offers", default=[])
    if isinstance(items, dict):
        items = _first(items, "itineraries", "results", default=[])
    return items or []


def _price(it: dict[str, Any], currency: str, fx: dict[str, Any] | None
           ) -> tuple[float | None, str | None, str | None]:
    """(price in `currency`, conversion note, problem). price None = unusable row.

    Prices quoted in another currency are converted only when `fx` supplies a published
    rate for it ({"rates": {"USD": 1.52}, "date": ..., "source": ...}); otherwise skipped."""
    rates = (fx or {}).get("rates", {})
    price_raw = _first(it, "price", "total_price", "amount", "fare")
    cur = currency
    if isinstance(price_raw, dict):
        cur = str(_first(price_raw, "currency", default=currency)).upper()
        price_raw = _first(price_raw, "amount", "total", "value")
    cur = str(_first(it, "currency", default=cur)).upper()
    try:
        price = float(price_raw)
    except (TypeError, ValueError):
        return None, None, None
    if cur == currency.upper():
        return price, None, None
    if cur not in rates:
        return None, None, f"skipped a fare quoted in {cur} (no {cur}->{currency} rate available)"
    note = f"converted from {cur} {price:,.0f} at {rates[cur]} ({fx.get('source')}, {fx.get('date')})"
    return round(price * float(rates[cur]), 2), note, None


def _dropped_note(n: int) -> list[str]:
    return [f"{n} itinerar{'y' if n == 1 else 'ies'} dropped (missing price, legs or leg duration)"] if n else []


def parse_response(
    payload: Any, out_date: dt.date, ret_date: dt.date, currency: str,
    fx: dict[str, Any] | None = None,
) -> tuple[list[Itinerary], list[str]]:
    """Normalise an Ignav round-trip response. Returns (itineraries, problems)."""
    problems: list[str] = []
    result: list[Itinerary] = []
    dropped = 0
    for it in _items(payload):
        if not isinstance(it, dict):
            continue
        price, note, problem = _price(it, currency, fx)
        if problem:
            problems.append(problem)
            continue
        if price is None:
            dropped += 1
            continue
        legs_raw = _first(it, "legs", "slices", "journeys", "bounds") or []
        if not legs_raw and ("outbound" in it or "inbound" in it or "return" in it):
            legs_raw = [it.get("outbound"), _first(it, "inbound", "return")]
        legs = [_parse_leg(l) for l in legs_raw if isinstance(l, dict)]
        if len(legs) != 2 or any(l is None for l in legs):
            dropped += 1
            continue
        result.append(Itinerary(
            provider="ignav",
            outbound_date=out_date,
            return_date=ret_date,
            price=price,
            currency=currency,
            outbound=legs[0],  # type: ignore[arg-type]
            inbound=legs[1],   # type: ignore[arg-type]
            single_ticket=not _is_self_transfer(it),
            booking_link=_first(it, "booking_url", "booking_link", "deep_link", "url"),
            notes=[note] if note else [],
        ))
    return result, problems + _dropped_note(dropped)


def parse_oneway(payload: Any, date: dt.date, currency: str, fx: dict[str, Any] | None = None
                 ) -> tuple[list[OneWay], list[str]]:
    """Normalise an Ignav one-way response. Returns (options, problems)."""
    problems: list[str] = []
    result: list[OneWay] = []
    dropped = 0
    for it in _items(payload):
        if not isinstance(it, dict):
            continue
        price, note, problem = _price(it, currency, fx)
        if problem:
            problems.append(problem)
            continue
        if price is None:
            dropped += 1
            continue
        raw_leg = _first(it, "outbound", "leg")
        if raw_leg is None:
            legs = _first(it, "legs", "slices", "journeys", "bounds") or []
            raw_leg = legs[0] if legs else (it if "segments" in it else None)
        leg = _parse_leg(raw_leg) if isinstance(raw_leg, dict) else None
        if leg is None:
            dropped += 1
            continue
        result.append(OneWay(provider="ignav", date=date, price=price, currency=currency, leg=leg,
                             single_ticket=not _is_self_transfer(it),
                             booking_link=_first(it, "booking_url", "booking_link", "deep_link", "url"),
                             notes=[note] if note else []))
    return result, problems + _dropped_note(dropped)


class IgnavProvider(FareProvider):
    name = "ignav"

    def is_configured(self) -> tuple[bool, str]:
        if not self.cfg.get("enabled", True):
            return False, "disabled in config.yaml"
        if not self.settings.env.get("IGNAV_API_KEY"):
            return False, "IGNAV_API_KEY is not set"
        return True, ""

    def build_body(self, out_date: dt.date, ret_date: dt.date) -> dict[str, Any]:
        t = self.settings.trip
        body: dict[str, Any] = {
            "origin": t.origin,
            "destination": t.destination,
            "departure_date": out_date.isoformat(),
            "return_date": ret_date.isoformat(),
            "adults": t.adults,
            "cabin_class": CABIN.get(t.cabin, t.cabin),
        }
        # Ignav rejects a currency field (400 invalid_request_body, field "currency");
        # prices come back in USD and are converted at a published rate.
        if self.cfg.get("send_currency"):
            body["currency"] = t.currency
        body.update(self.cfg.get("extra_body") or {})
        return body

    def route_body(self, origin: str, destination: str, departure: dt.date, return_date: dt.date | None = None,
                   airlines: list[str] | None = None) -> dict[str, Any]:
        """Request body for any route; airlines -> Ignav's airlines_include filter."""
        t = self.settings.trip
        body: dict[str, Any] = {"origin": origin, "destination": destination,
                                "departure_date": departure.isoformat(),
                                "adults": t.adults, "cabin_class": CABIN.get(t.cabin, t.cabin)}
        if return_date:
            body["return_date"] = return_date.isoformat()
        if airlines:
            body["airlines_include"] = airlines
        return body

    def post(self, endpoint: str, body: dict[str, Any]) -> Any:
        url = self.cfg.get("base_url", "https://ignav.com/api").rstrip("/") + endpoint
        headers = {"X-Api-Key": self.settings.env["IGNAV_API_KEY"],
                   "Content-Type": "application/json", "Accept": "application/json"}
        return request_json("POST", url, json=body, headers=headers, **self.http_kwargs)

    def _fx(self, payload: Any, res: ProviderResult) -> dict[str, Any] | None:
        """Published FX rates for any non-AUD currency in the payload, fetched once per run."""
        target = self.settings.trip.currency.upper()
        found = set(re.findall(r'"currency":\s*"([A-Za-z]{3})"', json.dumps(payload))) - {target}
        fx = res.extras.setdefault("fx", {"rates": {}, "source": "ECB reference rate via frankfurter.app"})
        for cur in (c.upper() for c in found):
            if cur in fx["rates"] or cur in fx.get("failed", []):
                continue
            url = self.cfg.get("fx_url", "https://api.frankfurter.app/latest")
            try:
                data = request_json("GET", url, params={"from": cur, "to": target},
                                    **{**self.http_kwargs, "timeout_s": 20})
                fx["rates"][cur] = float(data["rates"][target])
                fx["date"] = data.get("date")
            except (HttpError, KeyError, TypeError, ValueError) as exc:
                fx.setdefault("failed", []).append(cur)
                res.errors.append(f"no {cur}->{target} exchange rate ({exc}); {cur} fares left out")
        return fx

    def search(self, pairs: list[tuple[dt.date, dt.date]]) -> ProviderResult:
        res = ProviderResult(provider=self.name, ok=False)
        url = self.cfg.get("base_url", "https://ignav.com/api").rstrip("/") + \
            self.cfg.get("endpoint", "/fares/round-trip")
        headers = {"X-Api-Key": self.settings.env["IGNAV_API_KEY"],
                   "Content-Type": "application/json", "Accept": "application/json"}
        def fetch(pair: tuple[dt.date, dt.date]) -> tuple[dict[str, Any], Any, str | None]:
            body = self.build_body(*pair)
            try:
                return body, request_json("POST", url, json=body, headers=headers, **self.http_kwargs), None
            except HttpError as exc:
                return body, None, str(exc)

        # Calls run in parallel (keeps a run inside the Vercel time limit); results are
        # processed in order on this thread because storage connections aren't thread-safe.
        workers = max(1, int(self.cfg.get("concurrency", 4)))
        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            fetched = list(pool.map(fetch, pairs))
            # Ignav sometimes answers a date pair with an upstream error or an empty list that
            # a second try fills in – retry those once
            redo = [i for i, (_, payload, err) in enumerate(fetched) if err is not None or not _items(payload)]
            # ...but only while there is time left in the run (Vercel stops it at 300s)
            if time.monotonic() - t0 >= float(self.cfg.get("retry_within_s", 110)):
                redo = [i for i in redo if i == 0]      # short on time: still retry the primary pair
            if redo and self.cfg.get("retry_empty", True):
                for i, again in zip(redo, pool.map(fetch, [pairs[i] for i in redo])):
                    res.calls += 1
                    if again[2] is None and (_items(again[1]) or fetched[i][2] is not None):
                        fetched[i] = again

        succeeded = 0
        for (out_date, ret_date), (body, payload, err) in zip(pairs, fetched):
            label = f"ignav_{out_date:%m%d}_{ret_date:%m%d}"
            res.calls += 1
            if err is not None:
                msg = f"{out_date:%-d %b}–{ret_date:%-d %b}: {err}"
                log.error("Ignav %s", msg)
                res.errors.append(msg)
                res.raw_files.append(self.save_raw(label + "_error", {"request": body, "error": err}))
                continue
            res.raw_files.append(self.save_raw(label, {"request": body, "response": payload}))
            its, problems = parse_response(payload, out_date, ret_date, self.settings.trip.currency,
                                           self._fx(payload, res))
            res.errors += [f"{out_date:%-d %b}–{ret_date:%-d %b}: {p}" for p in problems]
            res.itineraries += its
            succeeded += 1
            log.info("Ignav %s–%s: %d itineraries", out_date, ret_date, len(its))
        res.ok = succeeded > 0
        return res
