"""Tests for read-only Digital Twin and employee observability."""
from datetime import datetime, timezone, timedelta

from mvp.monitor import build_monitor_report


def test_monitor_reports_twin_employee_task_io_and_provenance():
    now = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
    snapshot = {
        "tasks": [
            {
                "id": "task-a", "title": "Research players", "description": "Find source-backed needs",
                "capability": "research", "status": "assigned", "assigned_to": "worker-research",
                "attempts": 1, "max_attempts": 3, "updated_at": (now - timedelta(seconds=30)).isoformat(),
                "lease_until": (now + timedelta(minutes=4)).isoformat(), "output": "",
                "blocker": "", "feedback": [], "history": [{"event": "assigned"}],
            },
            {
                "id": "task-b", "title": "Analyze cost", "description": "Estimate inference costs",
                "capability": "analysis", "status": "completed", "assigned_to": "worker-analysis",
                "attempts": 1, "max_attempts": 3, "updated_at": now.isoformat(),
                "lease_until": None,
                "output": '{"content":"Example only","simulated":true,"metadata":{"test":true}}',
                "blocker": "", "feedback": [], "history": [{"event": "worker_report"}],
            },
        ],
        "events": [{"type": "task_created"}, {"type": "task_assigned"}],
    }
    report = build_monitor_report(snapshot, now=now)
    assert report["twin"]["status"] == "in_progress"
    assert report["twin"]["active_tasks"] == 1
    assert report["twin"]["completed_tasks"] == 1
    assert {employee["worker_id"]: employee["status"] for employee in report["employees"]} == {
        "worker-analysis": "idle", "worker-research": "working",
    }
    completed = next(task for task in report["tasks"] if task["task_id"] == "task-b")
    assert completed["input"]["description"] == "Estimate inference costs"
    assert completed["output"] == "Example only"
    assert completed["provenance"] == "simulated"
    assert report["event_count"] == 2


def test_monitor_flags_expired_leases_and_stale_or_blocked_tasks():
    now = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
    old = (now - timedelta(minutes=20)).isoformat()
    report = build_monitor_report({
        "tasks": [
            {"id": "expired", "status": "assigned", "updated_at": old,
             "lease_until": (now - timedelta(seconds=2)).isoformat(), "assigned_to": "worker-a"},
            {"id": "stale", "status": "queued", "updated_at": old},
            {"id": "blocked", "status": "blocked", "updated_at": now.isoformat(),
             "blocker": "model provider missing"},
        ],
        "events": [],
    }, now=now)
    kinds = {alert["type"] for alert in report["alerts"]}
    assert {"lease_expired", "stale_task", "blocked"} <= kinds
    assert report["twin"]["status"] == "needs_attention"


def test_monitor_accepts_dictionary_task_snapshots():
    report = build_monitor_report({"tasks": {"x": {"id": "x", "status": "completed"}}, "events": []})
    assert report["twin"]["completed_tasks"] == 1
