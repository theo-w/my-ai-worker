"""Supabase REST-backed storage for the provenance-first game knowledge base.

The local JSON file remains a cache/fallback. Credentials are read only from
server-side environment variables and are never logged or returned by APIs.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    from .game_knowledge import GameKnowledgeBase
except ImportError:
    from game_knowledge import GameKnowledgeBase


class SupabaseGameKnowledgeBase(GameKnowledgeBase):
    def __init__(self, url: str, secret_key: str, table: str = "jarvis_game_knowledge", path: str | None = None):
        self.supabase_url = url.rstrip("/")
        self.secret_key = secret_key
        self.table = table
        self.backend_error = None
        super().__init__(path=path)

    def _request(self, method: str, query: str = "", payload=None):
        endpoint = f"{self.supabase_url}/rest/v1/{quote(self.table, safe='_')}"
        if query:
            endpoint += "?" + query
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(endpoint, data=body, method=method, headers={
            "apikey": self.secret_key,
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        })
        try:
            with urlopen(request, timeout=8) as response:
                raw = response.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            # Never include request headers or credential-bearing data in errors.
            raise RuntimeError(f"Supabase knowledge storage returned HTTP {exc.code}") from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise RuntimeError("Supabase knowledge storage is unreachable or returned invalid JSON") from None

    def load(self) -> None:
        # Load remote first; merge any local-only records so a temporary outage
        # cannot discard records written to the local cache.
        local_records = []
        try:
            target = __import__("pathlib").Path(self.path)
            if target.exists():
                payload = json.loads(target.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    local_records = [row for row in payload.get("records", []) if isinstance(row, dict) and row.get("id")]
        except (OSError, ValueError, TypeError):
            local_records = []
        merged = {str(row["id"]): row for row in local_records}
        try:
            remote = self._request("GET", "select=*&order=last_seen_at.desc&limit=10000") or []
            if not isinstance(remote, list):
                raise RuntimeError("Supabase knowledge storage returned an unexpected response")
            merged = {str(row.get("id")): row for row in remote if isinstance(row, dict) and row.get("id")}
            for row in local_records:
                merged.setdefault(str(row["id"]), row)
            self._records = list(merged.values())
            self.backend_error = None
            if local_records and (not remote or len(merged) > len(remote)):
                self._sync_remote(self._records)
        except RuntimeError as exc:
            # Continue in JSON mode during setup/outage, while making the status
            # visible so the dashboard does not imply durable cloud storage.
            self.backend_error = str(exc)
            self._records = list(merged.values())

    def _sync_remote(self, rows):
        for start in range(0, len(rows), 200):
            self._request("POST", "on_conflict=id", rows[start:start + 200])

    def save(self) -> None:
        # Always keep a local cache, then sync to Supabase. Failures are surfaced
        # through summary() while allowing research itself to complete.
        super().save()
        try:
            self._sync_remote(self._records)
            self.backend_error = None
        except RuntimeError as exc:
            self.backend_error = str(exc)

    def summary(self) -> dict:
        result = super().summary()
        result.update({
            "storage_backend": "supabase" if self.backend_error is None else "json_fallback",
            "supabase_configured": True,
            "storage_error": self.backend_error,
            "table": self.table,
        })
        return result
