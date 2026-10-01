"""DocStorage (the Vercel Blob layout) over a local directory, plus the Blob HTTP client."""
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from fttracker.blobstore import LocalDirStore, VercelBlobStore
from fttracker.http import HttpError
from fttracker.runner import run
from fttracker.storage import INDEX, DocStorage

FIX = Path(__file__).parent / "fixtures" / "ignav_sample.json"
MEL = ZoneInfo("Australia/Melbourne")


def at(day, hour=17):
    return dt.datetime(2026, 10, day, hour, tzinfo=MEL)


def test_doc_storage_end_to_end(settings, tmp_path):
    store = LocalDirStore(tmp_path / "blob")
    for d, h in [(1, 7), (1, 12), (1, 17), (2, 7)]:
        r = run(settings, now=at(d, h), fixtures=FIX, storage=DocStorage(store))
    assert r["day"] == 2 and r["trend"]["previous"]["date"] == "2026-10-01"
    s = DocStorage(store)
    assert len(s.recent_runs()) == 4 and len(s.log_lines()) == 4
    assert len(store.list("index/")) == 4
    assert s.latest_report()["run_id"] == r["run_id"] == 20261002070000
    assert store.get_json(f"runs/{r['run_id']}.json")["itineraries"]


def test_doc_storage_rebuilds_missing_index(settings, tmp_path):
    store = LocalDirStore(tmp_path / "blob")
    run(settings, now=at(1), fixtures=FIX, storage=DocStorage(store))
    run(settings, now=at(2), fixtures=FIX, storage=DocStorage(store))
    import shutil
    shutil.rmtree(tmp_path / "blob" / "index")
    r = run(settings, now=at(3), fixtures=FIX, storage=DocStorage(store))
    assert r["day"] == 3   # baseline survived
    assert len(store.list("index/")) == 1 and len(DocStorage(store).recent_runs()) == 3


def test_index_files_are_never_overwritten(settings, tmp_path):
    """Blob's CDN can serve stale copies of overwritten files, so storage only ever adds files."""
    store = LocalDirStore(tmp_path / "blob")
    writes = []
    orig = store.put_json
    store.put_json = lambda path, obj: (writes.append(path), orig(path, obj))[1]
    for d, h in [(1, 7), (1, 12), (2, 7)]:
        run(settings, now=at(d, h), fixtures=FIX, storage=DocStorage(store))
    assert len(writes) == len(set(writes)), "a path was written twice"
    assert INDEX not in writes


def test_legacy_index_file_is_still_read(settings, tmp_path):
    store = LocalDirStore(tmp_path / "blob")
    store.put_json(INDEX, [{"id": 20260930120000, "run_at": "2026-09-30T12:00:00+10:00", "run_date": "2026-09-30",
                            "status": "ok", "best_value": 5000.0, "best_price": 4000.0, "summary_line": "legacy"}])
    r = run(settings, now=at(1), fixtures=FIX, storage=DocStorage(store))
    assert r["day"] == 2 and r["trend"]["baseline"]["value_score"] == 5000.0


def test_doc_storage_dry_run_writes_nothing(settings, tmp_path):
    store = LocalDirStore(tmp_path / "blob")
    run(settings, now=at(1), fixtures=FIX, storage=DocStorage(store, dry_run=True))
    assert store.list("") == []


class Resp:
    def __init__(self, status, body):
        self.status_code, self._b, self.text = status, body, json.dumps(body)

    def json(self):
        return self._b


class FakeBlobAPI:
    """Minimal in-memory imitation of the Blob HTTP API, recording requests."""

    def __init__(self):
        self.objects, self.calls = {}, []

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw.get("headers", {})))
        if method == "PUT":
            path = url.split("pathname=")[1].replace("%2F", "/")
            u = f"https://store.private.blob.vercel-storage.com/{path}"
            self.objects[path] = (u, json.loads(kw["data"]))
            return Resp(200, {"url": u, "pathname": path})
        if url.startswith("https://store."):
            for u, body in self.objects.values():
                if u == url:
                    return Resp(200, body)
            return Resp(404, {"error": "not found"})
        prefix = url.split("prefix=")[1].split("&")[0].replace("%2F", "/")
        return Resp(200, {"blobs": [{"pathname": p, "url": u} for p, (u, _) in self.objects.items()
                                    if p.startswith(prefix)], "hasMore": False})


def test_blob_client_round_trip_and_headers():
    api = FakeBlobAPI()
    b = VercelBlobStore("tok", session=api, http_kwargs={"retries": 0})
    b.put_json("runs/index.json", [{"id": 1}])
    method, url, headers = api.calls[0]
    assert method == "PUT" and url.startswith("https://vercel.com/api/blob/?pathname=runs%2Findex.json")
    assert headers["authorization"] == "Bearer tok"
    assert headers["x-allow-overwrite"] == "1" and headers["x-add-random-suffix"] == "0"
    assert headers["x-vercel-blob-access"] == "private"
    fresh = VercelBlobStore("tok", session=api, http_kwargs={"retries": 0})   # no cached URLs
    assert fresh.get_json("runs/index.json") == [{"id": 1}]
    assert fresh.list("runs/") == ["runs/index.json"]
    assert fresh.get_json("runs/missing.json") is None


def test_blob_errors_are_not_mistaken_for_empty():
    class Down:
        def request(self, *a, **k):
            return Resp(403, {"error": "forbidden"})

    s = DocStorage(VercelBlobStore("bad", session=Down(), http_kwargs={"retries": 0}))
    with pytest.raises(HttpError):
        s.recent_runs()
