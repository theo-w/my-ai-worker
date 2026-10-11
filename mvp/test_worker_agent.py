"""End-to-end tests for the standalone Digital Employee agent."""
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from mvp import server
from mvp.executor import WorkerExecutionResult
from mvp.twin import DigitalTwinCoordinator
from mvp.worker_agent import DigitalEmployeeAgent
from mvp.workforce import WorkforceRegistry


ADMIN = "admin-secret-worker-agent-tests-0001"
RESEARCHER = "researcher-secret-worker-agent-tests-0002"
ANALYST = "analyst-secret-worker-agent-tests-0003"


class FakeExecutor:
    def __init__(self, simulated=False, fail=False):
        self.simulated = simulated
        self.fail = fail
        self.calls = []

    def execute(self, task, goal):
        self.calls.append((task["id"], goal))
        if self.fail:
            raise RuntimeError("Required live research adapter is not configured")
        return WorkerExecutionResult(
            task_id=task["id"], capability=task["capability"],
            status="completed", output="Test executor result; source verification required.",
            simulated=self.simulated,
            metadata={"mode": "test_fake", "output_is_verified_evidence": False},
        )


@pytest.fixture
def system(monkeypatch, tmp_path):
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
    yield DigitalTwinCoordinator(base, ADMIN), base, registry
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=2)


def test_twin_plan_is_claimed_executed_and_reported_by_standalone_agent(system):
    twin, base, registry = system
    plan = twin.start_goal("评估一个 AI 原生游戏机会", tasks=[{
        "title": "Research player needs", "capability": "research", "priority": 5,
    }])
    executor = FakeExecutor(simulated=False)
    employee = DigitalEmployeeAgent(
        base, RESEARCHER, ["research"], executor, plan["goal"],
    )

    result = employee.run_once()
    assert result["status"] == "completed"
    assert result["task_id"] == plan["created_tasks"][0]["id"]
    assert result["simulated"] is False
    assert len(executor.calls) == 1

    snapshot = twin.inspect()
    task = next(item for item in snapshot["tasks"] if item["task_id"] == result["task_id"])
    assert task["status"] == "completed"
    assert task["provenance"] == "executor_reported_live"
    stored = next(item for item in registry.snapshot()["tasks"] if item["id"] == result["task_id"])
    envelope = json.loads(stored["output"])
    assert envelope["content"].startswith("Test executor result")
    assert envelope["metadata"]["output_is_verified_evidence"] is False


def test_agent_returns_idle_when_twin_has_no_compatible_tasks(system):
    _, base, _ = system
    employee = DigitalEmployeeAgent(base, ANALYST, ["analysis"], FakeExecutor(), "test goal")
    assert employee.run_once() == {"status": "idle", "task_id": None}


def test_agent_reports_missing_executor_dependency_as_blocked(system):
    twin, base, registry = system
    plan = twin.start_goal("Evaluate a game", tasks=[{
        "title": "Research", "capability": "research",
    }])
    employee = DigitalEmployeeAgent(
        base, RESEARCHER, ["research"], FakeExecutor(fail=True), plan["goal"],
    )
    result = employee.run_once()
    assert result["status"] == "blocked"
    assert "not configured" in result["error"]
    stored = next(item for item in registry.snapshot()["tasks"]
                  if item["id"] == plan["created_tasks"][0]["id"])
    assert stored["status"] == "queued"  # blocked work is eligible for bounded retry
    assert stored["blocker"]
