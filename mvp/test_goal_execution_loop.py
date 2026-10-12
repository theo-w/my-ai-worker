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
    monkeypatch.setenv("JARVIS_WORKER_CAPABILITIES", json.dumps({"researcher": ["analysis"]}))
    registry = WorkforceRegistry(path=str(tmp_path / "workforce.json"))
    monkeypatch.setattr(server, "WORKFORCE", registry)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        twin = DigitalTwinCoordinator(base, admin)
        worker = DigitalEmployeeAgent(base, token, ["analysis"], FakeExecutor(), "test goal")
        result = twin.execute_goal("test goal", [worker], max_cycles=3, tasks=[
            {"title": "Summarize test input", "capability": "analysis", "priority": 5},
        ])
        assert result["status"] == "completed"
        assert result["execution_decision"]["mode"] == "single_agent"
        assert result["counts"]["completed"] == 1
        assert result["tasks"][0]["provenance"] == "simulated"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_supervision_reclaims_expired_leases_and_returns_monitor_report(monkeypatch, tmp_path):
    admin, token = "admin-test-token-000000000021", "worker-test-token-000000000022"
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", admin)
    monkeypatch.setenv("JARVIS_WORKER_TOKENS", json.dumps({"analyst": token}))
    monkeypatch.setenv("JARVIS_WORKER_CAPABILITIES", json.dumps({"analyst": ["analysis"]}))
    registry = WorkforceRegistry(path=str(tmp_path / "workforce-supervision.json"))
    task = registry.create_task("Recover expired work", capability="analysis")
    claimed = registry.claim("analyst", ["analysis"])
    assert claimed and claimed["id"] == task["id"]
    registry.tasks[task["id"]]["lease_until"] = "2000-01-01T00:00:00+00:00"
    registry.save()
    monkeypatch.setattr(server, "WORKFORCE", registry)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        twin = DigitalTwinCoordinator(f"http://127.0.0.1:{httpd.server_port}", admin)
        result = twin.supervise_once()
        assert result["maintenance"]["requeued"] == [task["id"]]
        assert result["report"]["twin"]["active_tasks"] == 1
        assert any(event["type"] == "supervision_observed"
                   for event in result["supervision_events"])
        current = registry.snapshot()
        assert next(item for item in current["tasks"] if item["id"] == task["id"])["status"] == "queued"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_twin_rejects_invalid_execution_parameters():
    twin = DigitalTwinCoordinator("http://127.0.0.1:1", "admin-test-token-000000000001")
    with pytest.raises(ValueError):
        twin.execute_goal("goal", [], max_cycles=2)



def test_twin_does_not_accept_simulated_research_as_goal_success(monkeypatch, tmp_path):
    admin, token = "admin-test-token-000000000001", "worker-test-token-000000000002"
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", admin)
    monkeypatch.setenv("JARVIS_WORKER_TOKENS", json.dumps({"researcher": token}))
    monkeypatch.setenv("JARVIS_WORKER_CAPABILITIES", json.dumps({"researcher": ["research"]}))
    registry = WorkforceRegistry(path=str(tmp_path / "workforce-evidence.json"))
    monkeypatch.setattr(server, "WORKFORCE", registry)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        twin = DigitalTwinCoordinator(base, admin)
        worker = DigitalEmployeeAgent(base, token, ["research"], FakeExecutor(), "research goal")
        result = twin.execute_goal("research goal", [worker], max_cycles=3, tasks=[
            {"title": "Research evidence", "capability": "research", "priority": 5},
        ])
        assert result["counts"]["completed"] == 1
        assert result["status"] == "needs_attention"
        task = result["tasks"][0]
        assert task["verification"]["accepted"] is False
        assert task["verification"]["simulated"] is True
        assert any(event["type"] == "verification_rejected" for event in result["events"])
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)



