"""Qantas SYD <-> JNB section, offline via the fixture fetch."""
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from fttracker import qantas
from fttracker.http import HttpError
from fttracker.report import to_html, to_text
from fttracker.runner import open_storage, run

FIX = Path(__file__).parent / "fixtures" / "ignav_sample.json"
MEL = ZoneInfo("Australia/Melbourne")


def at(day, hour=17):
    return dt.datetime(2026, 10, day, hour, tzinfo=MEL)


def section(settings, hour=17, rows=None, fetch=None):
    return qantas.run_section(settings, now=at(1, hour), flex_this_run=hour >= 15, history_rows=rows or [],
                              save_raw=lambda *a: "", fetch=fetch or qantas.fixture_fetch(json.loads(FIX.read_text())),
                              main_best={"price_aud": 3420.0}, fixture=True)


def test_only_qantas_fares_are_kept(settings):
    q = section(settings)
    prices = [o["price_aud"] for o in q["options"]["rt"]]
    assert prices == [2650, 2890]                     # the 2100 Emirates option is ignored
    assert [o["price_aud"] for o in q["options"]["out"]] == [1650]    # 1100 EK one-way ignored
    assert "non-QF itineraries ignored" in q["note"]
    assert q["series"] == {"qf_rt": 2650, "qf_out": 1650, "qf_back": 1580}


def test_nonstop_detection_and_extras(settings):
    q = section(settings)
    rt = {o["price_aud"]: o for o in q["options"]["rt"]}
    assert rt[2890]["nonstop_both"] and rt[2890]["out"]["flights"] == "QF63"
    assert not rt[2650]["nonstop_both"] and rt[2650]["out"]["route"] == "SYD-PER-JNB"
    ex = q["stats"]["extra"]
    assert ex["nonstop_premium_aud"] == 240
    assert ex["two_one_ways_aud"] == 3230 and ex["return_vs_two_one_ways_aud"] == 580   # return cheaper
    assert ex["rt_vs_main_best_aud"] == 2650 - 3420


def test_flex_run_builds_date_matrix_and_cheapest_combo(settings):
    q = section(settings, hour=17)
    assert q["rt_matrix"]["2026-12-21_2027-01-10"] == 2590
    assert q["cheapest_combo"]["price_aud"] == 2590 and q["cheapest_combo"]["saving_vs_primary"] == 60
    assert q["ow_by_date"]["out"]["2026-12-19"] == 1490
    morning = section(settings, hour=7)
    assert "rt_matrix" not in morning and morning["calls"] == 3      # primary RT + 2 one-ways


def test_history_rules_and_step_jumps(settings):
    rows = [{"id": 1, "run_at": "2026-09-28T17:00", "run_date": "2026-09-28", "series": {"qf_rt": 2300}},
            {"id": 2, "run_at": "2026-09-29T17:00", "run_date": "2026-09-29", "series": {"qf_rt": 2450}},
            {"id": 3, "run_at": "2026-09-30T17:00", "run_date": "2026-09-30", "series": {"qf_rt": 2600}}]
    q = section(settings, rows=rows)
    assert q["decision"]["decision"] == "BUY" and q["decision"]["rule"] == "rising"   # 2300 -> 2450 -> 2600 -> 2650
    h = q["stats"]["qf_rt"]
    assert h["days_observed"] == 4 and h["baseline_value"] == 2300
    assert q["stats"]["qf_rt"]["steps"]["largest_step_pct"] > 0


def test_airline_filter_rejected_falls_back_to_local_filter(settings):
    payload = json.loads(FIX.read_text())
    calls = []

    def fetch(kind, body):
        calls.append(body)
        if "airlines_include" in body:
            raise HttpError('HTTP 400: {"field":"airlines_include"}', 400)
        return qantas.fixture_fetch(payload)(kind, body)

    q = section(settings, hour=7, fetch=fetch)
    assert q["series"]["qf_rt"] == 2650
    assert any("filtered locally" in e for e in q["errors"])


def test_failed_calls_never_invent_fares(settings):
    def down(kind, body):
        raise HttpError("HTTP 503", 503)

    q = section(settings, hour=7, fetch=down)
    assert q["status"] == "failed" and q["series"] == {"qf_rt": None, "qf_out": None, "qf_back": None}
    assert q["options"] == {"rt": [], "out": [], "back": []}
    assert q["decision"]["rule"] == "no_data"


