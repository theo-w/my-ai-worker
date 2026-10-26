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
        from urllib.parse import urlencode, urlsplit
        from urllib.request import Request, urlopen

        limit = max(1, min(int(limit), 10))
        headers = {
            "Accept": "application/json",
            "User-Agent": "JARVIS-ResearchAdapter/1.0",
        }
        host = (urlsplit(self.endpoint).hostname or "").lower()
        if host == "api.tavily.com" or host.endswith(".tavily.com"):
            # Tavily's native API uses POST JSON, not the generic GET contract.
            if not self.api_key:
                raise ValueError("Tavily requires JARVIS_SEARCH_API_KEY.")
            body = json.dumps({
                "api_key": self.api_key,
                "query": query,
                "max_results": limit,
                "search_depth": "basic",
                "include_answer": False,
            }).encode("utf-8")
            headers["Content-Type"] = "application/json"
            request = Request(self.endpoint, data=body, headers=headers, method="POST")
        else:
            url = self.endpoint + ("&" if "?" in self.endpoint else "?") + urlencode({
                "q": query, "limit": limit
            })
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
            # Tavily calls the excerpt field "content"; generic providers often use snippet/description.
            snippet = str(row.get("snippet", row.get("content", row.get("description", "")))).strip()
            if not title or not source_url.startswith("https://") or not snippet:
                continue
            sources.append(ResearchSource(
                title=title, url=source_url, snippet=snippet,
                provider="tavily" if (host == "api.tavily.com" or host.endswith(".tavily.com"))
                         else str(row.get("provider", "json_http")),
                published_at=row.get("published_at", row.get("published_date")),
            ))
        return sources


def research_environment_status() -> dict:
    """Report provider configuration without exposing the API key."""
    import os
    endpoint = os.getenv("JARVIS_SEARCH_ENDPOINT", "").strip()
    configured = bool(endpoint)
    from urllib.parse import urlsplit
    host = (urlsplit(endpoint).hostname or "").lower() if endpoint else ""
    provider = "tavily" if host == "api.tavily.com" or host.endswith(".tavily.com") else ("json_http" if configured else None)
    return {
        "configured": configured,
        "provider": provider,
        "message": "Search provider configured." if configured
                   else "No live search provider configured; real research is unavailable.",
    }