def test_twin_requires_approval_before_creating_or_running_tasks():
    twin = DigitalTwinCoordinator("http://127.0.0.1:1", "admin-test-token-000000000001")
    worker = DigitalEmployeeAgent(
        "http://127.0.0.1:1", "worker-test-token-000000000002",
        ["analysis"], FakeExecutor(), "sensitive goal",
    )
    result = twin.execute_goal(
        "sensitive goal", [worker], tasks=[
            {"title": "Publish announcement", "capability": "analysis",
             "human_approval_required": True},
        ],
    )
    assert result["status"] == "needs_approval"
    assert result["execution_decision"]["mode"] == "approval_required"
    assert result["counts"]["completed"] == 0
    assert not result["tasks"]


def test_twin_parallel_mode_runs_capability_matched_workers(monkeypatch, tmp_path):
    admin = "admin-test-token-000000000001"
    tokens = {
        "analyst_a": "worker-test-token-000000000002",
        "analyst_b": "worker-test-token-000000000003",
    }
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", admin)
    monkeypatch.setenv("JARVIS_WORKER_TOKENS", json.dumps(tokens))
    monkeypatch.setenv("JARVIS_WORKER_CAPABILITIES", json.dumps({
        "analyst_a": ["analysis"], "analyst_b": ["analysis"],
    }))
    registry = WorkforceRegistry(path=str(tmp_path / "workforce-parallel.json"))
    monkeypatch.setattr(server, "WORKFORCE", registry)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        twin = DigitalTwinCoordinator(base, admin)
        workers = [
            DigitalEmployeeAgent(base, tokens["analyst_a"], ["analysis"], FakeExecutor(), "parallel goal"),
            DigitalEmployeeAgent(base, tokens["analyst_b"], ["analysis"], FakeExecutor(), "parallel goal"),
        ]
        result = twin.execute_goal(
            "parallel goal", workers, max_cycles=3,
            tasks=[
                {"title": "Analyze input A", "capability": "analysis", "parallelizable": True},
                {"title": "Analyze input B", "capability": "analysis", "parallelizable": True},
            ],
            execution_profile={
                "complexity": 5, "parallelizable": True,
                "expected_parallel_quality_gain": 0.8,
                "expected_parallel_time_savings": 0.8,
                "team_cost_multiplier": 1.5,
            },
        )
        assert result["execution_decision"]["mode"] == "parallel_team"
        assert result["counts"]["completed"] == 2
        assert result["status"] == "completed"
        assert any(event.get("execution_mode") == "parallel_team"
                   for event in result["events"] if event["type"] == "cycle_finished")
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_twin_can_cancel_low_value_pending_work_after_feedback(monkeypatch, tmp_path):
    admin, token = "admin-test-token-000000000001", "worker-test-token-000000000002"
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", admin)
    monkeypatch.setenv("JARVIS_WORKER_TOKENS", json.dumps({"analyst": token}))
    monkeypatch.setenv("JARVIS_WORKER_CAPABILITIES", json.dumps({"analyst": ["analysis"]}))
    registry = WorkforceRegistry(path=str(tmp_path / "workforce-replan.json"))
    monkeypatch.setattr(server, "WORKFORCE", registry)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        twin = DigitalTwinCoordinator(base, admin)
        worker = DigitalEmployeeAgent(base, token, ["analysis"], FakeExecutor(), "changing goal")
        revision_calls = []

        def revise(goal, live_tasks, cycle):
            revision_calls.append((cycle, [task["task_id"] for task in live_tasks]))
            if cycle == 1:
                pending = next(task for task in live_tasks if task["status"] == "queued")
                return {"cancel": [{
                    "task_id": pending["task_id"],
                    "reason": "Earlier result made this follow-up redundant",
                }]}
            return {}

        result = twin.execute_goal(
            "changing goal", [worker], max_cycles=3,
            tasks=[
                {"title": "Primary analysis", "capability": "analysis", "priority": 5},
                {"title": "Optional follow-up", "capability": "analysis", "priority": 1},
            ],
            revision_policy=revise,
        )
        assert revision_calls
        assert result["status"] == "completed"
        assert result["counts"]["completed"] == 1
        assert any(event["type"] == "task_cancelled" for event in result["events"])
        assert result["counts"]["cancelled"] == 1
        assert result["metrics"]["cancelled_tasks"] == 1
        assert len(result["tasks"]) == 2
        assert any(task["status"] == "cancelled" for task in result["tasks"])
        assert any(event["type"] == "execution_metrics" for event in result["events"])
        snapshot = registry.snapshot()
        assert sum(task["status"] == "cancelled" for task in snapshot["tasks"]) == 1
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_independent_review_policy_fails_closed_without_reviewer(monkeypatch, tmp_path):
    admin, token = "admin-test-token-000000000011", "worker-test-token-000000000012"
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", admin)
    monkeypatch.setenv("JARVIS_WORKER_TOKENS", json.dumps({"analyst": token}))
    monkeypatch.setenv("JARVIS_WORKER_CAPABILITIES", json.dumps({"analyst": ["analysis"]}))
    registry = WorkforceRegistry(path=str(tmp_path / "workforce-review-unconfigured.json"))
    monkeypatch.setattr(server, "WORKFORCE", registry)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_port}"
        twin = DigitalTwinCoordinator(base, admin)
        worker = DigitalEmployeeAgent(base, token, ["analysis"], FakeExecutor(), "review unavailable")
        result = twin.execute_goal(
            "review unavailable", [worker], max_cycles=2,
            tasks=[{"title": "Analyze risk", "capability": "analysis"}],
            execution_profile={"risk_level": 5, "quality_requirement": 4},
        )
        assert result["execution_decision"]["verification"] == "evidence_gate"
        assert result["status"] == "needs_attention"
        verification = result["tasks"][0]["verification"]
        assert verification["accepted"] is False
        assert any(check["name"] == "source_structure" and not check["passed"]
                   for check in verification["checks"])
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)

