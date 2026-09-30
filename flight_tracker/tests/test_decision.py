import datetime as dt

from fttracker.config import DecisionConfig
from fttracker.decision import Point, apply_jev, decide, rising_streak

CFG = DecisionConfig()
D = dt.date(2026, 10, 1)


def pts(*values, start=dt.date(2026, 9, 20)):
    return [Point(start + dt.timedelta(days=i), v, v) for i, v in enumerate(values)]


def cur(v, price=None, day=D):
    return Point(day, v, price if price is not None else v)


def test_day1_sets_baseline_and_holds():
    d = decide(D, cur(3500), [], CFG)
    assert (d.decision, d.rule, d.day) == ("HOLD", "baseline", 1)
    assert d.baseline == 3500


def test_day1_under_3000_is_buy():
    assert decide(D, cur(2990), [], CFG).decision == "BUY"


def test_under_price_uses_price_not_value():
    d = decide(D, cur(3200, price=2950), pts(3200), CFG)
    assert (d.decision, d.rule) == ("BUY", "under_price")


def test_exactly_3000_is_not_under():
    assert decide(D, cur(3000), pts(3000), CFG).rule != "under_price"


def test_5pct_below_baseline_buys():
    d = decide(D, cur(3800), pts(4000, 3850), CFG)   # -5.0% vs baseline
    assert (d.decision, d.rule) == ("BUY", "below_baseline")


def test_4_9pct_below_baseline_holds():
    d = decide(D, cur(3804), pts(4000, 3850), CFG)   # -4.9%
    assert d.decision == "HOLD"


def test_rising_two_in_a_row_buys():
    d = decide(D, cur(3700), pts(3500, 3550, 3600), CFG)
    assert (d.decision, d.rule) == ("BUY", "rising")
    assert d.rising_streak == 3


def test_one_rise_is_not_enough():
    d = decide(D, cur(3520), pts(3600, 3550, 3500), CFG)
    assert d.rising_streak == 1 and d.decision == "HOLD"


def test_small_move_holds():
    d = decide(D, cur(3550), pts(3600, 3600), CFG)   # -1.4%
    assert (d.decision, d.rule) == ("HOLD", "small_move")


def test_big_drop_not_at_baseline_threshold_holds_with_reason():
    d = decide(D, cur(3800), pts(3900, 3950), CFG)   # -3.8% vs prev, -2.6% vs baseline
    assert (d.decision, d.rule) == ("HOLD", "no_trigger")


def test_book_by_forces_buy():
    d = decide(dt.date(2026, 10, 14), cur(3600), pts(3500, 3600), CFG)
    assert (d.decision, d.rule) == ("BUY", "book_by")


def test_hard_stop_day_is_final_buy():
    d = decide(dt.date(2026, 10, 31), cur(3600), pts(3500), CFG)
    assert d.decision == "BUY" and "hard stop" in d.reason


def test_after_hard_stop_is_stop():
    assert decide(dt.date(2026, 11, 1), cur(3600), pts(3500), CFG).decision == "STOP"


def test_no_data_holds_and_never_invents():
    d = decide(D, None, pts(3500), CFG)
    assert (d.decision, d.rule) == ("HOLD", "no_data")
    assert d.vs_previous_pct is None


def test_rising_streak_helper():
    assert rising_streak([1, 2, 3]) == 2
    assert rising_streak([3, 2, 3]) == 1
    assert rising_streak([3, 3]) == 0
    assert rising_streak([5]) == 0


def test_configurable_thresholds():
    cfg = DecisionConfig(buy_below_baseline_pct=10, buy_under_price=2500, hold_movement_pct=5)
    d = decide(D, cur(3800), pts(4000, 3850), cfg)   # -5% baseline no longer enough
    assert d.decision == "HOLD" and d.rule == "small_move"


def test_jev_upgrades_hold_when_confident():
    d = decide(D, cur(3550), pts(3600, 3600), CFG)
    d = apply_jev(d, 0.85, 0.80)
    assert (d.decision, d.rule) == ("BUY", "jev_upgrade")
    assert d.notes


def test_jev_below_threshold_leaves_hold():
    d = apply_jev(decide(D, cur(3550), pts(3600, 3600), CFG), 0.79, 0.80)
    assert d.decision == "HOLD"


def test_jev_never_downgrades_buy():
    d = apply_jev(decide(D, cur(2900), pts(3600, 3600), CFG), 0.0, 0.80)
    assert d.decision == "BUY"


def test_jev_needs_min_days_and_data():
    assert apply_jev(decide(D, cur(3550), pts(3600), CFG), 0.99, 0.80).decision == "HOLD"   # day 2
    assert apply_jev(decide(D, None, pts(3600, 3600), CFG), 0.99, 0.80).decision == "HOLD"


def test_jev_advisory_only_when_threshold_none():
    assert apply_jev(decide(D, cur(3550), pts(3600, 3600), CFG), 0.99, None).decision == "HOLD"