def test_questions_are_well_formed():
    qs = qantas.qantas_questions(["2026-12-19", "2026-12-21"], ["2027-01-08"])
    assert qs["best_outbound_date"]["criteria"].keys() == {"2026-12-19", "2026-12-21"}
    assert "best_return_date" not in qs
    for k, v in qs.items():
        assert v["type"] in ("noul", "choice", "score") and v["instructions"]
        if v["type"] in ("choice", "score"):
            assert len(v["criteria"]) >= 2, k
        if v["type"] == "score":
            assert isinstance(v["criteria"], list), k


def test_end_to_end_section_in_report_and_history(settings):
    run(settings, now=at(1, 17), fixtures=FIX)
    r = run(settings, now=at(2, 17), fixtures=FIX)
    q = r["qantas"]
    assert r["series"]["qf_rt"] == 2650
    assert q["stats"]["qf_rt"]["days_observed"] == 2 and q["decision"]["rule"] == "small_move"
    assert "QF SYD-JNB return AUD 2,650" in r["summary_line"]
    s = open_storage(settings)
    page = to_html(s.latest_report(), s.recent_runs(), s.log_lines())
    s.close()
    assert "Qantas SYD ⇄ JNB" in page and "QF63" in page and "Return fare by dates" in page
    assert "Qantas SYD ⇄ JNB: ok" in to_text(r)


# --- generic MEL <-> JNB section (any airline, domestic leg excluded) ---------------------
def mj_section(settings, hour=17, rows=None):
    return qantas.run_section(settings, now=at(1, hour), flex_this_run=hour >= 15, history_rows=rows or [],
                              save_raw=lambda *a: "", fetch=qantas.fixture_fetch(json.loads(FIX.read_text()), "mj"),
                              main_best={"price_aud": 3420.0}, fixture=True,
                              cfg=settings.routes["mel_jnb"], prefix="mj")


def test_generic_section_keeps_every_airline(settings):
    q = mj_section(settings)
    assert [o["price_aud"] for o in q["options"]["rt"]] == [2980, 3350]       # EK and QF both kept
    assert q["series"] == {"mj_rt": 2980, "mj_out": None, "mj_back": None}
    assert q["stats"]["extra"]["cheapest_by_airline"] == {"EK": 2980, "QF": 3350}
    assert q["title"] == "MEL ⇄ JNB (any airline)" and q["airline"] is None and "note" not in q
    assert q["cheapest_combo"]["price_aud"] == 2790


def test_generic_section_returns_only_and_no_airline_filter(settings):
    calls = []

    def fetch(kind, body):
        calls.append((kind, body))
        return qantas.fixture_fetch(json.loads(FIX.read_text()), "mj")(kind, body)

    qantas.run_section(settings, now=at(1, 7), flex_this_run=False, history_rows=[], save_raw=lambda *a: "",
                       fetch=fetch, fixture=True, cfg=settings.routes["mel_jnb"], prefix="mj")
    assert [k for k, _ in calls] == ["rt"]                                     # one_way: false
    assert "airlines_include" not in calls[0][1] and calls[0][1]["origin"] == "MEL"


def test_generic_questions_offer_airline_choice_without_nonstop_or_one_ways():
    qs = qantas.route_questions(["2026-12-21"], ["2027-01-08"], "MEL", "JNB", None, one_way=False,
                                carriers=["EK", "QF"])
    assert qs["preferred_airline"]["criteria"].keys() == {"EK", "QF"}
    assert "nonstop_worth_premium" not in qs and "one_ways_better_than_return" not in qs
    assert "book_one_ways_now" not in qs["action"]["criteria"]


def test_report_has_three_answers_and_series_kept_apart(settings):
    run(settings, now=at(1, 17), fixtures=FIX)
    r = run(settings, now=at(2, 17), fixtures=FIX)
    assert r["series"]["mj_rt"] == 2980 and r["series"]["qf_rt"] == 2650
    mj = r["routes"]["mel_jnb"]
    assert mj["stats"]["mj_rt"]["days_observed"] == 2
    assert "MEL-JNB return AUD 2,980" in r["summary_line"]
    page = to_html(r)
    assert page.count("class='card answer'") == 3
    assert "MEL ⇄ JNB (any airline)" in page and "Cheapest return by airline" in page
    assert "domestic" in page
