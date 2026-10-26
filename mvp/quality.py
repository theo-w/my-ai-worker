"""Evidence quality gates for JARVIS v0.7.

Mechanical source checks are not truth verification. This module separately labels
source role and reports whether the evidence mix can support a user-demand claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

try:
    from .accuracy import validate_source_record
except ImportError:  # Direct-script compatibility
    from accuracy import validate_source_record


PRIMARY_USER_HOSTS = {
    "reddit.com", "old.reddit.com", "steamcommunity.com", "steamcommunity",
    "discord.com", "forums.ea.com", "community.playstation.com",
    "community.xbox.com", "itch.io", "store.steampowered.com",
    "play.google.com", "apps.apple.com", "trustpilot.com",
}
SECONDARY_ANALYSIS_HOSTS = {
    "medium.com", "substack.com", "gamasutra.com", "gamedeveloper.com",
    "ign.com", "gamespot.com", "pcgamer.com", "polygon.com",
    "rockpapershotgun.com", "eurogamer.net", "youtube.com", "youtu.be",
}
OFFICIAL_HOST_HINTS = (
    "official", "support.", "help.", "ir.", "investor.", "developer.",
    "newsroom.", "press.",
)


@dataclass
class EvidenceQuality:
    score: float
    accepted: bool
    reasons: list[str]


def classify_source_role(source: dict | None) -> dict:
    """Classify likely source role conservatively; this is a heuristic, not proof."""
    source = source if isinstance(source, dict) else {}
    explicit = str(source.get("source_role", source.get("source_type", ""))).strip().lower()
    aliases = {
        "user": "primary_user_signal", "user_signal": "primary_user_signal",
        "primary": "primary_user_signal", "review": "primary_user_signal",
        "forum": "primary_user_signal", "ugc": "primary_user_signal",
        "analysis": "secondary_analysis", "article": "secondary_analysis",
        "editorial": "secondary_analysis", "official": "official_or_industry_data",
        "industry_data": "official_or_industry_data",
    }
    if explicit:
        role = aliases.get(explicit, explicit)
        if role in {"primary_user_signal", "secondary_analysis", "official_or_industry_data"}:
            return {"source_role": role, "role_basis": "explicit source metadata", "role_is_heuristic": False}

    url = str(source.get("url", "")).strip()
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    path = parsed.path.lower()
    if host in PRIMARY_USER_HOSTS or any(host.endswith("." + domain) for domain in PRIMARY_USER_HOSTS):
        # A platform may host official announcements as well as user posts.
        if host == "store.steampowered.com" and "/app/" in path and "/reviews/" not in path:
            return {"source_role": "official_or_industry_data", "role_basis": "store/product page; not a direct user statement", "role_is_heuristic": True}
        return {"source_role": "primary_user_signal", "role_basis": "user-review/community platform inferred from domain", "role_is_heuristic": True}
    if host in SECONDARY_ANALYSIS_HOSTS or any(host.endswith("." + domain) for domain in SECONDARY_ANALYSIS_HOSTS):
        return {"source_role": "secondary_analysis", "role_basis": "editorial/media platform inferred from domain", "role_is_heuristic": True}
    if any(hint in host for hint in OFFICIAL_HOST_HINTS):
        return {"source_role": "official_or_industry_data", "role_basis": "official/data-oriented host pattern; verify the specific claim", "role_is_heuristic": True}
    return {
        "source_role": "unclassified",
        "role_basis": "source role cannot be inferred safely; do not treat as direct user demand",
        "role_is_heuristic": True,
    }


def score_evidence(evidence: dict) -> EvidenceQuality:
    """Score provenance completeness; acceptance does not mean factual truth."""
    reasons: list[str] = []
    score = 0.0
    try:
        confidence = max(0.0, min(float(evidence.get("confidence", 0.0)), 1.0))
    except (TypeError, ValueError):
        confidence = 0.0
        reasons.append("invalid confidence value")
    score += confidence * 50

    source = evidence.get("source")
    source_valid = False
    if isinstance(source, dict):
        source_valid, source_reasons = validate_source_record(source)
        if source_valid:
            score += 30
        else:
            reasons.extend(source_reasons)
    else:
        reasons.append("missing source record")

    snippet = str((source or {}).get("snippet", (source or {}).get("description", ""))).strip() if isinstance(source, dict) else ""
    if snippet:
        score += 10
    else:
        reasons.append("missing source excerpt")

    role = classify_source_role(source)
    if role["source_role"] == "unclassified":
        reasons.append("source role unclassified; cannot count as direct user-demand evidence")

    if evidence.get("simulated", False):
        reasons.append("simulated evidence cannot pass the real-research gate")
        return EvidenceQuality(round(score, 1), False, reasons)

    if confidence < 0.6:
        reasons.append("confidence below 0.60")

    accepted = score >= 70 and confidence >= 0.6 and source_valid
    if accepted:
        reasons.append("mechanical provenance threshold passed; truth and claim relevance remain unverified")

    return EvidenceQuality(round(score, 1), accepted, reasons)


def evaluate_evidence(evidence: list[dict]) -> dict:
    results = []
    accepted = 0
    role_counts = {
        "primary_user_signal": 0,
        "secondary_analysis": 0,
        "official_or_industry_data": 0,
        "unclassified": 0,
    }
    accepted_role_counts = dict(role_counts)
    for item in evidence:
        source = item.get("source") if isinstance(item, dict) else None
        role = classify_source_role(source)
        quality = score_evidence(item)
        row = dict(item)
        row.update(role)
        row["quality_score"] = quality.score
        row["quality_accepted"] = quality.accepted
        row["quality_reasons"] = quality.reasons
        results.append(row)
        role_counts[role["source_role"]] = role_counts.get(role["source_role"], 0) + 1
        if quality.accepted:
            accepted += 1
            accepted_role_counts[role["source_role"]] = accepted_role_counts.get(role["source_role"], 0) + 1

    user_signal_count = accepted_role_counts["primary_user_signal"]
    secondary_count = accepted_role_counts["secondary_analysis"]
    official_count = accepted_role_counts["official_or_industry_data"]
    # This is an evidence sufficiency warning, not a claim that the evidence is true.
    if user_signal_count == 0:
        decision_readiness = "insufficient_user_demand_evidence"
        readiness_reasons = ["No mechanically accepted direct user/community signal was identified."]
    elif user_signal_count < 3:
        decision_readiness = "limited_user_demand_evidence"
        readiness_reasons = ["Fewer than three accepted direct user/community signals; sample breadth is weak."]
    else:
        decision_readiness = "user_signal_available_needs_validation"
        readiness_reasons = ["User/community signals exist, but representativeness, duplication, context and claim-level support still require validation."]
    return {
        "total": len(results),
        "accepted": accepted,
        "rejected": len(results) - accepted,
        "coverage": round(accepted / len(results), 2) if results else 0.0,
        "source_role_counts": role_counts,
        "accepted_source_role_counts": accepted_role_counts,
        "decision_readiness": decision_readiness,
        "readiness_reasons": readiness_reasons,
        "truth_verified": False,
        "note": "quality_accepted means mechanical provenance checks passed only; it does not prove truth, objectivity, representativeness, or claim relevance.",
        "items": results,
    }
