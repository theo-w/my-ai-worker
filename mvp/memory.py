#!/usr/bin/env python3
"""Persistent, provider-neutral memory for the Digital Twin.

The MVP deliberately keeps memory simple: a local JSON document with
structured memories and decision history. A future production adapter can
replace the storage layer without changing the Digital Twin contract.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryEntry:
    kind: str
    content: str
    importance: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)


@dataclass
class DecisionRecord:
    goal: str
    recommendation: str
    confidence: int
    risks: list[str] = field(default_factory=list)
    next_step: str = ""
    rationale: str = ""
    created_at: str = field(default_factory=_now)


class TwinMemory:
    """Small persistent memory store for a Digital Twin."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.memories: list[MemoryEntry] = []
        self.decisions: list[DecisionRecord] = []
        if self.path and self.path.exists():
            self.load()

    def remember(
        self,
        content: str,
        *,
        kind: str = "fact",
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            kind=kind,
            content=content,
            importance=max(0.0, min(1.0, importance)),
            metadata=metadata or {},
        )
        self.memories.append(entry)
        self.save()
        return entry

    def record_decision(self, decision: DecisionRecord) -> DecisionRecord:
        self.decisions.append(decision)
        self.save()
        return decision

    def recall(self, query: str = "", limit: int = 8) -> list[MemoryEntry]:
        items = self.memories
        if query.strip():
            terms = query.lower().split()
            items = [
                item for item in items
                if all(term in (item.content + " " + item.kind).lower() for term in terms)
            ]
        return sorted(
            items,
            key=lambda item: (item.importance, item.created_at),
            reverse=True,
        )[:limit]

    def recent_decisions(self, limit: int = 8) -> list[DecisionRecord]:
        return list(reversed(self.decisions[-limit:]))

    def snapshot(self, limit: int = 5) -> dict[str, Any]:
        return {
            "memory_count": len(self.memories),
            "decision_count": len(self.decisions),
            "recent_memories": [asdict(x) for x in self.recall(limit=limit)],
            "recent_decisions": [asdict(x) for x in self.recent_decisions(limit=limit)],
        }

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "memories": [asdict(x) for x in self.memories],
            "decisions": [asdict(x) for x in self.decisions],
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.memories = [MemoryEntry(**x) for x in payload.get("memories", [])]
        self.decisions = [DecisionRecord(**x) for x in payload.get("decisions", [])]