def _synthesize_with_llm(query: str, accepted_items: list[dict]) -> dict:
    """Optional LLM synthesis over accepted, source-backed findings only."""
    import json
    import os
    if os.getenv("JARVIS_LLM_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        return {
            "status": "disabled_by_cost_safety",
            "text": None,
            "source_urls": [],
            "message": "LLM synthesis is disabled by default to avoid test costs; source-backed deterministic results are retained.",
        }
    if not accepted_items:
        return {
            "status": "skipped_no_accepted_evidence",
            "text": None,
            "source_urls": [],
            "message": "LLM synthesis skipped because no evidence passed the quality gate.",
        }
    if not all(os.getenv(key, "").strip() for key in (
        "JARVIS_LLM_BASE_URL", "JARVIS_LLM_API_KEY", "JARVIS_LLM_MODEL"
    )):
        return {
            "status": "not_configured",
            "text": None,
            "source_urls": [],
            "message": "LLM synthesis is not configured; deterministic synthesis is retained.",
        }
    try:
        try:
            from .llm import OpenAICompatibleLLM
        except ImportError:
            from llm import OpenAICompatibleLLM
        client = OpenAICompatibleLLM.from_environment()
        rows = []
        for index, item in enumerate(accepted_items, start=1):
            source = item.get("source") or {}
            rows.append({
                "source_id": "S" + str(index),
                "title": source.get("title"),
                "url": source.get("url"),
                "excerpt": source.get("snippet"),
                "source_role": item.get("source_role", "unclassified"),
                "user_demand_eligible": item.get("user_demand_eligible", False),
                "raw_user_content_available": item.get("raw_user_content_available", False),
                "user_demand_eligibility_reason": item.get("user_demand_eligibility_reason", "not assessed"),
                "finding": item.get("finding"),
                "confidence": item.get("confidence"),
            })
        prompt = {
            "question": query,
            "accepted_source_backed_findings": rows,
            "instructions": [
                "Synthesize only the supplied findings.",
                "Cite claims using the supplied source IDs (for example [S1]).",
                "Never invent URLs, citations, data, or facts not present in the input.",
                "Distinguish evidence from inference and explicitly note gaps or conflicts.",
                "Do not treat secondary_analysis or media/editorial articles as original user demand.",
                "Do not claim original user reviews were collected unless raw_user_content_available and user_demand_eligible are both true.",
                "A search-result excerpt is not the full original review and cannot establish sentiment prevalence or representativeness.",
                "If the evidence is insufficient, say so instead of guessing.",
            ],
        }
        result = client.complete(
            "You are a cautious research analyst. Every factual claim must be traceable "
            "to the supplied source IDs. Do not claim to have browsed or independently "
            "verified pages; only supplied excerpts have been evaluated.",
            json.dumps(prompt, ensure_ascii=False),
        )
        try:
            from .claim_evidence import audit_synthesis
        except ImportError:
            from claim_evidence import audit_synthesis
        citation_audit = audit_synthesis(result, rows)
        return {
            "status": "completed_review_required",
            "text": result,
            "source_urls": [row["url"] for row in rows],
            "model": client.model,
            "citation_audit": citation_audit,
            "factual_release_allowed": False,
            "message": "LLM synthesis is based only on quality-accepted excerpts. Citation IDs and sentence coverage were audited structurally; semantic support and source truth remain unverified.",
        }
    except Exception as exc:
        return {
            "status": "failed",
            "text": None,
            "source_urls": [],
            "error": type(exc).__name__ + ": " + str(exc),
            "message": "LLM synthesis failed; deterministic synthesis remains available.",
        }



