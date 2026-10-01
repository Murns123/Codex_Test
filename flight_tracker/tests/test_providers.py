import datetime as dt
import json
from pathlib import Path

import pytest
import requests

from fttracker.http import HttpError, request_json
from fttracker.providers.ignav import _minutes, parse_response
from fttracker.providers.serpapi import is_self_transfer, parse_leg

FIX = Path(__file__).parent / "fixtures" / "ignav_sample.json"
OUT, RET = dt.date(2026, 12, 21), dt.date(2027, 1, 8)


def test_ignav_parse_fixture_drops_incomplete_rows():
    payload = json.loads(FIX.read_text())["2026-12-21_2027-01-08"]
    its, problems = parse_response(payload, OUT, RET, "AUD")
    assert [i.price for i in its] == [3420, 3150, 2700]
    assert any("2 itineraries dropped" in p for p in problems)


def test_ignav_parse_fields():
    payload = json.loads(FIX.read_text())["2026-12-21_2027-01-08"]
    a, d, e = parse_response(payload, OUT, RET, "AUD")[0]
    assert a.outbound.airports == ["MEL", "PER", "JNB", "ELS"]
    assert a.outbound.carriers == ["QF", "4Z"]
    assert a.outbound.stops == 2 and a.outbound.longest_layover_min == 180
    assert a.booking_link.startswith("https://")
    assert d.outbound.duration_min == 27 * 60 + 10          # ISO-8601 duration
    assert a.single_ticket and d.single_ticket and not e.single_ticket


def test_ignav_rejects_other_currency():
    payload = {"itineraries": [{"price": {"amount": 100, "currency": "USD"}, "legs": []}]}
    its, problems = parse_response(payload, OUT, RET, "AUD")
    assert its == [] and "USD" in problems[0]


def test_minutes_parser():
    assert _minutes(90) == 90
    assert _minutes("PT1H30M") == 90
    assert _minutes("P1DT2H") == 1560
    assert _minutes("abc") is None


def test_serpapi_leg_and_self_transfer():
    opt = {"flights": [{"departure_airport": {"id": "MEL", "time": "2026-12-21 06:00"},
                        "arrival_airport": {"id": "PER", "time": "2026-12-21 07:35"},
                        "duration": 275, "airline": "Qantas", "flight_number": "QF 770"},
                       {"departure_airport": {"id": "PER"}, "arrival_airport": {"id": "JNB"},
                        "duration": 705, "airline": "Qantas", "flight_number": "QF 63"}],
           "layovers": [{"duration": 180, "id": "PER"}], "total_duration": 1160, "price": 3400}
    leg = parse_leg(opt)
    assert leg.carriers == ["QF"] and leg.duration_min == 1160 and leg.layovers_min == [180]
    assert not is_self_transfer(opt)
    opt["extensions"] = ["Self transfer"]
    assert is_self_transfer(opt)


class FakeResp:
    def __init__(self, status, body):
        self.status_code, self._body, self.text = status, body, json.dumps(body)

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), 0

    def request(self, *a, **k):
        self.calls += 1
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def test_http_retries_then_succeeds():
    waits = []
    s = FakeSession([FakeResp(503, {}), requests.ConnectionError("boom"), FakeResp(200, {"ok": 1})])
    assert request_json("GET", "http://x", session=s, sleep=waits.append, backoff_base_s=2) == {"ok": 1}
    assert s.calls == 3 and waits == [2, 4]


def test_http_gives_up():
    s = FakeSession([FakeResp(500, {})] * 4)
    with pytest.raises(HttpError, match="gave up after 4"):
        request_json("GET", "http://x", session=s, sleep=lambda _: None, retries=3)


def test_http_does_not_retry_auth_errors():
    s = FakeSession([FakeResp(401, {"error": "bad key"})])
    with pytest.raises(HttpError, match="401"):
        request_json("GET", "http://x", session=s, sleep=lambda _: None)
    assert s.calls == 1


