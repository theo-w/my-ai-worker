from datetime import datetime, timedelta, timezone

import pytest

from mvp.workforce import WorkforceRegistry


def test_worker_claims_reports_and_twin_receives_feedback(tmp_path):
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"))
    task = registry.create_task("Build a prototype", capability="implementation", priority=5)
    claimed = registry.claim("worker-a", ["implementation"])
    assert claimed["id"] == task["id"]
    assert claimed["status"] == "assigned"

    registry.feedback(task["id"], "digital-twin", "Please include a test report", "correction")
    result = registry.report(task["id"], "worker-a", "completed", output="Prototype + tests")
    assert result["status"] == "completed"
    assert result["output"] == "Prototype + tests"
    assert result["feedback"][0]["actor"] == "digital-twin"
    assert registry.snapshot()["counts"]["completed"] == 1


def test_worker_cannot_report_another_workers_task(tmp_path):
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"))
    task = registry.create_task("Research", capability="research")
    registry.claim("worker-a", ["research"])
    with pytest.raises(ValueError, match="not leased"):
        registry.report(task["id"], "worker-b", "completed", output="forged")


def test_approval_gate_prevents_claim_until_approved(tmp_path):
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"))
    task = registry.create_task("Release", approval_required=True)
    assert registry.claim("worker-a") is None
    registry.approve_task(task["id"])
    assert registry.claim("worker-a")["id"] == task["id"]


def test_persistent_queue_survives_restart_and_retries_blocker(tmp_path):
    path = str(tmp_path / "workforce.json")
    first = WorkforceRegistry(path=path, max_attempts=2)
    task = first.create_task("Run tests", capability="testing")
    first.claim("worker-a", ["testing"])
    first.report(task["id"], "worker-a", "blocked", blocker="Missing dependency")

    restarted = WorkforceRegistry(path=path, max_attempts=2)
    assert restarted.snapshot()["tasks"][0]["status"] == "queued"
    assert restarted.claim("worker-b", ["testing"])["attempts"] == 2


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
        registry.report(task["id"], "worker-a", "completed", output="late result")

    refreshed = registry.snapshot()["tasks"][0]
    assert refreshed["status"] == "queued"
    assert refreshed["assigned_to"] is None
    assert refreshed["lease_until"] is None
    assert refreshed["attempts"] == 1


def test_expired_lease_exhausting_attempts_fails_closed(tmp_path):
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"), max_attempts=1)
    task = registry.create_task("One shot", capability="testing")
    registry.claim("worker-a", ["testing"])
    with registry.lock:
        registry.tasks[task["id"]]["lease_until"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
    with pytest.raises(ValueError, match="not leased"):
        registry.report(task["id"], "worker-a", "completed", output="late result")
    assert registry.snapshot()["tasks"][0]["status"] == "failed"
