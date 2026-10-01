"""Provider-neutral itinerary model. Every provider normalises into these."""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Segment:
    origin: str
    destination: str
    carrier: str                    # marketing carrier IATA code, e.g. "QF"
    operating_carrier: str | None = None
    flight_number: str | None = None
    departure: str | None = None    # ISO local time as given by the provider
    arrival: str | None = None
    duration_min: int | None = None


@dataclass
class Leg:
    """One direction of the trip (outbound or return)."""
    segments: list[Segment]
    duration_min: int                # total door-to-door incl. layovers, from the provider
    layovers_min: list[int] = field(default_factory=list)

    @property
    def stops(self) -> int:
        return max(0, len(self.segments) - 1)

    @property
    def hours(self) -> float:
        return self.duration_min / 60

    @property
    def longest_layover_min(self) -> int:
        return max(self.layovers_min, default=0)

    @property
    def airports(self) -> list[str]:
        if not self.segments:
            return []
        return [self.segments[0].origin] + [s.destination for s in self.segments]

    @property
    def carriers(self) -> list[str]:
        out: list[str] = []
        for s in self.segments:
            if s.carrier and s.carrier not in out:
                out.append(s.carrier)
        return out


@dataclass
class Itinerary:
    provider: str
    outbound_date: dt.date
    return_date: dt.date
    price: float                     # total round-trip price, 1 adult, in `currency`
    currency: str
    outbound: Leg
    inbound: Leg
    single_ticket: bool
    booking_link: str | None = None
    # Filled in by classify/scoring:
    route: str = ""
    value_score: float = 0.0
    too_long: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def carriers(self) -> list[str]:
        out: list[str] = []
        for c in self.outbound.carriers + self.inbound.carriers:
            if c not in out:
                out.append(c)
        return out

    @property
    def longest_layover_min(self) -> int:
        return max(self.outbound.longest_layover_min, self.inbound.longest_layover_min)

    @property
    def is_primary_dates(self) -> bool:
        return "primary" in self.notes

    def key(self) -> str:
        """Identity used to de-duplicate the same fare seen twice."""
        segs = "|".join(
            f"{s.carrier}{s.flight_number or ''}{s.origin}{s.destination}"
            for s in self.outbound.segments + self.inbound.segments
        )
        # ticketing is part of identity: the same flights sold as one ticket and as a
        # self-transfer combo are different products and must both survive de-duplication
        return f"{self.outbound_date}:{self.return_date}:{int(self.single_ticket)}:{segs}"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["outbound_date"] = self.outbound_date.isoformat()
        d["return_date"] = self.return_date.isoformat()
        return d


@dataclass
class OneWay:
    """A one-way fare (used by the Qantas SYD <-> JNB section)."""
    provider: str
    date: dt.date
    price: float
    currency: str
    leg: Leg
    single_ticket: bool = True
    booking_link: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class ProviderResult:
    provider: str
    ok: bool
    itineraries: list[Itinerary] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    calls: int = 0
    raw_files: list[str] = field(default_factory=list)
    skipped: bool = False            # not configured (e.g. no key) – not a failure
    extras: dict[str, Any] = field(default_factory=dict)   # e.g. Google price insights, API usage
