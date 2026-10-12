"""End-to-end HTTP tests for the Digital Twin ↔ Digital Employee mailbox."""
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from mvp import server
from mvp.workforce import WorkforceRegistry


ADMIN = "admin-secret-for-integration-tests-0001"
RESEARCHER = "researcher-secret-for-integration-tests-0002"
ANALYST = "analyst-secret-for-integration-tests-0003"


@pytest.fixture
def workforce_http(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", ADMIN)
    monkeypatch.setenv(
        "JARVIS_WORKER_TOKENS",
        json.dumps({"researcher": RESEARCHER, "analyst": ANALYST}),
    )
    monkeypatch.setenv(
        "JARVIS_WORKER_CAPABILITIES",
        json.dumps({"researcher": ["research"], "analyst": ["analysis"]}),
    )
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"))
    monkeypatch.setattr(server, "WORKFORCE", registry)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}", registry
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=2)


def request_json(base, path, token=None, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(base + path, data=data, headers=headers)
    try:
        response = urlopen(request, timeout=3)
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))
    with response:
        return response.status, json.loads(response.read().decode("utf-8"))


def test_http_twin_to_worker_to_twin_happy_path(workforce_http):
    base, _ = workforce_http
    status, created = request_json(
        base, "/api/workforce/tasks", ADMIN,
        {"title": "Assess AI-native game demand", "capability": "research", "priority": 5},
    )
    assert status == 201
    task_id = created["task"]["id"]
    assert created["task"]["status"] == "queued"

    status, claim = request_json(
        base, "/api/workforce/claim", RESEARCHER,
        {"capabilities": ["research"]},
    )
    assert status == 200
    assert claim["task"]["id"] == task_id
    assert claim["task"]["assigned_to"] == "researcher"
    assert claim["task"]["status"] == "assigned"
    lease_token = claim["task"]["lease_token"]
    assert lease_token

    status, progress = request_json(
        base, "/api/workforce/report", RESEARCHER,
        {"task_id": task_id, "status": "in_progress", "lease_token": lease_token,
         "output": "Checking source material"},
    )
    assert status == 200
    assert progress["task"]["status"] == "assigned"
    assert progress["task"]["lease_until"]

    status, completed = request_json(
        base, "/api/workforce/report", RESEARCHER,
        {"task_id": task_id, "status": "completed", "lease_token": lease_token,
         "output": "Found three candidate sources; independent verification still required."},
    )
    assert status == 200
    assert completed["task"]["status"] == "completed"

    status, snapshot = request_json(base, "/api/workforce", ADMIN)
    assert status == 200
    assert snapshot["counts"]["completed"] == 1
    assert any(event["type"] == "worker_reported" and event["task_id"] == task_id
               for event in snapshot["events"])


def test_worker_report_requires_current_lease_token(workforce_http):
    base, _ = workforce_http
    status, created = request_json(base, "/api/workforce/tasks", ADMIN, {
        "title": "Research with lease token", "capability": "research",
    })
    assert status == 201
    task_id = created["task"]["id"]
    status, claim = request_json(base, "/api/workforce/claim", RESEARCHER,
                                 {"capabilities": ["research"]})
    assert status == 200
    lease_token = claim["task"]["lease_token"]

    status, rejected = request_json(base, "/api/workforce/report", RESEARCHER, {
        "task_id": task_id, "status": "completed", "output": "missing token",
    })
    assert status == 400
    assert "lease token" in rejected["error"]

    status, accepted = request_json(base, "/api/workforce/report", RESEARCHER, {
        "task_id": task_id, "status": "completed", "lease_token": lease_token,
        "output": "current lease result",
    })
    assert status == 200
    assert accepted["task"]["output"] == "current lease result"


