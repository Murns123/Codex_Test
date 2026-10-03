"""Loads config.yaml and .env into one typed settings object."""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def _date(value: Any) -> dt.date:
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(str(value))


@dataclass(frozen=True)
class ScoringConfig:
    dollars_per_hour: float = 50
    hours_threshold: float = 22
    too_long_hours: float = 30
    too_long_exempt_saving: float = 500


@dataclass(frozen=True)
class DecisionConfig:
    buy_below_baseline_pct: float = 5
    buy_under_price: float = 3000
    rising_runs_for_buy: int = 2
    hold_movement_pct: float = 3
    suspect_jump_pct: float = 25      # a one-step move this big waits for a second run to confirm it
    book_by: dt.date = dt.date(2026, 10, 14)
    hard_stop: dt.date = dt.date(2026, 10, 31)
    trend_basis: str = "day"


@dataclass(frozen=True)
class TripConfig:
    origin: str
    destination: str
    outbound: dt.date
    return_date: dt.date
    adults: int
    cabin: str
    currency: str
    flex_outbound: list[dt.date]
    flex_return: list[dt.date]
    flex_mode: str = "cross"
    flex_from_hour: int = 15
    flex_time_budget_s: float = 170

    def date_pairs(self) -> list[tuple[dt.date, dt.date]]:
        """Primary pair first, then the flex combinations."""
        pairs = [(self.outbound, self.return_date)]
        if self.flex_mode == "grid":
            outs = [self.outbound, *self.flex_outbound]
            rets = [self.return_date, *self.flex_return]
            pairs += [(o, r) for o in sorted(outs) for r in sorted(rets)]
        else:
            pairs += [(o, self.return_date) for o in self.flex_outbound]
            pairs += [(self.outbound, r) for r in self.flex_return]
        seen: list[tuple[dt.date, dt.date]] = []
        for p in pairs:
            if p not in seen:
                seen.append(p)
        return seen


@dataclass
class Settings:
    trip: TripConfig
    scoring: ScoringConfig
    decision: DecisionConfig
    providers: dict[str, dict[str, Any]]
    http: dict[str, Any]
    jev: dict[str, Any]
    storage: dict[str, Any]
    qantas: dict[str, Any]
    routes: dict[str, dict[str, Any]]
    paths: dict[str, Path]
    timezone: str
    env: dict[str, str] = field(default_factory=dict)


def load_settings(config_path: Path | None = None, env_path: Path | None = None) -> Settings:
    config_path = config_path or ROOT / "config.yaml"
    load_dotenv(env_path or ROOT / ".env")
    raw = yaml.safe_load(config_path.read_text())

    t = raw["trip"]
    trip = TripConfig(
        origin=t["origin"],
        destination=t["destination"],
        outbound=_date(t["outbound"]),
        return_date=_date(t["return"]),
        adults=int(t.get("adults", 1)),
        cabin=t.get("cabin", "economy"),
        currency=t.get("currency", "AUD"),
        flex_outbound=[_date(d) for d in t.get("flex", {}).get("outbound", [])],
        flex_return=[_date(d) for d in t.get("flex", {}).get("return", [])],
        flex_mode=t.get("flex_mode", "cross"),
        flex_from_hour=int(t.get("flex_from_hour", 15)),
        flex_time_budget_s=float(t.get("flex_time_budget_s", 170)),
    )
    s = raw.get("scoring", {})
    scoring = ScoringConfig(**{k: float(v) for k, v in s.items()})
    d = dict(raw.get("decision", {}))
    for k in ("book_by", "hard_stop"):
        if k in d:
            d[k] = _date(d[k])
    if "rising_runs_for_buy" in d:
        d["rising_runs_for_buy"] = int(d["rising_runs_for_buy"])
    decision = DecisionConfig(**d)

    paths = {k: (ROOT / v) for k, v in raw.get("paths", {}).items()}
    env_keys = ["IGNAV_API_KEY", "SERPAPI_KEY", "JEV_API_KEY", "JEV_MODEL", "BLOB_READ_WRITE_TOKEN",
                "BLOB_STORE_ID", "VERCEL_OIDC_TOKEN", "CRON_SECRET", "VERCEL"]
    env = {k: os.environ.get(k, "").strip() for k in env_keys}
    # tolerate the common misspelling of the SerpApi variable name
    env["SERPAPI_KEY"] = env["SERPAPI_KEY"] or os.environ.get("SERAPI_KEY", "").strip()
    return Settings(
        trip=trip,
        scoring=scoring,
        decision=decision,
        providers=raw.get("providers", {}),
        http=raw.get("http", {}),
        jev=raw.get("jev", {}),
        storage=raw.get("storage", {}),
        qantas=raw.get("qantas", {}),
        routes=raw.get("routes", {}) or {},
        paths=paths,
        timezone=raw.get("timezone", "Australia/Melbourne"),
        env=env,
    )
