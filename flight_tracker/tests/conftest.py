import datetime as dt
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fttracker.models import Itinerary, Leg, Segment  # noqa: E402


def leg(route: list[tuple[str, str, str]], hours: float, layovers_h: list[float] | None = None) -> Leg:
    """route = [(origin, destination, carrier), ...]"""
    return Leg(segments=[Segment(o, d, c, flight_number=f"{c}{i}") for i, (o, d, c) in enumerate(route)],
               duration_min=int(hours * 60), layovers_min=[int(h * 60) for h in (layovers_h or [])])


def itin(price: float, out_h: float = 20, back_h: float = 20, single: bool = True,
         out_route=None, back_route=None) -> Itinerary:
    out_route = out_route or [("MEL", "PER", "QF"), ("PER", "JNB", "QF"), ("JNB", "ELS", "4Z")]
    back_route = back_route or [("ELS", "JNB", "4Z"), ("JNB", "PER", "QF"), ("PER", "MEL", "QF")]
    return Itinerary(provider="test", outbound_date=dt.date(2026, 12, 21), return_date=dt.date(2027, 1, 8),
                     price=price, currency="AUD", outbound=leg(out_route, out_h, [2, 3]),
                     inbound=leg(back_route, back_h, [2, 3]), single_ticket=single)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    for k in ("IGNAV_API_KEY", "SERPAPI_KEY", "JEV_API_KEY", "BLOB_READ_WRITE_TOKEN", "VERCEL"):
        monkeypatch.setenv(k, "")
    from fttracker.config import load_settings
    s = load_settings(ROOT / "config.yaml", env_path=tmp_path / "none.env")
    s.paths = {"db": tmp_path / "t.sqlite3", "raw_dir": tmp_path / "raw",
               "daily_log": tmp_path / "daily_log.md", "app_log": tmp_path / "t.log"}
    return s