def test_worker_cannot_impersonate_another_worker_or_admin(workforce_http):
    base, _ = workforce_http
    status, created = request_json(
        base, "/api/workforce/tasks", ADMIN,
        {"title": "Analyze retention", "capability": "analysis"},
    )
    assert status == 201
    task_id = created["task"]["id"]

    status, spoofed_claim = request_json(
        base, "/api/workforce/claim", RESEARCHER,
        {"worker_id": "analyst", "capabilities": ["research", "analysis"]},
    )
    assert status == 403

    status, forbidden = request_json(base, "/api/workforce", RESEARCHER)
    assert status == 403
    status, forbidden_create = request_json(
        base, "/api/workforce/tasks", ANALYST,
        {"title": "Unauthorized", "capability": "analysis"},
    )
    assert status == 403

    status, claim = request_json(base, "/api/workforce/claim", ANALYST,
                                 {"capabilities": ["analysis"]})
    assert status == 200
    assert claim["task"]["id"] == task_id

    status, spoofed_report = request_json(
        base, "/api/workforce/report", ANALYST,
        {"task_id": task_id, "worker_id": "researcher",
         "status": "completed", "output": "forged"},
    )
    assert status == 403


def test_worker_cannot_claim_capabilities_not_assigned_by_server(workforce_http):
    base, _ = workforce_http
    status, created = request_json(
        base, "/api/workforce/tasks", ADMIN,
        {"title": "Do privileged analysis", "capability": "analysis"},
    )
    assert status == 201
    status, claim = request_json(
        base, "/api/workforce/claim", RESEARCHER,
        {"capabilities": ["research", "analysis", "general"]},
    )
    assert status == 200
    assert claim["task"] is None


def test_worker_heartbeat_is_authenticated_and_cannot_impersonate(workforce_http):
    base, registry = workforce_http
    status, heartbeat = request_json(
        base, "/api/workers/heartbeat", RESEARCHER,
        {"status": "idle", "progress": "Waiting for work"},
    )
    assert status == 200
    assert heartbeat["worker"]["worker_id"] == "researcher"
    assert heartbeat["worker"]["status"] == "idle"
    assert "capabilities" in heartbeat["worker"]

    status, spoofed = request_json(
        base, "/api/workers/heartbeat", RESEARCHER,
        {"worker_id": "analyst", "status": "working"},
    )
    assert status == 403

    status, snapshot = request_json(base, "/api/workforce", ADMIN)
    assert status == 200
    assert any(w["worker_id"] == "researcher" for w in snapshot["workers"])


def test_admin_can_cancel_and_merge_tasks_but_worker_cannot(workforce_http):
    base, _ = workforce_http
    status, target = request_json(base, "/api/workforce/tasks", ADMIN, {
        "title": "Analyze cohort A", "description": "Week one", "capability": "analysis",
    })
    assert status == 201
    status, source = request_json(base, "/api/workforce/tasks", ADMIN, {
        "title": "Analyze cohort B", "description": "Week two", "capability": "analysis",
    })
    assert status == 201

    status, forbidden = request_json(base, "/api/workforce/merge", ANALYST, {
        "target_task_id": target["task"]["id"],
        "source_task_ids": [source["task"]["id"]],
        "reason": "Combine duplicates",
    })
    assert status == 403

    status, merged = request_json(base, "/api/workforce/merge", ADMIN, {
        "target_task_id": target["task"]["id"],
        "source_task_ids": [source["task"]["id"]],
        "reason": "Combine duplicate analyses",
    })
    assert status == 200
    assert merged["target"]["id"] == target["task"]["id"]
    assert merged["sources"][0]["status"] == "superseded"

    status, cancel_target = request_json(base, "/api/workforce/tasks", ADMIN, {
        "title": "Obsolete task", "capability": "analysis",
    })
    assert status == 201
    status, cancelled = request_json(base, "/api/workforce/cancel", ADMIN, {
        "task_id": cancel_target["task"]["id"], "reason": "Goal no longer needs it",
    })
    assert status == 200
    assert cancelled["task"]["status"] == "cancelled"


