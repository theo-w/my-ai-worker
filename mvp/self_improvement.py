"""Guarded recursive-improvement primitives for the JARVIS MVP.

This module records lessons and evaluates proposed policy changes. It deliberately
does not rewrite source code, grant new permissions, or deploy changes automatically.
A proposal must pass a repeatable evaluation gate before a human/operator can promote it.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


DEFAULT_MAX_ITERATIONS = 3


def summarize_outcomes(outcomes: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Summarize observed runs without treating model-written claims as ground truth.

    Each outcome should contain status and may contain failure_category,
    verified and provenance. Only explicitly verified outcomes contribute
    to the verified-success count.
    """
    items = list(outcomes)
    categories = Counter(
        str(item.get("failure_category") or "unspecified")
        for item in items
        if item.get("status") in {"failed", "blocked", "rejected"}
    )
    verified_successes = sum(
        1 for item in items
        if item.get("status") == "completed" and item.get("verified") is True
    )
    simulated = sum(1 for item in items if item.get("provenance") == "simulated")
    return {
        "sample_count": len(items),
        "verified_successes": verified_successes,
        "failure_categories": dict(categories),
        "simulated_count": simulated,
        "lesson_quality": "observed_only" if items else "no_data",
    }


def evaluate_improvement(
    proposal: dict[str, Any],
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    iteration: int = 1,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    min_samples: int = 3,
    min_gain: float = 0.02,
) -> dict[str, Any]:
    """Gate a candidate policy using comparable benchmark metrics.

    score is in [0, 1], regressions is the number of benchmark cases
    that regressed, and sample_count is the number of comparable cases.
    The function returns a decision record; it never applies the proposal.
    """
    reasons: list[str] = []
    if not isinstance(proposal, dict) or not str(proposal.get("hypothesis", "")).strip():
        reasons.append("missing_hypothesis")
    if iteration < 1 or max_iterations < 1 or iteration > max_iterations:
        reasons.append("iteration_budget_exceeded")
    if not isinstance(baseline, dict) or not isinstance(candidate, dict):
        reasons.append("invalid_metrics")
        baseline = baseline if isinstance(baseline, dict) else {}
        candidate = candidate if isinstance(candidate, dict) else {}

    def valid_score(metrics: dict[str, Any]) -> bool:
        value = metrics.get("score")
        return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1

    if not valid_score(baseline) or not valid_score(candidate):
        reasons.append("score_must_be_between_0_and_1")
    sample_count = candidate.get("sample_count", 0)
    if not isinstance(sample_count, int) or isinstance(sample_count, bool) or sample_count < min_samples:
        reasons.append("insufficient_evaluation_samples")
        sample_count = sample_count if isinstance(sample_count, int) and not isinstance(sample_count, bool) else 0
    regressions = candidate.get("regressions", 0)
    if not isinstance(regressions, int) or isinstance(regressions, bool) or regressions < 0:
        reasons.append("invalid_regression_count")
        regressions = 0
    if valid_score(baseline) and valid_score(candidate):
        gain = float(candidate["score"]) - float(baseline["score"])
        if gain < min_gain:
            reasons.append("improvement_below_threshold")
    else:
        gain = None
    if regressions:
        reasons.append("benchmark_regressions_detected")

    accepted = not reasons
    return {
        "accepted": accepted,
        "decision": "eligible_for_review" if accepted else "rejected",
        "iteration": iteration,
        "max_iterations": max_iterations,
        "hypothesis": str(proposal.get("hypothesis", ""))[:1000] if isinstance(proposal, dict) else "",
        "baseline_score": baseline.get("score"),
        "candidate_score": candidate.get("score"),
        "gain": gain,
        "sample_count": sample_count,
        "regressions": regressions,
        "reasons": reasons,
        "auto_applied": False,
        "requires_human_promotion": accepted,
    }
