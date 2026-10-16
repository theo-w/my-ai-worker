from mvp.revision_policy import ConservativeTransientRetryPolicy


def test_policy_retries_recognized_transient_failure_with_budget():
    policy = ConservativeTransientRetryPolicy()
    result = policy("goal", [{
        "task_id": "task-1",
        "status": "blocked",
        "blocker": "RuntimeError: source temporarily unavailable",
        "attempts": 1,
        "max_attempts": 3,
    }], 1)
    assert len(result["retry"]) == 1
    assert result["retry"][0]["task_id"] == "task-1"
    assert "configured attempt limit" in result["retry"][0]["reason"]


def test_policy_does_not_retry_permanent_or_unbounded_failures():
    policy = ConservativeTransientRetryPolicy()
    result = policy("goal", [
        {
            "task_id": "permanent",
            "status": "blocked",
            "blocker": "Permission denied",
            "attempts": 1,
            "max_attempts": 3,
        },
        {
            "task_id": "exhausted",
            "status": "failed",
            "blocker": "HTTP 503 temporarily unavailable",
            "attempts": 3,
            "max_attempts": 3,
        },
        {
            "task_id": "missing-budget",
            "status": "blocked",
            "blocker": "Connection reset",
            "attempts": 1,
        },
        {
            "task_id": "still-running",
            "status": "assigned",
            "blocker": "HTTP 503 temporarily unavailable",
            "attempts": 1,
            "max_attempts": 3,
        },
    ], 2)
    assert result == {"retry": []}
