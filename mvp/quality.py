"""Evidence quality gates for JARVIS v0.6."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvidenceQuality:
    score: float
    accepted: bool
    reasons: list[str]


def score_evidence(evidence: dict) -> EvidenceQuality:
    """Score evidence conservatively and explain the decision.

    Source-backed findings receive credit for provenance; simulated findings
    are retained for demo continuity but never pass the real-research gate.
    """
    reasons: list[str] = []
    score = 0.0

    confidence = float(evidence.get("confidence", 0.0))
    score += min(confidence, 1.0) * 50

    source = evidence.get("source")
    if source and source.get("url"):
        score += 30
    else:
        reasons.append("missing source URL")

    snippet = str((source or {}).get("snippet", "")).strip()
    if snippet:
        score += 10
    else:
        reasons.append("missing source excerpt")

    if evidence.get("simulated", False):
        reasons.append("simulated evidence cannot pass the real-research gate")
        return EvidenceQuality(round(score, 1), False, reasons)

    if confidence < 0.6:
        reasons.append("confidence below 0.60")

    accepted = score >= 70 and confidence >= 0.6 and bool(source and source.get("url"))
    if accepted:
        reasons.append("source, excerpt and confidence thresholds passed")

    return EvidenceQuality(round(score, 1), accepted, reasons)


def evaluate_evidence(evidence: list[dict]) -> dict:
    results = []
    accepted = 0
    for item in evidence:
        quality = score_evidence(item)
        row = dict(item)
        row["quality_score"] = quality.score
        row["quality_accepted"] = quality.accepted
        row["quality_reasons"] = quality.reasons
        results.append(row)
        accepted += int(quality.accepted)

    return {
        "total": len(results),
        "accepted": accepted,
        "rejected": len(results) - accepted,
        "coverage": round(accepted / len(results), 2) if results else 0.0,
        "items": results,
    }
