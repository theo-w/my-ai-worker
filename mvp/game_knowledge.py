"""Small provenance-first knowledge store for recurring game-mechanics research.

This is a lexical retrieval MVP, not a vector database. It stores source-backed
records with explicit verification status and never upgrades snippets into facts.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path


def _tokens(text: str) -> set[str]:
    text = str(text or "").lower()
    tokens = set(re.findall(r"[a-z0-9][a-z0-9_-]{1,}", text))
    # Chinese bigrams provide useful matching without external tokenization deps.
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(run) == 1:
            tokens.add(run)
        else:
            tokens.update(run[i:i + 2] for i in range(len(run) - 1))
    return tokens


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GameKnowledgeBase:
    """JSON-backed knowledge store; path can be redirected to persistent storage."""

    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("JARVIS_GAME_KNOWLEDGE_PATH", "data/game_knowledge.json")
        self._lock = threading.RLock()
        self._records: list[dict] = []
        self.load()

    def load(self) -> None:
        with self._lock:
            target = Path(self.path)
            if not target.exists():
                self._records = []
                return
            try:
                payload = json.loads(target.read_text(encoding="utf-8"))
                rows = payload.get("records", []) if isinstance(payload, dict) else []
                self._records = [row for row in rows if isinstance(row, dict) and row.get("id")]
            except (OSError, ValueError, TypeError):
                # Corrupt memory is isolated rather than preventing startup.
                self._records = []

    def save(self) -> None:
        with self._lock:
            target = Path(self.path)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_text(json.dumps({
                "schema_version": 1,
                "updated_at": _now(),
                "records": self._records,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(target)

    def ingest_sources(self, query: str, sources: list[dict], evidence: list[dict] | None = None) -> dict:
        """Store traceable source records; a search excerpt is not independently verified."""
        accepted_urls = {
            str((item.get("source") or {}).get("url", "")).split("#", 1)[0].rstrip("/")
            for item in (evidence or [])
            if item.get("quality_accepted") and isinstance(item.get("source"), dict)
        }
        inserted = 0
        updated = 0
        with self._lock:
            by_url = {str(row.get("url", "")).split("#", 1)[0].rstrip("/"): row for row in self._records if row.get("url")}
            for source in sources or []:
                if not isinstance(source, dict):
                    continue
                url = str(source.get("url", "")).strip()
                title = str(source.get("title", "")).strip()
                snippet = str(source.get("snippet", "")).strip()
                if not url.startswith("https://") or not title or not snippet:
                    continue
                normalized = url.split("#", 1)[0].rstrip("/")
                quality_accepted = normalized in accepted_urls
                existing = by_url.get(normalized)
                record = {
                    "id": hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16],
                    "title": title[:500],
                    "url": normalized,
                    "snippet": snippet[:4000],
                    "query": str(query or "")[:2000],
                    "provider": str(source.get("provider", "unknown"))[:100],
                    "published_at": source.get("published_at"),
                    "first_seen_at": (existing or {}).get("first_seen_at", _now()),
                    "last_seen_at": _now(),
                    "seen_count": int((existing or {}).get("seen_count", 0)) + 1,
                    "quality_accepted_at_capture": quality_accepted,
                    "knowledge_status": "source_backed_unverified",
                    "verification_note": "Search excerpt retained for retrieval; page truth, source independence and semantic support are not independently verified.",
                }
                if existing:
                    existing.update(record)
                    updated += 1
                else:
                    self._records.append(record)
                    by_url[normalized] = record
                    inserted += 1
            self.save()
        return {"inserted": inserted, "updated": updated, "total": self.count()}

    def search(self, query: str, limit: int = 8) -> dict:
        query = str(query or "").strip()
        if not query:
            return {"query": query, "matches": [], "total_records": self.count()}
        query_tokens = _tokens(query)
        scored = []
        with self._lock:
            rows = list(self._records)
        for row in rows:
            searchable = " ".join(str(row.get(key, "")) for key in ("title", "snippet", "query", "provider"))
            tokens = _tokens(searchable)
            overlap = len(query_tokens & tokens)
            if not overlap:
                continue
            score = overlap / max(1, len(query_tokens))
            if query.lower() in searchable.lower():
                score += 0.25
            if row.get("quality_accepted_at_capture"):
                score += 0.05
            scored.append((score, row))
        scored.sort(key=lambda item: (item[0], item[1].get("last_seen_at", "")), reverse=True)
        matches = []
        for score, row in scored[:max(1, min(int(limit), 20))]:
            matches.append({**row, "retrieval_score": round(score, 3)})
        return {"query": query, "matches": matches, "total_records": len(rows)}

    def summary(self) -> dict:
        with self._lock:
            rows = list(self._records)
        return {
            "record_count": len(rows),
            "unique_sources": len({row.get("url") for row in rows if row.get("url")}),
            "last_updated_at": max((row.get("last_seen_at", "") for row in rows), default=None),
            "retrieval": "lexical token and Chinese-bigram overlap",
            "verification_policy": "source-backed excerpts remain unverified until independently reviewed",
            "storage_path_configured": bool(os.getenv("JARVIS_GAME_KNOWLEDGE_PATH")),
        }

    def count(self) -> int:
        with self._lock:
            return len(self._records)
