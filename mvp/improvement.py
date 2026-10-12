"""Observe-only recursive self-improvement reports.

This module converts recorded task outcomes into bounded improvement proposals.
It never edits plans, retries tasks, changes permissions, or modifies code.
Every proposal requires independent evaluation and human approval before adoption.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import re


def _task_rows(snapshot: dict) -> list[dict]:
    tasks = snapshot.get("tasks", [])
    if isinstance(tasks, dict):
        tasks = list(tasks.values())
    return [task for task in tasks if isinstance(task, dict)] if isinstance(tasks, list) else []


def _normalize_blocker(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    return text[:300]


def build_improvement_report(snapshot: dict, min_samples: int = 2,
                             max_proposals: int = 5) -> dict:
    """Build a deterministic report from an immutable workforce snapshot.

    Repeated exact blocker text is treated as a signal to investigate, not proof
    of a root cause. No proposed change is automatically adopted.
    """
    tasks = _task_rows(snapshot)
    min_samples = max(2, min(int(min_samples), 20))
    max_proposals = max(0, min(int(max_proposals), 10))

    counts = Counter(str(task.get("status", "unknown")) for task in tasks)
    repeated_blockers: dict[str, list[str]] = defaultdict(list)
    retry_task_ids = []
    rejected_task_ids = []
    pending_validation_ids = []
    for task in tasks:
        task_id = str(task.get("id") or task.get("task_id") or "unknown")
        blocker = _normalize_blocker(task.get("blocker"))
        if task.get("status") in {"blocked", "failed"} and blocker:
            repeated_blockers[blocker].append(task_id)
        attempts = task.get("attempts", task.get("attempt", 0))
        if isinstance(attempts, int) and not isinstance(attempts, bool) and attempts >= 2:
            retry_task_ids.append(task_id)
        verification = task.get("verification")
        if (task.get("status") == "blocked"
                or (isinstance(verification, dict) and verification.get("accepted") is False)):
            rejected_task_ids.append(task_id)
        if task.get("status") == "awaiting_validation":
            pending_validation_ids.append(task_id)

    proposals = []
    observations = []
    for blocker, ids in sorted(repeated_blockers.items(), key=lambda item: (-len(item[1]), item[0])):
        if len(ids) < min_samples:
            continue
        observations.append({
            "signal": "repeated_blocker_text",
            "sample_count": len(ids),
            "task_ids": ids[:10],
            "detail": blocker,
            "interpretation": "Repeated text is a diagnostic lead; root cause is not established.",
        })
        proposals.append({
            "id": "investigate-repeated-blocker",
            "title": "Investigate recurring task blocker",
            "hypothesis": "A repeatable source of friction may be affecting multiple tasks.",
            "evidence_task_ids": ids[:10],
            "experiment": "Replay representative tasks against the current baseline and one documented workflow change.",
            "success_metric": "Higher independently accepted task rate without increased cost or safety failures.",
            "adoption": "requires_independent_evaluation_and_human_approval",
        })

    if len(retry_task_ids) >= min_samples:
        observations.append({
            "signal": "repeated_retries",
            "sample_count": len(retry_task_ids),
            "task_ids": retry_task_ids[:10],
            "detail": "Tasks with at least two recorded attempts.",
            "interpretation": "Retry concentration may indicate unclear instructions, unstable dependencies, or incorrect retry policy.",
        })
        proposals.append({
            "id": "evaluate-retry-policy",
            "title": "Evaluate retry and escalation policy",
            "hypothesis": "Some repeated attempts may be avoidable through better triage or escalation.",
            "evidence_task_ids": retry_task_ids[:10],
            "experiment": "Compare current policy with a bounded alternative on replayable failed tasks.",
            "success_metric": "Fewer repeated attempts per accepted task with no reduction in independent acceptance rate.",
            "adoption": "requires_independent_evaluation_and_human_approval",
        })

    if len(rejected_task_ids) >= min_samples:
        observations.append({
            "signal": "rejected_or_blocked_outputs",
            "sample_count": len(rejected_task_ids),
            "task_ids": rejected_task_ids[:10],
            "detail": "Tasks recorded as blocked or with rejected verification.",
            "interpretation": "This does not identify whether the cause is worker output, evidence quality, or verifier policy.",
        })
        proposals.append({
            "id": "evaluate-evidence-contract",
            "title": "Evaluate output and evidence contract",
            "hypothesis": "Clearer output fields or evidence requirements may reduce avoidable validation failures.",
            "evidence_task_ids": rejected_task_ids[:10],
            "experiment": "Replay rejected cases against the current contract and a versioned stricter schema.",
            "success_metric": "Higher independent verification pass rate without more unsupported claims.",
            "adoption": "requires_independent_evaluation_and_human_approval",
        })

    proposals = proposals[:max_proposals]
    return {
        "mode": "observe_only",
        "generated_from": "recorded_workforce_snapshot",
        "metrics": {
            "task_count": len(tasks),
            "status_counts": dict(sorted(counts.items())),
            "blocked_or_failed_count": counts.get("blocked", 0) + counts.get("failed", 0),
            "retry_task_count": len(retry_task_ids),
            "rejected_or_blocked_count": len(rejected_task_ids),
            "awaiting_validation_count": len(pending_validation_ids),
            "verified_truth_count": sum(task.get("verified_truth") is True for task in tasks),
        },
        "observations": observations,
        "proposals": proposals,
        "actions_taken": [],
        "adoption_requires": ["fixed_regression_suite", "independent_evaluation", "human_approval"],
        "truth_claim": "Signals are derived from recorded metadata; they do not prove root cause or factual truth.",
    }
