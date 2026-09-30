"""value_score and the "too long" flag."""
from __future__ import annotations

from .config import ScoringConfig
from .models import Itinerary


def value_score(it: Itinerary, cfg: ScoringConfig) -> float:
    """price + $/h for every hour over the threshold, per direction, summed."""
    penalty = sum(
        cfg.dollars_per_hour * max(0.0, leg.hours - cfg.hours_threshold)
        for leg in (it.outbound, it.inbound)
    )
    return round(it.price + penalty, 2)


def is_over_long(it: Itinerary, cfg: ScoringConfig) -> bool:
    return it.outbound.hours > cfg.too_long_hours or it.inbound.hours > cfg.too_long_hours


def score_all(its: list[Itinerary], cfg: ScoringConfig) -> list[Itinerary]:
    """Set value_score and too_long on every itinerary; return them sorted best-first.

    An itinerary with a direction over `too_long_hours` is flagged unless its price
    is more than `too_long_exempt_saving` below the cheapest non-long option.
    """
    for it in its:
        it.value_score = value_score(it, cfg)
    normal = [it for it in its if not is_over_long(it, cfg)]
    best_normal_price = min((it.price for it in normal), default=None)
    for it in its:
        if not is_over_long(it, cfg):
            it.too_long = False
        elif best_normal_price is None:
            it.too_long = True  # nothing to compare against – keep the warning
        else:
            it.too_long = not (best_normal_price - it.price > cfg.too_long_exempt_saving)
    return sorted(its, key=lambda i: (i.too_long, i.value_score, i.price))


def best_single_ticket(its: list[Itinerary]) -> Itinerary | None:
    """Best single-ticket option: not too long if possible, lowest value_score."""
    single = [it for it in its if it.single_ticket]
    if not single:
        return None
    return min(single, key=lambda i: (i.too_long, i.value_score, i.price))
