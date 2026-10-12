from datetime import datetime, timedelta, timezone

import pytest

from mvp.workforce import WorkforceRegistry


def test_worker_claims_reports_and_twin_receives_feedback(tmp_path):
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"))
    task = registry.create_task("Build a prototype", capability="implementation", priority=5)
    claimed = registry.claim("worker-a", ["implementation"])
    assert claimed["id"] == task["id"]
    assert claimed["lease_token"]
    assert claimed["status"] == "assigned"

    registry.feedback(task["id"], "digital-twin", "Please include a test report", "correction")
    result = registry.report(task["id"], "worker-a", "completed", output="Prototype + tests", lease_token=claimed["lease_token"])
    assert result["status"] == "completed"
    assert result["output"] == "Prototype + tests"
    assert result["feedback"][0]["actor"] == "digital-twin"
    assert registry.snapshot()["counts"]["completed"] == 1


def test_worker_cannot_report_another_workers_task(tmp_path):
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"))
    task = registry.create_task("Research", capability="research")
    claimed = registry.claim("worker-a", ["research"])
    with pytest.raises(ValueError, match="not leased"):
        registry.report(task["id"], "worker-b", "completed", output="forged", lease_token=claimed["lease_token"])


def test_approval_gate_prevents_claim_until_approved(tmp_path):
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"))
    task = registry.create_task("Release", approval_required=True)
    assert registry.claim("worker-a") is None
    registry.approve_task(task["id"])
    assert registry.claim("worker-a")["id"] == task["id"]


def test_persistent_queue_survives_restart_and_keeps_blocked_for_triage(tmp_path):
    path = str(tmp_path / "workforce.json")
    first = WorkforceRegistry(path=path, max_attempts=2)
    task = first.create_task("Run tests", capability="testing")
    claimed = first.claim("worker-a", ["testing"])
    first.report(task["id"], "worker-a", "blocked", blocker="Missing dependency", lease_token=claimed["lease_token"])

    restarted = WorkforceRegistry(path=path, max_attempts=2)
    assert restarted.snapshot()["tasks"][0]["status"] == "blocked"
    assert restarted.claim("worker-b", ["testing"]) is None


