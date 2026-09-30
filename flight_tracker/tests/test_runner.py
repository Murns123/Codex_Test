"""End-to-end over the fixture provider and a temp SQLite DB – no network."""
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

from fttracker.report import headline, to_html, to_text
from fttracker.runner import open_storage, run

FIX = Path(__file__).parent / "fixtures" / "ignav_sample.json"
MEL = ZoneInfo("Australia/Melbourne")


def at(day, hour=17):
    return dt.datetime(2026, 10, day, hour, 0, tzinfo=MEL)


def test_first_run_sets_baseline(settings):
    r = run(settings, now=at(1), fixtures=FIX)
    assert r["day"] == 1 and r["decision"]["rule"] == "baseline"
    # best is tracked on the primary dates (21 Dec / 8 Jan):
    #   QF 3420: 22.5h out, 23.7h back -> 3420 + 25 + 83 = 3528   <- best
    #   EK 3150: 27.2h out, 26.1h back -> 3150 + 258 + 204 = 3612
    #   2700 self-transfer on the same QF flights must not knock out the 3420 single ticket
    assert r["best"]["price_aud"] == 3420 and r["best"]["route"] == "A"
    assert [o["price_aud"] for o in r["top3"]] == [3420, 3150, 2700]
    assert [o["single_ticket"] for o in r["top3"]] == [True, True, False]
    assert r["flex_searched"] is True
    assert r["flex_saving"]["dates"] == "20 Dec–08 Jan" and r["flex_saving"]["price_saving"] == 130
    assert r["status"] == "fixture" and r["fixture_data"]
    assert "FIXTURE" in r["summary_line"]
    assert headline(r) == "Flight analysis – MEL to ELS | Day 1 – HOLD"
    assert settings.paths["daily_log"].read_text().count("\n- ") == 1


def test_three_runs_a_day_use_daily_closes(settings):
    run(settings, now=at(1, 7), fixtures=FIX)
    run(settings, now=at(1, 12), fixtures=FIX)
    r = run(settings, now=at(2, 7), fixtures=FIX)
    assert r["day"] == 2
    assert r["trend"]["previous"]["date"] == "2026-10-01"
    assert r["trend"]["vs_previous_pct"] == 0.0
    assert r["decision"]["rule"] == "small_move"


def test_dry_run_saves_nothing(settings):
    run(settings, now=at(1), fixtures=FIX, dry_run=True)
    s = open_storage(settings)
    assert s.latest_report() is None
    s.close()
    assert not settings.paths["daily_log"].exists()


def test_no_providers_configured_reports_failure_without_fares(settings):
    r = run(settings, now=at(1))
    assert r["status"] == "failed"
    assert r["best"] is None and r["top3"] == []
    assert r["decision"]["rule"] == "no_data"
    assert [p["provider"] for p in r["providers"]] == ["ignav", "serpapi"]
    assert all(p["skipped"] for p in r["providers"])
    assert "IGNAV_API_KEY" in " ".join(r["providers"][0]["errors"])
    text = to_text(r)
    assert "nothing is shown rather than guessing" in text


def test_after_hard_stop_makes_no_calls(settings):
    r = run(settings, now=dt.datetime(2026, 11, 1, 17, tzinfo=MEL), fixtures=FIX)
    assert r["status"] == "stopped" and r["decision"]["decision"] == "STOP"


def test_book_by_date_says_buy(settings):
    r = run(settings, now=at(14), fixtures=FIX)
    assert r["decision"]["decision"] == "BUY" and r["decision"]["rule"] == "book_by"


def test_html_renders(settings):
    run(settings, now=at(1), fixtures=FIX)
    s = open_storage(settings)
    page = to_html(s.latest_report(), s.recent_runs(), s.log_lines())
    s.close()
    assert "FIXTURE DATA" in page and "Top 3 options" in page and "<table>" in page
    assert to_html(None).count("No runs yet") == 1


def test_flex_dates_only_on_evening_run_and_carried_forward(settings):
    morning = run(settings, now=at(1, 7), fixtures=FIX)
    assert morning["flex_searched"] is False and morning["flex_saving"] is None
    evening = run(settings, now=at(1, 17), fixtures=FIX)
    assert evening["flex_searched"] is True and evening["flex_saving"]
    next_morning = run(settings, now=at(2, 7), fixtures=FIX)
    assert next_morning["flex_searched"] is False
    assert next_morning["flex_saving"] == evening["flex_saving"]
    assert next_morning["flex_checked_at"] == evening["flex_checked_at"]
    assert next_morning["api_calls"]["fixture"] == 1   # primary pair only