def collect_steam_raw_reviews(sources: list[dict], max_reviews_per_app: int = 30) -> tuple[list[dict], list[dict]]:
    """Collect public raw Steam review records for app IDs found in research URLs.

    This collector only runs when a public Steam app ID is discoverable from a
    Steam store URL. It does not infer reviews from media articles or snippets.
    """
    import json
    import re
    from datetime import datetime, timezone
    from urllib.parse import urlparse, urlencode
    from urllib.request import Request, urlopen

    app_ids = []
    for source in sources:
        url = str(source.get("url", ""))
        parsed = urlparse(url)
        if (parsed.hostname or "").lower().removeprefix("www.") != "store.steampowered.com":
            continue
        match = re.match(r"/app/(\d+)(?:/|$)", parsed.path)
        if match and match.group(1) not in app_ids:
            app_ids.append(match.group(1))
    reviews = []
    errors = []
    for app_id in app_ids[:5]:
        endpoint = "https://store.steampowered.com/appreviews/" + app_id + "?" + urlencode({
            "json": 1, "language": "all", "review_type": "all",
            "purchase_type": "all", "num_per_page": min(100, max(1, int(max_reviews_per_app))),
            "filter": "recent",
        })
        try:
            request = Request(endpoint, headers={
                "Accept": "application/json",
                "User-Agent": "JARVIS-ResearchAdapter/1.0",
            })
            with urlopen(request, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
            for row in payload.get("reviews", [])[:max_reviews_per_app]:
                if not isinstance(row, dict):
                    continue
                raw_text = str(row.get("review", "")).strip()
                review_id = str(row.get("recommendationid", "")).strip()
                if not raw_text or not review_id:
                    continue
                created = row.get("timestamp_created")
                created_iso = datetime.fromtimestamp(int(created), timezone.utc).isoformat() if created else None
                reviews.append({
                    "title": "Steam 原始玩家评价 · App " + app_id,
                    "url": endpoint + "&reviewid=" + review_id,
                    "snippet": raw_text[:1200],
                    "raw_review_text": raw_text,
                    "review_id": review_id,
                    "review_created_at": created_iso,
                    "published_at": created_iso,
                    "collection_method": "Steam Store Reviews API",
                    "source_role": "primary_user_signal",
                    "provider": "steam_store_reviews_api",
                    "app_id": app_id,
                    "language": row.get("language"),
                    "recommended": row.get("voted_up"),
                    "votes_up": row.get("votes_up"),
                    "weighted_vote_score": row.get("weighted_vote_score"),
                    "simulated": False,
                })
        except Exception as exc:
            errors.append({"app_id": app_id, "provider": "steam_store_reviews_api", "error": type(exc).__name__})
    return reviews, errors


def run_live_research_batch(queries: list[str], limit_per_query: int = 3, progress_callback: Callable[[dict], None] | None = None) -> dict:
    """Run a bounded multi-angle search, deduplicate sources, then synthesize once.

    This is intended for feasibility work where a single broad query would miss
    competitors, player needs, cost/technical risks, or counter-evidence. Search
    failures are reported per angle; successful partial results are never
    presented as comprehensive coverage.
    """
    import os
    try:
        from .quality import evaluate_evidence
        from .synthesis import synthesize
    except ImportError:
        from quality import evaluate_evidence
        from synthesis import synthesize

    if not isinstance(queries, list):
        return {"ok": False, "status": "invalid_request", "error": "queries must be a list."}
    normalized = []
    for query in queries[:8]:
        if isinstance(query, str) and query.strip():
            normalized.append(query.strip()[:500])
    if not normalized:
        return {"ok": False, "status": "invalid_request", "error": "At least one research query is required."}
    try:
        limit = max(1, min(int(limit_per_query), 5))
    except (TypeError, ValueError):
        limit = 3

    joined_query = " | ".join(normalized)
    endpoint = os.getenv("JARVIS_SEARCH_ENDPOINT", "").strip()
    if not endpoint:
        return {
            "ok": False, "status": "provider_unconfigured", "query": joined_query,
            "queries": normalized, "query_errors": [],
            "message": "No live search provider configured; no real research was performed.",
            "sources": [], "evidence": [], "quality": evaluate_evidence([]),
            "synthesis": synthesize(joined_query, []).to_dict(),
            "llm_synthesis": _synthesize_with_llm(joined_query, []),
        }

    try:
        provider = JsonHttpSearchProvider(
            endpoint=endpoint, api_key=os.getenv("JARVIS_SEARCH_API_KEY") or None
        )
    except Exception as exc:
        return {
            "ok": False, "status": "provider_error", "query": joined_query,
            "queries": normalized, "query_errors": [{"query": "", "error": type(exc).__name__}],
            "sources": [], "evidence": [], "quality": evaluate_evidence([]),
            "synthesis": synthesize(joined_query, []).to_dict(),
            "llm_synthesis": _synthesize_with_llm(joined_query, []),
        }

    source_rows: dict[str, dict] = {}
    query_errors = []
    empty_queries = []
    successful_queries = set()
    for query_index, query in enumerate(normalized, start=1):
        query_error = None
        try:
            found = provider.search(query, limit)
        except Exception as exc:
            found = []
            query_error = type(exc).__name__
            query_errors.append({"query": query, "error": query_error})
        if query_error is None:
            if found:
                successful_queries.add(query)
            else:
                empty_queries.append(query)
            for source in found:
                normalized_url = source.url.split("#", 1)[0].rstrip("/")
                if not normalized_url:
                    continue
                if normalized_url not in source_rows:
                    source_rows[normalized_url] = {
                        **source.to_dict(),
                        "research_queries": [query],
                    }
                elif query not in source_rows[normalized_url]["research_queries"]:
                    source_rows[normalized_url]["research_queries"].append(query)
        if progress_callback is not None:
            try:
                progress_callback({
                    "status": "running",
                    "queries_completed": query_index,
                    "queries_total": len(normalized),
                    "current_query": query,
                    "query_errors": list(query_errors),
                    "sources": list(source_rows.values())[:20],
                    "successful_angles": len(successful_queries),
                    "empty_angles": len(empty_queries),
                    "failed_angles": len(query_errors),
                })
            except Exception:
                # Progress reporting must never interrupt the research task.
                pass

    sources = list(source_rows.values())[:20]
    raw_user_reviews, review_collection_errors = collect_steam_raw_reviews(sources)
    # Keep article/search-result sources and individual original reviews separate.
    sources.extend(raw_user_reviews)
    evidence = [{
        "worker": "Live Research Adapter",
        "finding": source.get("snippet", ""),
        "confidence": 0.75,
        "simulated": False,
        "source": {key: value for key, value in source.items() if key != "research_queries"},
        "research_queries": source.get("research_queries", []),
    } for source in sources]
    quality = evaluate_evidence(evidence)
    accepted = [item for item in quality["items"] if item.get("quality_accepted")]
    deterministic = synthesize(joined_query, accepted)
    llm_synthesis = _synthesize_with_llm(joined_query, accepted)
    if sources:
        status = "completed"
        ok = True
    elif query_errors:
        status = "provider_error"
        ok = False
    else:
        status = "no_results"
        ok = False
    return {
        "ok": ok, "status": status, "query": joined_query, "queries": normalized,
        "query_errors": query_errors, "sources": sources, "evidence": quality["items"],
        "review_collection": {
            "provider": "steam_store_reviews_api",
            "raw_review_records": len(raw_user_reviews),
            "errors": review_collection_errors,
            "note": "Raw Steam review collection only runs when a Steam app ID is found in search results; no records means no original reviews were collected from this adapter.",
        },
        "quality": quality, "synthesis": deterministic.to_dict(),
        "llm_synthesis": llm_synthesis,
        "coverage": {
            "requested_angles": len(normalized),
            "successful_angles": len(successful_queries),
            "empty_angles": len(empty_queries),
            "failed_angles": len(query_errors),
            "distinct_sources": len(sources),
            "accepted_evidence": quality.get("accepted", 0),
            "comprehensive": bool(sources) and not query_errors and not empty_queries,
        },
    }


def run_live_research(query: str, limit: int = 5) -> dict:
    """Search configured provider, deduplicate, quality-gate and optionally synthesize."""
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
        return {
            "ok": False, "status": "provider_unconfigured",
            "message": "No live search provider configured; no real research was performed.",
            "sources": [], "evidence": [], "quality": evaluate_evidence([]),
            "synthesis": synthesize(query, []).to_dict(),
            "llm_synthesis": _synthesize_with_llm(query, []),
        }
    try:
        provider = JsonHttpSearchProvider(
            endpoint=endpoint, api_key=os.getenv("JARVIS_SEARCH_API_KEY") or None
        )
        found = provider.search(query, limit)
        sources = []
        seen = set()
        for source in found:
            normalized_url = source.url.split("#", 1)[0].rstrip("/")
            if normalized_url in seen:
                continue
            seen.add(normalized_url)
            sources.append(source)
        evidence = [{
            "worker": "Live Research Adapter",
            "finding": source.snippet,
            "confidence": 0.75,
            "simulated": False,
            "source": source.to_dict(),
        } for source in sources]
        quality = evaluate_evidence(evidence)
        deterministic = synthesize(query, quality["items"])
        llm_synthesis = _synthesize_with_llm(
            query, [item for item in quality["items"] if item.get("quality_accepted")]
        )
        return {
            "ok": bool(sources),
            "status": "completed" if sources else "no_results",
            "query": query,
            "sources": [source.to_dict() for source in sources],
            "evidence": quality["items"],
            "quality": quality,
            "synthesis": deterministic.to_dict(),
            "llm_synthesis": llm_synthesis,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "provider_error",
            "error": type(exc).__name__ + ": " + str(exc),
            "query": query,
            "sources": [], "evidence": [], "quality": evaluate_evidence([]),
            "synthesis": synthesize(query, []).to_dict(),
            "llm_synthesis": _synthesize_with_llm(query, []),
        }
