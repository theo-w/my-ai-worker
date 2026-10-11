"""Integration checks for the Digital Twin bounded execution loop."""
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from mvp import server
from mvp.executor import WorkerExecutionResult
from mvp.twin import DigitalTwinCoordinator
from mvp.worker_agent import DigitalEmployeeAgent
from mvp.workforce import WorkforceRegistry


class FakeExecutor:
    def execute(self, task, goal):
        return WorkerExecutionResult(
            task_id=task["id"], capability=task["capability"],
            status="completed", output="Simulated test output",
            simulated=True, metadata={"test": True},
        )


def test_twin_coordinates_worker_and_reports_goal(monkeypatch, tmp_path):
    admin, token = "admin-test-token-000000000001", "worker-test-token-000000000002"
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", admin)
    monkeypatch.setenv("JARVIS_WORKER_TOKENS", json.dumps({"researcher": token}))
    monkeypatch.setenv("JARVIS_WORKER_CAPABILITIES", json.dumps({"researcher": ["research"]}))
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"))
    monkeypatch.setattr(server, "WORKFORCE", registry)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        twin = DigitalTwinCoordinator(base, admin)
        worker = DigitalEmployeeAgent(base, token, ["research"], FakeExecutor(), "test goal")
        result = twin.execute_goal("test goal", [worker], max_cycles=3, tasks=[
            {"title": "Research", "capability": "research", "priority": 5},
        ])
        assert result["status"] == "completed"
        assert result["counts"]["completed"] == 1
        assert result["tasks"][0]["provenance"] == "simulated"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_twin_rejects_invalid_execution_parameters():
    twin = DigitalTwinCoordinator("http://127.0.0.1:1", "admin-test-token-000000000001")
    with pytest.raises(ValueError):
        twin.execute_goal("goal", [], max_cycles=2)
