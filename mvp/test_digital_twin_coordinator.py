"""End-to-end tests for Digital Twin planning and supervision over HTTP."""
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from mvp import server
from mvp.twin import DigitalTwinAPIError, DigitalTwinCoordinator
from mvp.workforce import WorkforceRegistry


ADMIN = "admin-secret-for-twin-tests-0001"
RESEARCHER = "researcher-secret-for-twin-tests-0002"
ANALYST = "analyst-secret-for-twin-tests-0003"


@pytest.fixture
def twin_system(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", ADMIN)
    monkeypatch.setenv("JARVIS_WORKER_TOKENS", json.dumps({
        "researcher": RESEARCHER, "analyst": ANALYST,
    }))
    monkeypatch.setenv("JARVIS_WORKER_CAPABILITIES", json.dumps({
        "researcher": ["research"], "analyst": ["analysis"],
    }))
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"))
    monkeypatch.setattr(server, "WORKFORCE", registry)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    yield DigitalTwinCoordinator(base, ADMIN), base
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=2)


def post(base, path, token, payload):
    request = Request(base + path, data=json.dumps(payload).encode(),
                      headers={"Authorization": "Bearer " + token,
                               "Content-Type": "application/json"})
    try:
        response = urlopen(request, timeout=3)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())
    with response:
        return response.status, json.loads(response.read().decode())


def test_twin_plans_goal_and_inspects_real_worker_progress(twin_system):
    twin, base = twin_system
    plan = twin.start_goal("评估一个 AI 原生游戏机会")
    assert plan["status"] == "planned"
    assert plan["task_count"] == 4
    assert all(task["status"] == "queued" for task in plan["created_tasks"])

    first = plan["created_tasks"][0]
    status, claim = post(base, "/api/workforce/claim", RESEARCHER,
                         {"capabilities": ["research"]})
    assert status == 200
    assert claim["task"]["id"] == first["id"]
    lease_token = claim["task"]["lease_token"]

    progress = twin.inspect()
    assert progress["status"] == "in_progress"
    assert progress["counts"]["assigned"] == 1
    assert progress["counts"]["queued"] == 3

    status, result = post(base, "/api/workforce/report", RESEARCHER, {
        "task_id": first["id"], "status": "completed", "lease_token": lease_token,
        "output": json.dumps({
            "content": "Example evidence placeholder; verify source URLs before decisions.",
            "simulated": True, "metadata": {"source_count": 0},
        }),
    })
    assert status == 200
    assert result["task"]["status"] == "completed"

    snapshot = twin.inspect()
    completed = next(item for item in snapshot["tasks"] if item["task_id"] == first["id"])
    assert completed["status"] == "completed"
    assert completed["provenance"] == "simulated"
    assert snapshot["counts"]["queued"] == 3


def test_twin_refuses_empty_goals_and_invalid_task_plans(twin_system):
    twin, _ = twin_system
    with pytest.raises(ValueError, match="goal"):
        twin.start_goal(" ")
    with pytest.raises(ValueError, match="task plan"):
        twin.start_goal("Valid goal", tasks=[])


def test_twin_requires_admin_credentials_for_supervision(twin_system):
    _, base = twin_system
    unauthorized = DigitalTwinCoordinator(base, RESEARCHER)
    with pytest.raises(DigitalTwinAPIError) as error:
        unauthorized.inspect()
    assert error.value.status == 403
