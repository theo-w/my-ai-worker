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
        """Deduplicate by source URL; retain stable text and emit history for material changes."""
        accepted_urls = {
            str((item.get("source") or {}).get("url", "")).split("#", 1)[0].rstrip("/")
            for item in (evidence or [])
            if item.get("quality_accepted") and isinstance(item.get("source"), dict)
        }
        inserted = 0
        updated = 0
        unchanged = 0
        changes = []
        now = _now()
        query_text = str(query or "")[:2000]
        query_tokens = sorted(_tokens(query_text))
        topic_key = hashlib.sha256(" ".join(query_tokens).encode("utf-8")).hexdigest()[:24]
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
                if not existing:
                    record = {
                        "id": hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16],
                        "title": title[:500], "url": normalized, "snippet": snippet[:4000],
                        "query": query_text, "provider": str(source.get("provider", "unknown"))[:100],
                        "published_at": source.get("published_at"), "first_seen_at": now,
                        "last_seen_at": now, "seen_count": 1,
                        "quality_accepted_at_capture": quality_accepted,
                        "knowledge_status": "source_backed_unverified",
                        "verification_note": "Search excerpt retained for retrieval; page truth, source independence and semantic support are not independently verified.",
                    }
                    self._records.append(record)
                    by_url[normalized] = record
                    inserted += 1
                    continue

                old_title = str(existing.get("title", ""))
                old_snippet = str(existing.get("snippet", ""))
                old_tokens = _tokens(old_title + " " + old_snippet)
                new_tokens = _tokens(title + " " + snippet)
                similarity = len(old_tokens & new_tokens) / max(1, len(old_tokens | new_tokens))
                materially_changed = similarity < 0.72 or (
                    bool(existing.get("published_at")) and bool(source.get("published_at"))
                    and str(existing.get("published_at")) != str(source.get("published_at"))
                    and similarity < 0.88
                )
                existing["last_seen_at"] = now
                existing["seen_count"] = int(existing.get("seen_count", 0)) + 1
                existing["last_checked_query"] = query_text
                existing["last_check_status"] = "material_change" if materially_changed else "no_material_change"
                # Preserve the original topic/query association and stable content on routine recrawls.
                if materially_changed:
                    changes.append({
                        "id": hashlib.sha256((existing["id"] + now + old_snippet + snippet).encode("utf-8")).hexdigest()[:32],
                        "source_id": existing["id"], "topic_key": topic_key, "query": query_text,
                        "change_type": "material_source_update", "old_title": old_title,
                        "new_title": title[:500], "old_snippet": old_snippet,
                        "new_snippet": snippet[:4000], "source_url": normalized,
                        "detected_at": now,
                        "reason": "Title/snippet token overlap fell below the material-change threshold; review evidence before changing any synthesized conclusion.",
                    })
                    existing.update({
                        "title": title[:500], "snippet": snippet[:4000],
                        "provider": str(source.get("provider", "unknown"))[:100],
                        "published_at": source.get("published_at"),
                        "query": query_text,
                        "quality_accepted_at_capture": quality_accepted,
                        "knowledge_status": "source_backed_unverified",
                        "verification_note": "Material source change detected; the new excerpt is still unverified and must not alone be treated as a confirmed fact.",
                    })
                    updated += 1
                else:
                    # Refresh metadata only; don't rewrite stable knowledge with equivalent snippets.
                    existing["quality_accepted_at_capture"] = bool(existing.get("quality_accepted_at_capture") or quality_accepted)
                    unchanged += 1
            self.save()
        return {
            "inserted": inserted, "updated": updated, "unchanged": unchanged,
            "changes": changes, "topic_key": topic_key, "total": self.count(),
        }

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
