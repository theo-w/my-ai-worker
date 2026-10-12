"""Opt-in deterministic recovery policy for known transient worker failures.

This policy does not use an LLM and does not change plans. It only proposes a
bounded retry for explicitly recognized transient failures; the workforce API
still validates task state, task scope, and retry limits.
"""
from __future__ import annotations


class ConservativeTransientRetryPolicy:
    """Recommend retries only for known transient error markers."""

    TRANSIENT_MARKERS = (
        "timed out",
        "timeout",
        "temporarily unavailable",
        "temporary outage",
        "connection reset",
        "connection refused",
        "rate limit",
        "http 429",
        "http 502",
        "http 503",
        "http 504",
        "upstream unavailable",
    )

    def __call__(self, goal: str, tasks: list[dict], cycle: int) -> dict:
        del goal, cycle
        retries = []
        for task in tasks:
            if task.get("status") not in {"blocked", "failed"}:
                continue
            attempts = task.get("attempts")
            maximum = task.get("max_attempts")
            if not isinstance(attempts, int) or not isinstance(maximum, int):
                continue
            if attempts >= maximum:
                continue
            blocker = str(task.get("blocker") or "").strip()
            lowered = blocker.lower()
            if not blocker or not any(marker in lowered for marker in self.TRANSIENT_MARKERS):
                continue
            retries.append({
                "task_id": task.get("task_id"),
                "reason": (
                    "Conservative policy matched a known transient failure; "
                    "retry is within the configured attempt limit. Original blocker: "
                    + blocker[:400]
                ),
            })
        return {"retry": retries}
