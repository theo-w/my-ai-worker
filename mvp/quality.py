#!/usr/bin/env python3
"""Evidence quality gate for JARVIS research outputs."""
from __future__ import annotations

from collections import defaultdict


def gate(evidence: list[object]) -> dict:
    if not evidence:
        return {
            "status": "BLOCKED",
            "score": 0,
            "accepted": 0,
            "rejected": 0,
            "reasons": ["No research evidence was returned."],
        }

    seen: set[tuple[str, str]] = set()
    accepted = []
    rejected = []
    for item in evidence:
        url = str(getattr(item, "source_url", ""))
        finding = str(getattr(item, "finding", ""))
        score = float(getattr(item, "quality_score", getattr(item, "confidence", 0)))
        key = (url, finding[:120])
        if not url or score < 0.55 or key in seen:
            rejected.append(item)
            continue
        seen.add(key)
        accepted.append(item)

    worker_counts = defaultdict(int)
    for item in accepted:
        worker_counts[getattr(item, "worker", "unknown")] += 1

    score = round(sum(float(getattr(x, "quality_score", 0)) for x in accepted) / max(len(accepted), 1) * 100)
    status = "PASS" if len(accepted) >= 3 and score >= 60 else "REVIEW"
    reasons = [
        f"{len(accepted)} evidence items passed the source-quality threshold.",
        f"{len(worker_counts)} worker perspectives contributed accepted evidence.",
    ]
    if status != "PASS":
        reasons.append("Decision confidence should remain constrained until evidence coverage improves.")

    return {
        "status": status,
        "score": score,
        "accepted": len(accepted),
        "rejected": len(rejected),
        "reasons": reasons,
    }
