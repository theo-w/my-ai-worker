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



class JsonHttpSearchProvider:
    """Adapter for search APIs that return JSON.

    Configure an endpoint and optional bearer token through environment
    variables JARVIS_SEARCH_ENDPOINT and JARVIS_SEARCH_API_KEY. The endpoint
    must accept ?q=<query>&limit=<n> and return either a list of results or
    {"results": [{"title": ..., "url": ..., "snippet": ..., "published_at": ...}]}.
    This generic adapter does not assume a particular vendor schema beyond
    that small response contract.
    """
    def __init__(self, endpoint: str, api_key: str | None = None, timeout: float = 10.0):
        self.endpoint = endpoint.strip()
        self.api_key = api_key
        self.timeout = max(1.0, float(timeout))
        if not self.endpoint.startswith("https://"):
            raise ValueError("Search endpoint must use HTTPS.")

    def search(self, query: str, limit: int = 5) -> list[ResearchSource]:
        import json
        from urllib.parse import urlencode
        from urllib.request import Request, urlopen

        limit = max(1, min(int(limit), 10))
        url = self.endpoint + ("&" if "?" in self.endpoint else "?") + urlencode({
            "q": query, "limit": limit
        })
        headers = {"Accept": "application/json", "User-Agent": "JARVIS-ResearchAdapter/1.0"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=self.timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError("Search provider returned HTTP " + str(response.status))
            payload = json.loads(response.read().decode("utf-8"))

        rows = payload.get("results", []) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("Search provider response must be a list or contain a results list.")
        sources = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title", "")).strip()
            source_url = str(row.get("url", "")).strip()
            snippet = str(row.get("snippet", row.get("description", ""))).strip()
            if not title or not source_url.startswith("https://") or not snippet:
                continue
            sources.append(ResearchSource(
                title=title, url=source_url, snippet=snippet,
                provider=str(row.get("provider", "json_http")),
                published_at=row.get("published_at"),
            ))
        return sources


def research_environment_status() -> dict:
    """Report provider configuration without exposing the API key."""
    import os
    endpoint = os.getenv("JARVIS_SEARCH_ENDPOINT", "").strip()
    configured = bool(endpoint)
    return {
        "configured": configured,
        "provider": "json_http" if configured else None,
        "message": "Search provider configured." if configured
                   else "No live search provider configured; real research is unavailable.",
    }


def run_live_research(query: str, limit: int = 5) -> dict:
    """Run configured provider, quality-gate results, then synthesize."""
    import os
    try:
        from .quality import evaluate_evidence
        from .synthesis import synthesize
    except ImportError:  # Direct-script compatibility
        from quality import evaluate_evidence
        from synthesis import synthesize

    query = str(query).strip()
    if not query:
        return {"ok": False, "status": "invalid_request", "error": "A research query is required."}
    endpoint = os.getenv("JARVIS_SEARCH_ENDPOINT", "").strip()
    if not endpoint:
        return {"ok": False, "status": "provider_unconfigured", "message": "No live search provider configured; no real research was performed.", "sources": [], "evidence": [], "quality": evaluate_evidence([]), "synthesis": synthesize(query, []).to_dict()}
    try:
        provider = JsonHttpSearchProvider(endpoint=endpoint, api_key=os.getenv("JARVIS_SEARCH_API_KEY") or None)
        sources = provider.search(query, limit)
        evidence = [{"worker": "Live Research Adapter", "finding": source.snippet, "confidence": 0.75, "simulated": False, "source": source.to_dict()} for source in sources]
        quality = evaluate_evidence(evidence)
        synthesis = synthesize(query, quality["items"])
        return {"ok": bool(sources), "status": "completed" if sources else "no_results", "query": query, "sources": [source.to_dict() for source in sources], "evidence": quality["items"], "quality": quality, "synthesis": synthesis.to_dict()}
    except Exception as exc:
        return {"ok": False, "status": "provider_error", "error": type(exc).__name__ + ": " + str(exc), "query": query, "sources": [], "evidence": [], "quality": evaluate_evidence([]), "synthesis": synthesize(query, []).to_dict()}
