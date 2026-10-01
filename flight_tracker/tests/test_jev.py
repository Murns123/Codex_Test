from fttracker import jev
from fttracker.http import HttpError

ANSWERS = {
    "book_now_is_right": {"type": "noul", "noul": 0.7},
    "action": {"type": "choice", "choice": "buy_now", "confidence": 0.6,
               "probabilities": {"buy_now": 0.6, "buy_flex": 0.25, "hold": 0.15}},
    "urgency": {"type": "score", "score": 4, "confidence": 0.5, "legend": {}, "probabilities": {}},
}


def test_extract_and_buy_probability():
    flat = jev.extract(ANSWERS)
    assert flat["book_now_is_right"] == 0.7
    assert flat["urgency"]["score"] == 4
    assert jev.buy_probability(flat) == 0.85


def test_buy_probability_missing_action():
    assert jev.buy_probability({}) is None


def test_every_question_is_well_formed():
    for key, q in jev.QUESTIONS.items():
        if q["type"] == "score":
            assert isinstance(q["criteria"], list) and len(q["criteria"]) >= 2 and "legend" not in q, key
        assert q["type"] in ("noul", "choice", "score"), key
        assert q["instructions"], key
        if q["type"] == "choice":
            assert len(q["criteria"]) >= 2


def test_evaluate_sends_questions_and_parses(monkeypatch):
    seen = {}

    def fake(method, url, **kw):
        seen.update(url=url, body=kw["json"], auth=kw["headers"]["Authorization"])
        return {"model": "jev-latest", "answers": ANSWERS, "usage": {}}

    monkeypatch.setattr(jev, "request_json", fake)
    out = jev.evaluate({"x": 1}, "k", "jev-latest", {})
    assert out["ok"] and out["buy_probability"] == 0.85
    assert seen["url"].endswith("/v1/systemone") and seen["auth"] == "Bearer k"
    assert set(seen["body"]["questions"]) == set(jev.QUESTIONS)


def test_evaluate_failure_is_reported_not_raised(monkeypatch):
    def boom(*a, **k):
        raise HttpError("HTTP 503")

    monkeypatch.setattr(jev, "request_json", boom)
    out = jev.evaluate({}, "k", "m", {})
    assert not out["ok"] and out["buy_probability"] is None and "503" in out["error"]
