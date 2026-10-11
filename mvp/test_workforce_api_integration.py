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

    status, progress = request_json(
        base, "/api/workforce/report", RESEARCHER,
        {"task_id": task_id, "status": "in_progress", "output": "Checking source material"},
    )
    assert status == 200
    assert progress["task"]["status"] == "assigned"
    assert progress["task"]["lease_until"]

    status, completed = request_json(
        base, "/api/workforce/report", RESEARCHER,
        {"task_id": task_id, "status": "completed",
         "output": "Found three candidate sources; independent verification still required."},
    )
    assert status == 200
    assert completed["task"]["status"] == "completed"

    status, snapshot = request_json(base, "/api/workforce", ADMIN)
    assert status == 200
    assert snapshot["counts"]["completed"] == 1
    assert any(event["type"] == "worker_reported" and event["task_id"] == task_id
               for event in snapshot["events"])


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