def test_high_quality_goal_runs_independent_review_and_rejects_revision(monkeypatch, tmp_path):
    admin, token = "admin-test-token-000000000001", "worker-test-token-000000000002"
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", admin)
    monkeypatch.setenv("JARVIS_WORKER_TOKENS", json.dumps({"analyst": token}))
    monkeypatch.setenv("JARVIS_WORKER_CAPABILITIES", json.dumps({"analyst": ["analysis"]}))
    registry = WorkforceRegistry(path=str(tmp_path / "workforce-review.json"))
    monkeypatch.setattr(server, "WORKFORCE", registry)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    reviews = []

    def reviewer(task, context):
        reviews.append((task.get("title"), context.get("provenance")))
        return {"decision": "revise", "rationale": "Need a counterargument and supporting evidence."}

    try:
        twin = DigitalTwinCoordinator(base, admin)
        worker = DigitalEmployeeAgent(base, token, ["analysis"], FakeExecutor(), "high-quality goal")
        result = twin.execute_goal(
            "high-quality goal", [worker], max_cycles=3,
            tasks=[{
                "title": "Analyze key risk", "capability": "analysis",
                "success_criteria": {"required_phrases": ["simulated test output"]},
            }],
            execution_profile={"risk_level": 5, "quality_requirement": 4},
            independent_reviewer=reviewer,
        )
        assert result["execution_decision"]["verification"] == "independent_review"
        assert result["status"] == "needs_attention"
        assert reviews and reviews[0][0] == "Analyze key risk"
        verification = result["tasks"][0]["verification"]
        assert verification["independent_review"] == "revise"
        assert verification["accepted"] is False
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_twin_recommends_replan_for_blocked_task_without_auto_retry(monkeypatch, tmp_path):
    admin, token = "admin-test-token-000000000031", "worker-test-token-000000000032"
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", admin)
    monkeypatch.setenv("JARVIS_WORKER_TOKENS", json.dumps({"analyst": token}))
    monkeypatch.setenv("JARVIS_WORKER_CAPABILITIES", json.dumps({"analyst": ["analysis"]}))
    registry = WorkforceRegistry(path=str(tmp_path / "workforce-blocked-triage.json"))
    monkeypatch.setattr(server, "WORKFORCE", registry)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    class FailingExecutor:
        def execute(self, task, goal):
            raise RuntimeError("upstream source unavailable")

    try:
        base = f"http://127.0.0.1:{httpd.server_port}"
        twin = DigitalTwinCoordinator(base, admin)
        worker = DigitalEmployeeAgent(base, token, ["analysis"], FailingExecutor(), "recover goal")
        result = twin.execute_goal(
            "recover goal", [worker], max_cycles=3,
            tasks=[{"title": "Analyze source", "capability": "analysis"}],
        )
        assert result["status"] == "needs_attention"
        recommendations = [e for e in result["events"] if e["type"] == "replan_recommended"]
        assert len(recommendations) == 1
        assert recommendations[0]["task_status"] == "blocked"
        assert "upstream source unavailable" in recommendations[0]["reason"]
        assert recommendations[0]["automatic_retry"] is False
        snapshot = registry.snapshot()
        task = next(t for t in snapshot["tasks"] if t["id"] == recommendations[0]["task_id"])
        assert task["status"] == "blocked"
        assert task["attempts"] == 1
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)