def test_http_rejects_late_report_from_previous_lease(workforce_http):
    from datetime import datetime, timedelta, timezone

    base, registry = workforce_http
    status, created = request_json(base, "/api/workforce/tasks", ADMIN, {
        "title": "Retry safely over HTTP", "capability": "research",
    })
    assert status == 201
    task_id = created["task"]["id"]

    status, first_claim = request_json(
        base, "/api/workforce/claim", RESEARCHER, {"capabilities": ["research"]},
    )
    assert status == 200
    old_token = first_claim["task"]["lease_token"]

    # Expire the lease deterministically, then let the same worker claim the retry.
    with registry.lock:
        registry.tasks[task_id]["lease_until"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
    registry.maintain()
    status, second_claim = request_json(
        base, "/api/workforce/claim", RESEARCHER, {"capabilities": ["research"]},
    )
    assert status == 200
    assert second_claim["task"]["attempts"] == 2
    new_token = second_claim["task"]["lease_token"]
    assert new_token != old_token

    status, stale = request_json(base, "/api/workforce/report", RESEARCHER, {
        "task_id": task_id, "status": "completed", "lease_token": old_token,
        "output": "late result from previous attempt",
    })
    assert status == 400
    assert "not leased" in stale["error"] or "lease token" in stale["error"]

    status, current = request_json(base, "/api/workforce/report", RESEARCHER, {
        "task_id": task_id, "status": "completed", "lease_token": new_token,
        "output": "result from current attempt",
    })
    assert status == 200
    assert current["task"]["output"] == "result from current attempt"

def test_working_heartbeat_renews_lease_only_with_current_token(workforce_http):
    from datetime import datetime

    base, registry = workforce_http
    status, created = request_json(base, "/api/workforce/tasks", ADMIN, {
        "title": "Keep long task leased", "capability": "research",
    })
    assert status == 201
    task_id = created["task"]["id"]
    status, claim = request_json(base, "/api/workforce/claim", RESEARCHER, {
        "capabilities": ["research"],
    })
    assert status == 200
    lease_token = claim["task"]["lease_token"]
    before = datetime.fromisoformat(claim["task"]["lease_until"])

    status, rejected = request_json(base, "/api/workers/heartbeat", RESEARCHER, {
        "status": "working", "current_task_id": task_id, "lease_token": "stale-token",
    })
    assert status == 400
    assert "lease token" in rejected["error"]

    status, beat = request_json(base, "/api/workers/heartbeat", RESEARCHER, {
        "status": "working", "current_task_id": task_id, "lease_token": lease_token,
        "progress": "Still executing",
    })
    assert status == 200
    after = datetime.fromisoformat(registry.snapshot()["tasks"][0]["lease_until"])
    assert after > before
    assert beat["worker"]["status"] == "working"


def test_working_heartbeat_renews_only_the_current_lease(workforce_http):
    from datetime import datetime, timedelta, timezone

    base, registry = workforce_http
    status, created = request_json(base, "/api/workforce/tasks", ADMIN, {
        "title": "Long-running task", "capability": "research",
    })
    assert status == 201
    task_id = created["task"]["id"]
    status, claim = request_json(base, "/api/workforce/claim", RESEARCHER, {
        "capabilities": ["research"],
    })
    assert status == 200
    token = claim["task"]["lease_token"]

    # Put the lease near expiry without waiting for wall-clock time.
    with registry.lock:
        registry.tasks[task_id]["lease_until"] = (
            datetime.now(timezone.utc) + timedelta(seconds=1)
        ).isoformat()
    before = registry.snapshot()["tasks"][0]["lease_until"]

    status, beat = request_json(base, "/api/workers/heartbeat", RESEARCHER, {
        "status": "working", "current_task_id": task_id,
        "lease_token": token, "progress": "Still executing",
    })
    assert status == 200
    after = next(t for t in registry.snapshot()["tasks"] if t["id"] == task_id)["lease_until"]
    assert datetime.fromisoformat(after) > datetime.fromisoformat(before)

    status, rejected = request_json(base, "/api/workers/heartbeat", RESEARCHER, {
        "status": "working", "current_task_id": task_id,
        "lease_token": "not-the-current-token", "progress": "Stale worker",
    })
    assert status == 400
    assert "lease token" in rejected["error"] or "not leased" in rejected["error"]


def test_http_retry_exhaustion_marks_task_failed_and_visible_to_monitor(workforce_http):
    from datetime import datetime, timedelta, timezone
    from mvp.monitor import build_monitor_report

    base, registry = workforce_http
    registry.max_attempts = 1
    status, created = request_json(base, "/api/workforce/tasks", ADMIN, {
        "title": "Fail after one lost lease", "capability": "research",
    })
    assert status == 201
    task_id = created["task"]["id"]

    status, claim = request_json(
        base, "/api/workforce/claim", RESEARCHER, {"capabilities": ["research"]},
    )
    assert status == 200
    token = claim["task"]["lease_token"]

    with registry.lock:
        registry.tasks[task_id]["lease_until"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()

    status, late = request_json(base, "/api/workforce/report", RESEARCHER, {
        "task_id": task_id, "status": "completed", "lease_token": token,
        "output": "too late",
    })
    assert status == 400
    failed = next(t for t in registry.snapshot()["tasks"] if t["id"] == task_id)
    assert failed["status"] == "failed"
    assert failed["attempts"] == 1

    report = build_monitor_report(registry.snapshot())
    assert report["twin"]["status"] == "needs_attention"
    assert any(alert["type"] == "failed" and alert["task_id"] == task_id
               for alert in report["alerts"])

def test_admin_retry_endpoint_requires_triage_reason_and_worker_cannot_call(workforce_http):
    base, registry = workforce_http
    status, created = request_json(base, "/api/workforce/tasks", ADMIN, {
        "title": "Retry only after review", "capability": "research",
    })
    assert status == 201
    task_id = created["task"]["id"]
    status, claim = request_json(
        base, "/api/workforce/claim", RESEARCHER, {"capabilities": ["research"]},
    )
    assert status == 200
    status, report = request_json(base, "/api/workforce/report", RESEARCHER, {
        "task_id": task_id, "status": "blocked",
        "lease_token": claim["task"]["lease_token"],
        "blocker": "Source endpoint temporarily unavailable",
    })
    assert status == 200
    status, forbidden = request_json(base, "/api/workforce/retry", RESEARCHER, {
        "task_id": task_id, "reason": "Worker cannot authorize its own retry",
    })
    assert status == 403
    status, retried = request_json(base, "/api/workforce/retry", ADMIN, {
        "task_id": task_id, "reason": "Twin checked the source outage; retry once",
    })
    assert status == 200
    assert retried["task"]["status"] == "queued"
    assert retried["task"]["history"][-1]["event"] == "retry_approved"

def test_trace_dashboard_is_served_without_exposing_workforce_data(workforce_http):
    from urllib.request import urlopen

    base, _ = workforce_http
    with urlopen(base + "/trace", timeout=3) as response:
        page = response.read().decode("utf-8")
        assert response.status == 200
        assert "流程追踪与验收" in page
        assert "员工在线与心跳" in page
        assert "最近心跳" in page
        assert 'fetch("/api/workforce"' in page
        assert "localStorage.setItem" not in page
        assert "localStorage.getItem" not in page
    status, protected = request_json(base, "/api/workforce")
    assert status == 401
    assert protected["ok"] is False
def test_admin_verification_endpoint_records_check_without_claiming_truth(workforce_http):
    base, registry = workforce_http
    status, created = request_json(base, "/api/workforce/tasks", ADMIN, {
        "title": "Verify visible output", "capability": "research",
    })
    assert status == 201
    task_id = created["task"]["id"]
    status, claim = request_json(
        base, "/api/workforce/claim", RESEARCHER, {"capabilities": ["research"]},
    )
    assert status == 200
    status, reported = request_json(base, "/api/workforce/report", RESEARCHER, {
        "task_id": task_id, "status": "completed",
        "lease_token": claim["task"]["lease_token"], "output": "candidate result",
    })
    assert status == 200
    status, forbidden = request_json(base, "/api/workforce/verify", RESEARCHER, {
        "task_id": task_id, "verification": {"accepted": True},
    })
    assert status == 403
    status, verified = request_json(base, "/api/workforce/verify", ADMIN, {
        "task_id": task_id,
        "verification": {"accepted": True, "status": "accepted", "checks": []},
    })
    assert status == 200
    assert verified["task"]["verification"]["accepted"] is True
    assert verified["task"]["verified_truth"] is False
    assert any(e["type"] == "verification_recorded" and e["task_id"] == task_id
               for e in registry.snapshot()["events"])

def test_acceptance_scenario_blocker_retry_completion_and_verification(workforce_http):
    """Exercise the observable acceptance path through authenticated HTTP APIs."""
    base, registry = workforce_http
    status, created = request_json(base, "/api/workforce/tasks", ADMIN, {
        "title": "Validate a game-demand research result",
        "description": "Collect a result, handle a temporary source outage, then verify its recorded evidence.",
        "capability": "research",
        "priority": 5,
        "success_criteria": {"min_output_chars": 20},
    })
    assert status == 201
    task_id = created["task"]["id"]

    status, first_claim = request_json(base, "/api/workforce/claim", RESEARCHER, {
        "capabilities": ["research"],
    })
    assert status == 200
    first_token = first_claim["task"]["lease_token"]

    status, blocked = request_json(base, "/api/workforce/report", RESEARCHER, {
        "task_id": task_id,
        "status": "blocked",
        "lease_token": first_token,
        "blocker": "Research endpoint temporarily unavailable",
        "output": "Initial research attempt could not reach the source.",
    })
    assert status == 200
    assert blocked["task"]["status"] == "blocked"

    status, retry = request_json(base, "/api/workforce/retry", ADMIN, {
        "task_id": task_id,
        "reason": "Twin reviewed the temporary outage and authorized one bounded retry.",
    })
    assert status == 200
    assert retry["task"]["status"] == "queued"

    status, second_claim = request_json(base, "/api/workforce/claim", RESEARCHER, {
        "capabilities": ["research"],
    })
    assert status == 200
    second_token = second_claim["task"]["lease_token"]
    assert second_token and second_token != first_token

    status, completed = request_json(base, "/api/workforce/report", RESEARCHER, {
        "task_id": task_id,
        "status": "completed",
        "lease_token": second_token,
        "output": "Candidate finding: three sources reviewed; factual confirmation pending.",
    })
    assert status == 200
    assert completed["task"]["status"] == "completed"

    status, verification = request_json(base, "/api/workforce/verify", ADMIN, {
        "task_id": task_id,
        "verification": {
            "accepted": True,
            "status": "structural_checks_passed",
            "checks": [{"name": "output_present", "passed": True}],
            "reviewer": "acceptance-test",
        },
    })
    assert status == 200
    assert verification["task"]["verification"]["accepted"] is True
    assert verification["task"]["verified_truth"] is False

    status, snapshot = request_json(base, "/api/workforce", ADMIN)
    assert status == 200
    task = next(item for item in snapshot["tasks"] if item["id"] == task_id)
    assert task["status"] == "completed"
    assert any("temporarily unavailable" in str(entry).lower() for entry in task["history"])
    assert task["verification"]["accepted"] is True
    assert task["verified_truth"] is False
    event_types = [event["type"] for event in snapshot["events"] if event.get("task_id") == task_id]
    assert "task_created" in event_types
    assert "worker_reported" in event_types
    assert "retry_approved" in event_types
    assert "verification_recorded" in event_types
    assert len(task["history"]) >= 4

def test_worker_can_claim_only_requested_eligible_task_without_bypassing_capabilities(workforce_http):
    base, _ = workforce_http
    status, first = request_json(
        base, "/api/workforce/tasks", ADMIN,
        {"title": "Earlier task", "capability": "research", "priority": 3},
    )
    assert status == 201
    status, target = request_json(
        base, "/api/workforce/tasks", ADMIN,
        {"title": "Target task", "capability": "research", "priority": 3},
    )
    assert status == 201

    status, claimed = request_json(
        base, "/api/workforce/claim", RESEARCHER,
        {"capabilities": ["research"], "task_id": target["task"]["id"]},
    )
    assert status == 200
    assert claimed["task"]["id"] == target["task"]["id"]

    status, denied = request_json(
        base, "/api/workforce/claim", RESEARCHER,
        {"capabilities": ["research"], "task_id": first["task"]["id"]},
    )
    assert status == 200
    assert denied["task"] is None

