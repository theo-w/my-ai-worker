"""HTTP access-control tests for the observe-only improvement endpoint."""
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from mvp import server
from mvp.workforce import WorkforceRegistry


ADMIN = "admin-secret-for-improvement-tests-0001"


@pytest.fixture
def improvement_http(monkeypatch, tmp_path):
    monkeypatch.delenv("JARVIS_PUBLIC_DEMO", raising=False)
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", ADMIN)
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"))
    registry.create_task("blocked one", capability="analysis")
    registry.create_task("blocked two", capability="analysis")
    # Record two matching blockers through the registry's supported task lifecycle.
    for task in registry.tasks.values():
        task["status"] = "blocked"
        task["blocker"] = "provider timeout"
    registry.save()
    monkeypatch.setattr(server, "WORKFORCE", registry)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}", registry
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=2)


def get_json(base, token=None):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(base + "/api/improvement/report", headers=headers)
    try:
        response = urlopen(request, timeout=3)
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))
    with response:
        return response.status, json.loads(response.read().decode("utf-8"))


def test_improvement_report_requires_admin_authentication(improvement_http):
    base, _ = improvement_http
    status, body = get_json(base)
    assert status in (401, 403)
    assert body["ok"] is False


def test_admin_receives_observe_only_report_without_task_mutation(improvement_http):
    base, registry = improvement_http
    before = json.dumps(registry.tasks, sort_keys=True)
    status, body = get_json(base, ADMIN)
    assert status == 200
    assert body["ok"] is True
    assert body["report"]["mode"] == "observe_only"
    assert body["report"]["actions_taken"] == []
    assert body["report"]["observations"][0]["signal"] == "repeated_blocker_text"
    assert json.dumps(registry.tasks, sort_keys=True) == before
