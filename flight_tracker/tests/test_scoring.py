from conftest import itin

from fttracker.config import ScoringConfig
from fttracker.scoring import best_single_ticket, score_all, value_score

CFG = ScoringConfig(dollars_per_hour=50, hours_threshold=22, too_long_hours=30, too_long_exempt_saving=500)


def test_no_penalty_under_threshold():
    assert value_score(itin(3000, 20, 22), CFG) == 3000


def test_penalty_per_direction_summed():
    # 25h out = 3h over, 24h back = 2h over -> 5h * 50 = 250
    assert value_score(itin(3000, 25, 24), CFG) == 3250


def test_penalty_uses_fractional_hours():
    assert value_score(itin(3000, 22.5, 20), CFG) == 3025


def test_custom_rate_and_threshold():
    cfg = ScoringConfig(dollars_per_hour=80, hours_threshold=20, too_long_hours=30, too_long_exempt_saving=500)
    assert value_score(itin(3000, 21, 21), cfg) == 3160


def test_too_long_flagged_when_saving_small():
    normal = itin(3400, 24, 24)
    long_ = itin(3000, 31, 20)          # only 400 cheaper
    score_all([normal, long_], CFG)
    assert long_.too_long and not normal.too_long


def test_too_long_exempt_when_saves_over_500():
    normal = itin(3600, 24, 24)
    long_ = itin(3000, 20, 32)          # 600 cheaper
    score_all([normal, long_], CFG)
    assert not long_.too_long


def test_exactly_500_saving_still_flagged():
    normal = itin(3500, 24, 24)
    long_ = itin(3000, 31, 20)
    score_all([normal, long_], CFG)
    assert long_.too_long


def test_all_long_are_flagged():
    a, b = itin(3000, 31, 20), itin(3100, 20, 35)
    score_all([a, b], CFG)
    assert a.too_long and b.too_long


def test_best_single_ticket_ignores_self_transfer_and_prefers_unflagged():
    cheap_self = itin(2000, single=False)
    long_ = itin(3000, 31, 20)
    good = itin(3300, 23, 23)
    ranked = score_all([cheap_self, long_, good], CFG)
    assert best_single_ticket(ranked) is good


def test_best_single_ticket_none_when_only_self_transfer():
    assert best_single_ticket(score_all([itin(2000, single=False)], CFG)) is None
