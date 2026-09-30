"""Persistence.

- SqliteStorage: local CLI runs (data/tracker.sqlite3).
- DocStorage: one JSON document per run in an object store – Vercel Blob in production.
  Layout: runs/<id>.json (full report + itineraries), runs/index.json (one summary row
  per run), raw/<date>/<id>_<label>.json (every provider response).

Both expose the same methods. With dry_run=True every write is a no-op but reads still
see real history.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id {pk},
    run_at TEXT NOT NULL,
    run_date TEXT NOT NULL,
    status TEXT NOT NULL,
    decision TEXT,
    rule TEXT,
    reason TEXT,
    best_value REAL,
    best_price REAL,
    best_route TEXT,
    report_json TEXT
);
CREATE TABLE IF NOT EXISTS itineraries (
    id {pk},
    run_id BIGINT NOT NULL,
    rank INTEGER,
    provider TEXT,
    out_date TEXT,
    ret_date TEXT,
    route TEXT,
    price REAL,
    value_score REAL,
    too_long INTEGER,
    single_ticket INTEGER,
    carriers TEXT,
    stops_out INTEGER,
    stops_back INTEGER,
    hours_out REAL,
    hours_back REAL,
    longest_layover_min INTEGER,
    booking_link TEXT,
    detail_json TEXT
);
CREATE TABLE IF NOT EXISTS raw_responses (
    id {pk},
    run_id BIGINT NOT NULL,
    label TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS daily_log (
    id {pk},
    run_id BIGINT NOT NULL,
    run_date TEXT NOT NULL,
    line TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_itin_run ON itineraries(run_id);
CREATE INDEX IF NOT EXISTS idx_raw_run ON raw_responses(run_id);
"""


