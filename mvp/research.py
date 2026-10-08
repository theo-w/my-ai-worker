#!/usr/bin/env python3
"""Lightweight web research adapter with an optional LLM synthesis layer."""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html import unescape
from typing import Any


@dataclass
class Source:
    title: str
    url: str
    snippet: str
    query: str


@dataclass
class ResearchEvidence:
    worker: str
    finding: str
    confidence: float
    source_url: str
    source_title: str
    query: str
    quality_score: float
    quality_reasons: list[str]
    simulated: bool = False


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def search_web(query: str, limit: int = 4, timeout: int = 8) -> list[Source]:
    """Use DuckDuckGo's public HTML endpoint; no SDK or API key required."""
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "JARVIS-Digital-Workforce/0.6"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="ignore")

    blocks = re.findall(r'<div[^>]+class="result[^"]*"[^>]*>(.*?)</div>\s*</div>', html, flags=re.S)
    results: list[Source] = []
    for block in blocks:
        link = re.search(r'class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.S)
        snippet = re.search(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', block, flags=re.S)
        if not link:
            continue
        href = unescape(link.group(1))
        title = _clean(link.group(2))
        text = _clean(snippet.group(1) if snippet else "")
        if href.startswith("//"):
            href = "https:" + href
        if href.startswith("http"):
            results.append(Source(title, href, text, query))
        if len(results) >= limit:
            break
    return results


def quality_gate(source: Source) -> tuple[float, list[str]]:
    score = 0.45
    reasons = ["source URL is available"]
    host = urllib.parse.urlparse(source.url).netloc.lower()
    trusted = (
        ".gov", ".edu", "reuters.com", "bloomberg.com", "nytimes.com",
        "theverge.com", "gdcvault.com", "steamcommunity.com", "steampowered.com",
    )
    if any(host.endswith(x) for x in trusted):
        score += 0.25
        reasons.append("recognized high-value domain")
    if len(source.snippet) >= 80:
        score += 0.15
        reasons.append("substantive source snippet")
    if len(source.title) >= 12:
        score += 0.10
        reasons.append("descriptive source title")
    if host:
        score += 0.05
        reasons.append("source domain is identifiable")
    return min(score, 1.0), reasons


def _llm_config() -> tuple[str, str, str] | None:
    base = os.getenv("LLM_BASE_URL", "").rstrip("/")
    key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "")
    if not (base and key and model):
        return None
    return base, key, model


def synthesize(worker: str, query: str, sources: list[Source]) -> str:
    """Synthesize source snippets when an OpenAI-compatible endpoint is configured."""
    config = _llm_config()
    if not sources:
        return "No web evidence returned for this research query."

    if not config:
        joined = " ".join(s.snippet for s in sources if s.snippet)
        return (joined[:420] + ("…" if len(joined) > 420 else "")) or sources[0].title

    base, key, model = config
    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {
                "role": "system",
                "content": "Synthesize only the supplied source snippets. Do not invent facts. Return one concise business finding.",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"worker": worker, "query": query, "sources": [s.__dict__ for s in sources]},
                    ensure_ascii=False,
                ),
            },
        ],
    }
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode())
        return str(data["choices"][0]["message"]["content"]).strip()
    except Exception:
        return synthesize(worker, query, sources[:1]) if len(sources) > 1 else sources[0].snippet


def research_worker(worker: str, capability: str, goal: str) -> list[ResearchEvidence]:
    query_map = {
        "game_market_research": f"AI native games market {goal}",
        "player_research": f"players AI NPC persistent memory game reactions {goal}",
        "game_ai_technology_feasibility": f"LLM NPC memory latency inference cost games {goal}",
        "ai_gameplay_feasibility": f"AI native game mechanics NPC relationships player retention {goal}",
    }
    query = query_map.get(capability, goal)
    try:
        sources = search_web(query)
    except Exception:
        sources = []

    if not sources:
        return []

    finding = synthesize(worker, query, sources)
    items: list[ResearchEvidence] = []
    for source in sources[:3]:
        score, reasons = quality_gate(source)
        items.append(
            ResearchEvidence(
                worker=worker,
                finding=finding,
                confidence=score,
                source_url=source.url,
                source_title=source.title,
                query=query,
                quality_score=score,
                quality_reasons=reasons,
            )
        )
    return items
