"""JEV (api.typesafe.ai) second opinion on the booking decision.

Same safety model as the paper trader in this repo: JEV returns probabilities,
deterministic code decides. JEV sees only the fares and statistics we computed
from real provider responses; it is never asked to produce a price.
"""
from __future__ import annotations

import logging
from typing import Any

from .http import HttpError, request_json

log = logging.getLogger(__name__)

JEV_BASE = "https://api.typesafe.ai"


def _noul(text: str) -> dict[str, str]:
    return {"type": "noul", "instructions": text}


QUESTIONS: dict[str, dict[str, Any]] = {
    # --- timing ---------------------------------------------------------------
    "book_now_is_right": _noul(
        "Given the price history, trend statistics, days left before the book-by date and the "
        "Christmas-peak season, is booking the best single-ticket option today the right call?"),
    "likely_rise_next_7d": _noul(
        "Is the best single-ticket price likely to be higher in 7 days than it is today?"),
    "likely_drop_5pct_before_book_by": _noul(
        "Is a further drop of 5% or more in the best single-ticket value score likely before the "
        "book-by date?"),
    "trend_is_upward": _noul(
        "Do the daily closes, regression slopes and streaks show a genuine upward trend rather than noise?"),
    "current_is_good_price": _noul(
        "Relative to the observed history and today's distribution of fares, is today's best single-ticket "
        "price a good price for this route and season?"),
    "volatility_high": _noul(
        "Is day-to-day price volatility high enough that waiting carries meaningful risk of a large jump?"),
    # --- option quality ---------------------------------------------------------
    "best_option_good_value": _noul(
        "Is the top-ranked option good overall value once travel time, stops and layovers are considered, "
        "not just price?"),
    "connection_risk_high": _noul(
        "Does the top-ranked option carry high misconnection or disruption risk (tight or very long "
        "layovers, many stops, multiple carriers, final regional hop into ELS)?"),
    "flex_dates_worth_it": _noul(
        "Is the best flex-date saving large enough to justify changing from the primary dates "
        "(21 Dec out / 8 Jan back)?"),
    "self_transfer_worth_considering": _noul(
        "Is the cheapest self-transfer option cheap enough versus the best single-ticket fare to be worth "
        "the missed-connection risk over Christmas?"),
    "data_quality_concern": _noul(
        "Is there a data-quality concern (failed providers, few itineraries, few date pairs, missing routes) "
        "that should make us cautious about today's reading?"),
    # --- choices ----------------------------------------------------------------
    "action": {
        "type": "choice",
        "instructions": "Choose the best action for this traveller today.",
        "criteria": {
            "buy_now": "Book the best single-ticket option today.",
            "buy_flex": "Book today but on the best flex-date combination instead of the primary dates.",
            "hold": "Wait for the next check; evidence does not yet favour booking.",
        },
    },
    "preferred_route": {
        "type": "choice",
        "instructions": "Which route family offers the best balance of price, time and reliability today? "
                        "Only choose among routes that appear in today's fares.",
        "criteria": {
            "A": "Qantas via Perth to Johannesburg, then connection to East London.",
            "B": "Qantas via Sydney to Johannesburg, then connection to East London.",
            "C": "South African Airways via Perth.",
            "D": "Gulf or Asian carrier (Emirates, Qatar, Etihad, Singapore) via its hub.",
            "other": "Another single-ticket routing.",
        },
    },
    "urgency": {
        "type": "score",
        "instructions": "How urgent is it to book? 1 = no rush, 5 = book immediately.",
        "legend": {"1": "no rush", "2": "low", "3": "moderate", "4": "high", "5": "book immediately"},
    },
}


def build_state(stats: dict[str, Any], decision: dict[str, Any], top: list[dict[str, Any]],
                rules: dict[str, Any], providers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "task": "Decide when to book a return economy flight Melbourne (MEL) -> East London (ELS), "
                "South Africa, 1 adult, prices in AUD.",
        "trip": stats["trip"],
        "calendar": stats["calendar"],
        "today": stats["today"],
        "history": stats["history"],
        "top_options": top,
        "rules_engine_decision": decision,
        "decision_rules": rules,
        "provider_status": providers,
        "note": "All prices are real quotes from fare APIs; value_score = price + a time penalty.",
    }


def extract(answers: dict[str, Any]) -> dict[str, Any]:
    """Flatten JEV answers into {key: probability | {choice probabilities} | score}."""
    out: dict[str, Any] = {}
    for k, a in (answers or {}).items():
        t = a.get("type")
        if t == "noul":
            out[k] = a.get("noul")
        elif t == "choice":
            out[k] = {"choice": a.get("choice"), "confidence": a.get("confidence"),
                      "probabilities": a.get("probabilities", {})}
        elif t == "score":
            out[k] = {"score": a.get("score"), "confidence": a.get("confidence")}
    return out


def buy_probability(flat: dict[str, Any]) -> float | None:
    """P(book today) = P(buy_now) + P(buy_flex) from the action question."""
    action = flat.get("action")
    if not isinstance(action, dict):
        return None
    p = action.get("probabilities") or {}
    if not p:
        return None
    return float(p.get("buy_now", 0)) + float(p.get("buy_flex", 0))


def evaluate(state: dict[str, Any], api_key: str, model: str, http_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Returns {"ok": bool, "answers": {...}, "buy_probability": float|None, "error": str|None, "raw": ...}."""
    body = {"model": model, "state": state, "questions": QUESTIONS}
    try:
        raw = request_json("POST", f"{JEV_BASE}/v1/systemone", json=body,
                           headers={"Authorization": f"Bearer {api_key}",
                                    "Content-Type": "application/json"},
                           **http_kwargs)
    except HttpError as exc:
        log.error("JEV failed: %s", exc)
        return {"ok": False, "answers": {}, "buy_probability": None, "error": str(exc), "raw": None}
    flat = extract(raw.get("answers", {}))
    return {"ok": True, "answers": flat, "buy_probability": buy_probability(flat), "error": None,
            "model": raw.get("model", model), "usage": raw.get("usage"), "raw": raw}