class SqliteStorage:
    def __init__(self, sqlite_path: Path | None = None, dry_run: bool = False):
        self.dry_run = dry_run
        path = sqlite_path or Path("data/tracker.sqlite3")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        for stmt in SCHEMA.format(pk="INTEGER PRIMARY KEY AUTOINCREMENT").split(";"):
            if stmt.strip():
                self._exec(stmt)
        self.conn.commit()

    # -- low level ---------------------------------------------------------------
    def _exec(self, sql: str, params: Iterable[Any] = ()) -> Any:
        cur = self.conn.cursor()
        cur.execute(sql, tuple(params))
        return cur

    def _rows(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        cur = self._exec(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def _commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # -- writes --------------------------------------------------------------------
    def start_run(self, run_at: dt.datetime) -> int:
        if self.dry_run:
            return 0
        cur = self._exec("INSERT INTO runs (run_at, run_date, status) VALUES (?, ?, 'running') RETURNING id",
                         (run_at.isoformat(), run_at.date().isoformat()))
        run_id = cur.fetchone()[0]
        self._commit()
        return int(run_id)

    def save_raw(self, run_id: int, label: str, payload: Any) -> None:
        if self.dry_run:
            return
        self._exec("INSERT INTO raw_responses (run_id, label, payload, created_at) VALUES (?, ?, ?, ?)",
                   (run_id, label, json.dumps(payload, default=str),
                    dt.datetime.now(dt.timezone.utc).isoformat()))
        self._commit()

    def finish_run(self, run_id: int, status: str, report: dict[str, Any], itineraries: list[Any]) -> None:
        if self.dry_run:
            return
        best = report.get("best") or {}
        dec = report.get("decision") or {}
        self._exec(
            "UPDATE runs SET status=?, decision=?, rule=?, reason=?, best_value=?, best_price=?, "
            "best_route=?, report_json=? WHERE id=?",
            (status, dec.get("decision"), dec.get("rule"), dec.get("reason"), best.get("value_score"),
             best.get("price_aud"), best.get("route"), json.dumps(report, default=str), run_id))
        for rank, it in enumerate(itineraries, 1):
            self._exec(
                "INSERT INTO itineraries (run_id, rank, provider, out_date, ret_date, route, price, value_score,"
                " too_long, single_ticket, carriers, stops_out, stops_back, hours_out, hours_back,"
                " longest_layover_min, booking_link, detail_json)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, rank, it.provider, it.outbound_date.isoformat(), it.return_date.isoformat(),
                 it.route, it.price, it.value_score, int(it.too_long), int(it.single_ticket),
                 ",".join(it.carriers), it.outbound.stops, it.inbound.stops, round(it.outbound.hours, 2),
                 round(it.inbound.hours, 2), it.longest_layover_min, it.booking_link,
                 json.dumps(it.to_dict(), default=str)))
        self._commit()

    def append_log(self, run_id: int, run_date: dt.date, line: str) -> None:
        if self.dry_run:
            return
        self._exec("INSERT INTO daily_log (run_id, run_date, line) VALUES (?, ?, ?)",
                   (run_id, run_date.isoformat(), line))
        self._commit()

    # -- reads ---------------------------------------------------------------------
    def scored_runs(self, exclude_run_id: int | None = None) -> list[dict[str, Any]]:
        """All runs that produced a best single-ticket option, oldest first."""
        rows = self._rows("SELECT id, run_at, run_date, best_value, best_price FROM runs "
                          "WHERE best_value IS NOT NULL ORDER BY run_at, id")
        return [r for r in rows if r["id"] != exclude_run_id]

    def latest_report(self) -> dict[str, Any] | None:
        rows = self._rows("SELECT report_json FROM runs WHERE report_json IS NOT NULL "
                          "ORDER BY run_at DESC, id DESC LIMIT 1")
        return json.loads(rows[0]["report_json"]) if rows else None

    def recent_runs(self, limit: int = 60) -> list[dict[str, Any]]:
        return self._rows("SELECT id, run_at, run_date, status, decision, reason, best_value, best_price,"
                          " best_route FROM runs ORDER BY run_at DESC, id DESC LIMIT ?", (limit,))

    def log_lines(self, limit: int = 200) -> list[str]:
        rows = self._rows("SELECT line FROM daily_log ORDER BY id DESC LIMIT ?", (limit,))
        return [r["line"] for r in reversed(rows)]

    def raw_for_run(self, run_id: int) -> list[dict[str, Any]]:
        return self._rows("SELECT label, payload, created_at FROM raw_responses WHERE run_id=? ORDER BY id",
                          (run_id,))


# ---------------------------------------------------------------------------------------
INDEX = "runs/index.json"
INDEX_FIELDS = ("id", "run_at", "run_date", "status", "decision", "rule", "reason",
                "best_value", "best_price", "best_route", "summary_line")


class DocStorage:
    """Same interface as SqliteStorage, on top of an ObjectStore (Vercel Blob)."""

    def __init__(self, store: Any, dry_run: bool = False):
        self.store = store
        self.dry_run = dry_run
        self._index: list[dict[str, Any]] | None = None

    def close(self) -> None:
        pass

    # -- index -------------------------------------------------------------------------
    def _load_index(self) -> list[dict[str, Any]]:
        if self._index is None:
            idx = self.store.get_json(INDEX)
            if idx is None:
                idx = self._rebuild_index()
            self._index = sorted(idx, key=lambda r: (r["run_at"], r["id"]))
        return self._index

    def _rebuild_index(self) -> list[dict[str, Any]]:
        """If index.json is missing, rebuild it from the per-run documents (never start empty
        while run documents exist – that would silently reset the baseline)."""
        rows = []
        for path in self.store.list("runs/"):
            if path == INDEX or not path.endswith(".json"):
                continue
            doc = self.store.get_json(path)
            if doc and "row" in doc:
                rows.append(doc["row"])
        if rows:
            log.warning("runs/index.json missing – rebuilt from %d run documents", len(rows))
        return rows

    # -- writes --------------------------------------------------------------------------
    def start_run(self, run_at: dt.datetime) -> int:
        if self.dry_run:
            return 0
        self._load_index()   # fail early (before any API spend) if storage is unreachable
        run_id = int(run_at.strftime("%Y%m%d%H%M%S"))
        return run_id

    def save_raw(self, run_id: int, label: str, payload: Any) -> None:
        if self.dry_run:
            return
        date = str(run_id)[:8]
        self.store.put_json(f"raw/{date[:4]}-{date[4:6]}-{date[6:]}/{run_id}_{label}.json", payload)

    def finish_run(self, run_id: int, status: str, report: dict[str, Any], itineraries: list[Any]) -> None:
        if self.dry_run:
            return
        best = report.get("best") or {}
        dec = report.get("decision") or {}
        row = {
            "id": run_id, "run_at": report["run_at"], "run_date": report["run_at"][:10], "status": status,
            "decision": dec.get("decision"), "rule": dec.get("rule"), "reason": dec.get("reason"),
            "best_value": best.get("value_score"), "best_price": best.get("price_aud"),
            "best_route": best.get("route"), "summary_line": report.get("summary_line"),
        }
        self.store.put_json(f"runs/{run_id}.json", {
            "row": row, "report": report,
            "itineraries": [it.to_dict() for it in itineraries],
        })
        index = [r for r in self._load_index() if r["id"] != run_id] + [row]
        self.store.put_json(INDEX, index)
        self._index = sorted(index, key=lambda r: (r["run_at"], r["id"]))

    def append_log(self, run_id: int, run_date: dt.date, line: str) -> None:
        pass  # the summary line is part of the index row written by finish_run

    # -- reads ---------------------------------------------------------------------------
    def scored_runs(self, exclude_run_id: int | None = None) -> list[dict[str, Any]]:
        return [r for r in self._load_index() if r.get("best_value") is not None and r["id"] != exclude_run_id]

    def latest_report(self) -> dict[str, Any] | None:
        idx = self._load_index()
        if not idx:
            return None
        doc = self.store.get_json(f"runs/{idx[-1]['id']}.json")
        return doc["report"] if doc else None

    def recent_runs(self, limit: int = 60) -> list[dict[str, Any]]:
        return list(reversed(self._load_index()))[:limit]

    def log_lines(self, limit: int = 200) -> list[str]:
        return [r["summary_line"] for r in self._load_index() if r.get("summary_line")][-limit:]

    def raw_for_run(self, run_id: int) -> list[dict[str, Any]]:
        d = str(run_id)[:8]
        paths = [p for p in self.store.list(f"raw/{d[:4]}-{d[4:6]}-{d[6:]}/") if f"/{run_id}_" in p]
        return [{"label": p.rsplit("/", 1)[-1], "payload": self.store.get_json(p)} for p in paths]
