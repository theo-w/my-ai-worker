"""Provider-neutral synthesis layer for JARVIS v0.6."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class SynthesisResult:
    question: str
    conclusion: str
    supporting_findings: list[str]
    conflicts: list[str]
    confidence: float
    evidence_count: int

    def to_dict(self) -> dict:
        return asdict(self)


def synthesize(question: str, evidence: list[dict]) -> SynthesisResult:
    """Deterministic baseline; an LLM provider can replace this contract."""
    by_worker = defaultdict(list)
    for item in evidence:
        by_worker[item.get("worker", "Unknown")].append(item)

    supporting = [
        str(item.get("finding", "")).strip()
        for item in evidence
        if item.get("quality_accepted") and item.get("finding")
    ]
    conflicts = []
    if len(by_worker) >= 2:
        workers = sorted(by_worker)
        conflicts.append(f"Cross-worker validation required: {', '.join(workers)}")

    confidence = (
        sum(float(item.get("confidence", 0)) for item in evidence) / len(evidence)
        if evidence else 0.0
    )
    conclusion = (
        f"{len(supporting)} source-backed findings support further validation."
        if supporting else
        "Insufficient source-backed evidence for a business conclusion."
    )
    return SynthesisResult(
        question=question, conclusion=conclusion,
        supporting_findings=supporting, conflicts=conflicts,
        confidence=round(confidence, 2), evidence_count=len(evidence),
    )