def test_expired_lease_rejects_late_report_and_requeues_task(tmp_path):
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"), max_attempts=2)
    task = registry.create_task("Run tests", capability="testing")
    claimed = registry.claim("worker-a", ["testing"])
    assert claimed["status"] == "assigned"

    # Simulate expiry without waiting for the periodic supervisor.
    with registry.lock:
        registry.tasks[task["id"]]["lease_until"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
    with pytest.raises(ValueError, match="not leased"):
        registry.report(task["id"], "worker-a", "completed", output="late result", lease_token=claimed["lease_token"])

    refreshed = registry.snapshot()["tasks"][0]
    assert refreshed["status"] == "queued"
    assert refreshed["assigned_to"] is None
    assert refreshed["lease_until"] is None
    assert refreshed["attempts"] == 1


def test_expired_lease_exhausting_attempts_fails_closed(tmp_path):
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"), max_attempts=1)
    task = registry.create_task("One shot", capability="testing")
    claimed = registry.claim("worker-a", ["testing"])
    with registry.lock:
        registry.tasks[task["id"]]["lease_until"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
    with pytest.raises(ValueError, match="not leased"):
        registry.report(task["id"], "worker-a", "completed", output="late result", lease_token=claimed["lease_token"])
    assert registry.snapshot()["tasks"][0]["status"] == "failed"


def test_cancel_task_is_audited_and_rejects_late_worker_report(tmp_path):
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"))
    task = registry.create_task("Optional task", capability="analysis")
    claimed = registry.claim("worker-a", ["analysis"])
    cancelled = registry.cancel_task(task["id"], "Goal changed; no longer valuable")
    assert cancelled["status"] == "cancelled"
    assert "_lease_token" not in cancelled
    assert cancelled["history"][-1]["event"] == "cancelled"
    with pytest.raises(ValueError, match="not leased"):
        registry.report(task["id"], "worker-a", "completed", output="late output", lease_token=claimed["lease_token"])
    assert any(event["type"] == "task_cancelled" for event in registry.snapshot()["events"])


def test_merge_only_unstarted_tasks_with_same_capability(tmp_path):
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"))
    target = registry.create_task("Analyze retention", "Week 1", "analysis", priority=2)
    source = registry.create_task("Analyze cohort", "Week 2", "analysis", priority=5)
    merged = registry.merge_tasks(target["id"], [source["id"]], "Combine overlapping analysis")
    assert merged["target"]["priority"] == 5
    assert "_lease_token" not in merged["target"]
    assert "_lease_token" not in merged["sources"][0]
    assert "[Merged from " + source["id"] + "]" in merged["target"]["description"]
    assert merged["sources"][0]["status"] == "superseded"
    assert registry.snapshot()["counts"]["superseded"] == 1


def test_merge_rejects_incompatible_or_started_tasks(tmp_path):
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"))
    target = registry.create_task("Analyze", capability="analysis")
    source = registry.create_task("Research", capability="research")
    with pytest.raises(ValueError, match="matching capabilities"):
        registry.merge_tasks(target["id"], [source["id"]], "Unsafe merge")
    registry.claim("worker-a", ["analysis"])
    with pytest.raises(ValueError, match="must not have started"):
        registry.merge_tasks(target["id"], [source["id"]], "Too late")


def test_fencing_token_rejects_stale_attempt_from_same_worker(tmp_path):
    registry = WorkforceRegistry(path=str(tmp_path / "fencing.json"), max_attempts=3)
    task = registry.create_task("Retry safely", capability="analysis")
    first = registry.claim("same-worker", ["analysis"])
    with registry.lock:
        registry.tasks[task["id"]]["lease_until"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
    with pytest.raises(ValueError, match="not leased"):
        registry.report(task["id"], "same-worker", "completed", output="late attempt",
                        lease_token=first["lease_token"])
    second = registry.claim("same-worker", ["analysis"])
    assert second["attempts"] == 2
    assert second["lease_token"] != first["lease_token"]
    with pytest.raises(ValueError, match="lease token"):
        registry.report(task["id"], "same-worker", "completed", output="stale result",
                        lease_token=first["lease_token"])
    accepted = registry.report(task["id"], "same-worker", "completed", output="current result",
                               lease_token=second["lease_token"])
    assert accepted["output"] == "current result"
    assert accepted["status"] == "completed"
    assert "_lease_token" not in registry.snapshot()["tasks"][0]

def test_active_lease_heartbeat_renews_lease_and_rejects_stale_token(tmp_path):
    registry = WorkforceRegistry(
        path=str(tmp_path / "renew.json"), lease_seconds=30, max_attempts=2,
    )
    task = registry.create_task("Long-running task", capability="analysis")
    claimed = registry.claim("worker-a", ["analysis"])
    before = datetime.fromisoformat(claimed["lease_until"])

    renewed = registry.renew_lease(task["id"], "worker-a", claimed["lease_token"])
    after = datetime.fromisoformat(renewed["lease_until"])
    assert after > before
    assert renewed["history"][-1]["event"] == "lease_renewed"

    with pytest.raises(ValueError, match="lease token"):
        registry.renew_lease(task["id"], "worker-a", "stale-token")

def test_explicit_retry_requeues_blocked_task_with_audit_and_limit(tmp_path):
    registry = WorkforceRegistry(path=str(tmp_path / "explicit-retry.json"), max_attempts=2)
    task = registry.create_task("Needs dependency", capability="analysis")
    first = registry.claim("worker-a", ["analysis"])
    registry.report(task["id"], "worker-a", "blocked", blocker="Missing dependency",
                    lease_token=first["lease_token"])

    retried = registry.retry_task(task["id"], "Dependency restored; retry once")
    assert retried["status"] == "queued"
    assert retried["blocker"] == ""
    assert retried["history"][-1]["event"] == "retry_approved"
    assert retried["history"][-1]["reason"] == "Dependency restored; retry once"

    second = registry.claim("worker-a", ["analysis"])
    registry.report(task["id"], "worker-a", "blocked", blocker="Still unavailable",
                    lease_token=second["lease_token"])
    with pytest.raises(ValueError, match="retry limit"):
        registry.retry_task(task["id"], "Do not exceed the bounded retry policy")
def test_verification_record_is_persisted_without_claiming_truth(tmp_path):
    registry = WorkforceRegistry(path=str(tmp_path / "verification.json"))
    task = registry.create_task("Verify output", capability="analysis")
    claimed = registry.claim("worker-a", ["analysis"])
    registry.report(task["id"], "worker-a", "completed", output="A candidate result",
                    lease_token=claimed["lease_token"])
    verification = {
        "accepted": True, "status": "accepted",
        "checks": [{"name": "required_phrase", "passed": True}],
    }
    saved = registry.record_verification(task["id"], verification)
    assert saved["verification"]["accepted"] is True
    assert saved["verified_truth"] is False
    assert saved["history"][-1]["event"] == "verification_recorded"
    restored = WorkforceRegistry(path=str(tmp_path / "verification.json"))
    assert restored.snapshot()["tasks"][0]["verification"]["accepted"] is True
    assert restored.snapshot()["tasks"][0]["verified_truth"] is False

