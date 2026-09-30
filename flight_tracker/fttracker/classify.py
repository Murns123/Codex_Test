"""Route classification A–E.

A = Qantas via PER to JNB + ELS connection
B = Qantas via SYD to JNB + ELS connection
C = SAA via PER
D = Gulf/Asia carrier (EK, QR, EY, SQ) via its hub to JNB/DUR/CPT + ELS
E = anything requiring self-transfer / separate tickets
X = single ticket but none of the above (shown, never force-fitted)
"""
from __future__ import annotations

from .models import Itinerary, Leg

AU_AIRPORTS = {"MEL", "PER", "SYD", "BNE", "ADL", "CBR", "OOL", "CNS", "DRW", "HBA", "AVV"}
SA_GATEWAYS = {"JNB", "DUR", "CPT"}
GULF_ASIA = {"EK", "QR", "EY", "SQ"}
GULF_ASIA_HUBS = {"DXB", "DOH", "AUH", "SIN"}


def _longhaul_index(leg: Leg, outbound: bool) -> int | None:
    """Index of the segment that leaves (outbound) or enters (return) Australia."""
    for i, s in enumerate(leg.segments):
        if outbound and s.origin in AU_AIRPORTS and s.destination not in AU_AIRPORTS:
            return i
        if not outbound and s.origin not in AU_AIRPORTS and s.destination in AU_AIRPORTS:
            return i
    return None


def classify_leg(leg: Leg, outbound: bool) -> str:
    idx = _longhaul_index(leg, outbound)
    if idx is None:
        return "X"
    seg = leg.segments[idx]
    carriers = {seg.carrier, seg.operating_carrier} - {None, ""}
    au_port = seg.origin if outbound else seg.destination
    airports = set(leg.airports)

    if "QF" in carriers and "JNB" in airports:
        if au_port == "PER":
            return "A"
        if au_port == "SYD":
            return "B"
    if "SA" in carriers and au_port == "PER":
        return "C"
    if carriers & GULF_ASIA and airports & GULF_ASIA_HUBS and airports & SA_GATEWAYS:
        return "D"
    return "X"


def classify(it: Itinerary) -> str:
    if not it.single_ticket:
        return "E"
    out = classify_leg(it.outbound, outbound=True)
    ret = classify_leg(it.inbound, outbound=False)
    return out if out == ret else f"{out}/{ret}"


ROUTE_LABELS = {
    "A": "Qantas via PER",
    "B": "Qantas via SYD",
    "C": "SAA via PER",
    "D": "Gulf/Asia hub",
    "E": "Self-transfer",
    "X": "Other",
}


def route_label(code: str) -> str:
    return " / ".join(ROUTE_LABELS.get(c, c) for c in code.split("/"))
