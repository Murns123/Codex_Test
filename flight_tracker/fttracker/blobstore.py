"""Tiny object stores for JSON documents: local directory (tests/offline) and Vercel Blob.

Vercel Blob is called over its HTTP API (the same calls the @vercel/blob SDK makes).
Base URL, API version and access mode come from config.yaml -> storage.blob so they can be
adjusted without code changes; `/api/selftest` exercises put/list/get on the live store.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode

import requests

from .http import HttpError, request_json

log = logging.getLogger(__name__)


class ObjectStore(Protocol):
    def put_json(self, path: str, obj: Any) -> None: ...
    def get_json(self, path: str) -> Any | None: ...   # None = does not exist
    def list(self, prefix: str) -> list[str]: ...


class LocalDirStore:
    def __init__(self, root: Path):
        self.root = root

    def put_json(self, path: str, obj: Any) -> None:
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, default=str))

    def get_json(self, path: str) -> Any | None:
        p = self.root / path
        return json.loads(p.read_text()) if p.exists() else None

    def list(self, prefix: str) -> list[str]:
        base = self.root / prefix
        if not base.exists():
            return []
        return sorted(str(p.relative_to(self.root)) for p in base.rglob("*") if p.is_file())


class VercelBlobStore:
    def __init__(self, token: str, *, base_url: str = "https://vercel.com/api/blob",
                 api_version: str = "11", access: str = "private", cache_max_age: int = 60,
                 store_id: str = "", store_id_header: str = "x-vercel-blob-store-id",
                 http_kwargs: dict[str, Any] | None = None, session: requests.Session | None = None):
        """token: a BLOB_READ_WRITE_TOKEN, or a Vercel OIDC token together with store_id
        (stores connected with OIDC have BLOB_STORE_ID but no read-write token)."""
        self.token = token
        self.store_id = store_id
        self.store_id_header = store_id_header
        self.base = base_url.rstrip("/")
        self.api_version = str(api_version)
        self.access = access
        self.cache_max_age = cache_max_age
        self.http_kwargs = http_kwargs or {}
        self.session = session
        self._urls: dict[str, str] = {}

    def _headers(self) -> dict[str, str]:
        h = {"authorization": f"Bearer {self.token}", "x-api-version": self.api_version}
        if self.store_id and self.store_id_header:
            h[self.store_id_header] = self.store_id
        return h

    def put_json(self, path: str, obj: Any) -> None:
        headers = {
            **self._headers(),
            "x-vercel-blob-access": self.access,
            "x-add-random-suffix": "0",
            "x-allow-overwrite": "1",
            "x-content-type": "application/json",
            "x-cache-control-max-age": str(self.cache_max_age),
        }
        res = request_json("PUT", f"{self.base}/?{urlencode({'pathname': path})}",
                           data=json.dumps(obj, default=str).encode(), headers=headers,
                           session=self.session, **self.http_kwargs)
        if isinstance(res, dict) and res.get("url"):
            self._urls[path] = res["url"]

    def _list_raw(self, prefix: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        cursor = None
        while True:
            params = {"prefix": prefix, "limit": 1000, **({"cursor": cursor} if cursor else {})}
            res = request_json("GET", f"{self.base}?{urlencode(params)}", headers=self._headers(),
                               session=self.session, **self.http_kwargs)
            out += res.get("blobs", [])
            if not res.get("hasMore") or not res.get("cursor"):
                return out
            cursor = res["cursor"]

    def list(self, prefix: str) -> list[str]:
        blobs = self._list_raw(prefix)
        for b in blobs:
            self._urls[b["pathname"]] = b["url"]
        return sorted(b["pathname"] for b in blobs)

    def get_json(self, path: str) -> Any | None:
        url = self._urls.get(path)
        if url is None:
            match = [b for b in self._list_raw(path) if b["pathname"] == path]
            if not match:
                return None
            url = self._urls[path] = match[0]["url"]
        try:
            return request_json("GET", url, headers={"authorization": f"Bearer {self.token}"},
                                session=self.session, **self.http_kwargs)
        except HttpError as exc:
            if exc.status == 404:
                return None
            raise
