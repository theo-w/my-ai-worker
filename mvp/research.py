"""Research adapters for the JARVIS v0.6 MVP.

The adapter boundary keeps real web research separate from Worker orchestration.
When no external search provider is configured, callers can use the explicit
simulated fallback without presenting it as real research.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable


@dataclass
class ResearchSource:
    title: str
    url: str
    snippet: str
    provider: str = "unknown"
    published_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResearchFinding:
    worker: str
    finding: str
    confidence: float
    source: ResearchSource | None = None
    simulated: bool = False

    def to_dict(self) -> dict:
        data = asdict(self)
        data["source"] = self.source.to_dict() if self.source else None
        return data


SearchFn = Callable[[str, int], list[ResearchSource]]


class ResearchAdapter:
    """Small provider-neutral research boundary.

    A provider only needs to implement search(query, limit) -> sources.
    This makes web search, a future connector, or a self-hosted crawler
    interchangeable without changing Worker or Digital Twin code.
    """

    def __init__(self, search: SearchFn | None = None):
        self.search = search

    @property
    def available(self) -> bool:
        return self.search is not None

    def search_sources(self, query: str, limit: int = 5) -> list[ResearchSource]:
        if not self.search:
            return []
        return self.search(query, limit)


def build_finding(
    worker: str,
    finding: str,
    confidence: float,
    source: ResearchSource | None = None,
    simulated: bool = False,
) -> ResearchFinding:
    return ResearchFinding(
        worker=worker,
        finding=finding,
        confidence=max(0.0, min(1.0, confidence)),
        source=source,
        simulated=simulated,
    )