def test_twin_can_explicitly_retry_after_revision_policy_reviews_blocker(monkeypatch, tmp_path):
    admin, token = "admin-test-token-000000000041", "worker-test-token-000000000042"
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", admin)
    monkeypatch.setenv("JARVIS_WORKER_TOKENS", json.dumps({"analyst": token}))
    monkeypatch.setenv("JARVIS_WORKER_CAPABILITIES", json.dumps({"analyst": ["analysis"]}))
    registry = WorkforceRegistry(path=str(tmp_path / "workforce-explicit-retry.json"))
    monkeypatch.setattr(server, "WORKFORCE", registry)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    class FailOnceExecutor:
        def __init__(self):
            self.calls = 0

        def execute(self, task, goal):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("source temporarily unavailable")
            return WorkerExecutionResult(
                task_id=task["id"], capability=task["capability"],
                status="completed", output="Source recovered; result collected.",
                simulated=False, metadata={"attempt": self.calls},
            )

    try:
        base = f"http://127.0.0.1:{httpd.server_port}"
        twin = DigitalTwinCoordinator(base, admin)
        executor = FailOnceExecutor()
        worker = DigitalEmployeeAgent(base, token, ["analysis"], executor, "recover goal")
        from mvp.revision_policy import ConservativeTransientRetryPolicy

        result = twin.execute_goal(
            "recover goal", [worker], max_cycles=3,
            tasks=[{"title": "Analyze source", "capability": "analysis"}],
            revision_policy=ConservativeTransientRetryPolicy(),
        )
        assert result["status"] == "completed"
        assert result["counts"]["completed"] == 1
        assert executor.calls == 2
        assert any(event["type"] == "task_retry_approved" for event in result["events"])
        assert any(event["type"] == "replan_recommended" for event in result["events"])
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)

def test_twin_persists_verification_into_traceable_workforce_history(monkeypatch, tmp_path):
    admin, token = "admin-test-token-000000000051", "worker-test-token-000000000052"
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", admin)
    monkeypatch.setenv("JARVIS_WORKER_TOKENS", json.dumps({"analyst": token}))
    monkeypatch.setenv("JARVIS_WORKER_CAPABILITIES", json.dumps({"analyst": ["analysis"]}))
    registry = WorkforceRegistry(path=str(tmp_path / "workforce-verification-trace.json"))
    monkeypatch.setattr(server, "WORKFORCE", registry)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        twin = DigitalTwinCoordinator(f"http://127.0.0.1:{httpd.server_port}", admin)
        worker = DigitalEmployeeAgent(
            f"http://127.0.0.1:{httpd.server_port}", token, ["analysis"],
            FakeExecutor(), "trace verification goal",
        )
        result = twin.execute_goal(
            "trace verification goal", [worker], max_cycles=3,
            tasks=[{"title": "Trace a checked result", "capability": "analysis"}],
        )
        task_id = result["tasks"][0]["task_id"]
        snapshot = registry.snapshot()
        task = next(item for item in snapshot["tasks"] if item["id"] == task_id)
        assert "verification" in task
        assert task["verification"]["accepted"] is True
        assert task["verified_truth"] is False
        assert any(
            event["type"] == "verification_recorded" and event["task_id"] == task_id
            for event in snapshot["events"]
        )
        assert any(
            item.get("event") == "verification_recorded"
            for item in task["history"]
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)