def test_http_errors_never_carry_api_keys():
    class Boom:
        def request(self, *a, **k):
            raise requests.ConnectionError("Max retries exceeded with url: /search.json?engine=x&api_key=SECRET123&q=1")

    with pytest.raises(HttpError) as e:
        request_json("GET", "http://x", session=Boom(), sleep=lambda _: None, retries=0)
    assert "SECRET123" not in str(e.value) and "api_key=***" in str(e.value)


# Shape reported for the real Ignav API: price object in USD, outbound/inbound legs,
# segments with marketing_carrier_code and *_time_local fields.
REAL_SHAPE = {"itineraries": [{
    "ignav_id": "abc",
    "price": {"amount": 2500, "currency": "USD", "status": "verified"},
    "booking_url": "https://example.invalid/book",
    "outbound": {"carrier": "QF", "duration_minutes": 1400, "segments": [
        {"marketing_carrier_code": "QF", "flight_number": "770", "departure_airport": "MEL",
         "departure_time_local": "2026-12-21T06:00:00", "arrival_airport": "PER",
         "arrival_time_local": "2026-12-21T07:35:00", "duration_minutes": 275},
        {"marketing_carrier_code": "QF", "flight_number": "63", "departure_airport": "PER",
         "departure_time_local": "2026-12-21T10:35:00", "arrival_airport": "JNB",
         "arrival_time_local": "2026-12-21T17:20:00", "duration_minutes": 705}]},
    "inbound": {"carrier": "QF", "duration_minutes": 1450, "segments": [
        {"marketing_carrier_code": "QF", "flight_number": "64", "departure_airport": "JNB",
         "departure_time_local": "2027-01-08T11:30:00", "arrival_airport": "PER",
         "arrival_time_local": "2027-01-09T05:05:00", "duration_minutes": 695},
        {"marketing_carrier_code": "QF", "flight_number": "771", "departure_airport": "PER",
         "departure_time_local": "2027-01-09T09:05:00", "arrival_airport": "MEL",
         "arrival_time_local": "2027-01-09T14:45:00", "duration_minutes": 220}]},
}]}


def test_ignav_real_shape_with_usd_conversion():
    fx = {"rates": {"USD": 1.5}, "date": "2026-10-01", "source": "ECB"}
    its, problems = parse_response(REAL_SHAPE, OUT, RET, "AUD", fx)
    assert problems == [] and len(its) == 1
    it = its[0]
    assert it.price == 3750.0 and "converted from USD 2,500 at 1.5" in it.notes[0]
    assert it.outbound.airports == ["MEL", "PER", "JNB"] and it.outbound.carriers == ["QF"]
    assert it.outbound.layovers_min == [180] and it.inbound.layovers_min == [240]   # from same-airport local times
    assert it.booking_link == "https://example.invalid/book"


def test_ignav_usd_without_rate_is_left_out():
    its, problems = parse_response(REAL_SHAPE, OUT, RET, "AUD", None)
    assert its == [] and "no USD->AUD rate" in problems[0]


def test_ignav_retries_empty_and_failed_pairs_once(settings, monkeypatch):
    from fttracker.providers import ignav
    settings.env["IGNAV_API_KEY"] = "k"
    payload = json.loads(FIX.read_text())["2026-12-21_2027-01-08"]
    seen = []

    def fake(method, url, json=None, **kw):
        key = json["departure_date"]
        seen.append(key)
        if key == "2026-12-19":                          # 19 Dec: empty first time, fares second time
            n = seen.count(key)
            return {"itineraries": []} if n == 1 else payload
        raise HttpError("HTTP 424: upstream_error")      # everything else keeps failing

    monkeypatch.setattr(ignav, "request_json", fake)
    p = ignav.IgnavProvider(settings, lambda label, data: label)
    res = p.search([(dt.date(2026, 12, 19), RET), (dt.date(2026, 12, 20), RET)])
    assert res.calls == 4                                 # 2 pairs + 1 retry each
    assert len(res.itineraries) == 3                       # 19 Dec filled in on the retry
    fails = [e for e in res.errors if "424" in e]
    assert len(fails) == 1 and fails[0].startswith("20 Dec")   # still reported, nothing invented
