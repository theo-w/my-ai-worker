"""Tests for bounded goal-driven planning and server integration."""
import json
from unittest.mock import patch

import pytest
from mvp.planning import deterministic_plan, plan_project, validate_plan

def test_deterministic_plan_has_bounded_actionable_steps():
    plan = deterministic_plan("Evaluate an AI-native RPG")
    assert plan["mode"] == "deterministic_fallback"
    assert 3 <= len(plan["tasks"]) <= 6
    assert len({task["id"] for task in plan["tasks"]}) == len(plan["tasks"])
    assert all(task["status"] == "queued" for task in plan["tasks"])

def test_validate_plan_rejects_invalid_json_and_duplicate_ids():
    with pytest.raises(ValueError, match="valid JSON"):
        validate_plan("not-json")
    with pytest.raises(ValueError, match="unique"):
        validate_plan(json.dumps({"tasks": [{"id": "same", "title": "One", "capability": "research"}, {"id": "same", "title": "Two", "capability": "analysis"}]}))

def test_validate_plan_rejects_unsupported_capability_and_too_many_tasks():
    with pytest.raises(ValueError, match="Unsupported"):
        validate_plan(json.dumps({"tasks": [{"id": "x", "title": "Run shell", "capability": "shell"}]}))
    with pytest.raises(ValueError, match="1 to"):
        validate_plan(json.dumps({"tasks": [{"id": str(i), "title": "Task", "capability": "general"} for i in range(9)]}))

def test_llm_plan_is_validated_before_tasks_are_returned():
    class FakeLLM:
        def complete(self, system_prompt, user_prompt):
            return json.dumps({"tasks": [{"id": "research", "title": "Gather market evidence", "capability": "research"}, {"id": "decision", "title": "Compare options", "capability": "decision"}]})
    plan = plan_project("Evaluate a product", FakeLLM())
    assert plan["mode"] == "llm"
    assert [task["id"] for task in plan["tasks"]] == ["research", "decision"]

def test_llm_plan_failure_falls_back_and_explains_why():
    class BrokenLLM:
        def complete(self, system_prompt, user_prompt):
            raise TimeoutError("unavailable")
    plan = plan_project("Evaluate a product", BrokenLLM())
    assert plan["mode"] == "deterministic_fallback"
    assert any("TimeoutError" in warning for warning in plan["warnings"])

def test_autonomous_api_returns_planning_provenance():
    from mvp import server
    from mvp.executor import SimulatedWorkerExecutor
    original = server.WORKER_EXECUTOR
    try:
        server.WORKER_EXECUTOR = SimulatedWorkerExecutor()
        class FakeHandler:
            def _json(self, payload, code=200):
                self.payload, self.code = payload, code
            def _read_json(self):
                return {"goal": "Evaluate a business opportunity"}
        handler = FakeHandler()
        # Exercise the shared planning + project-loop integration without HTTP sockets.
        body = handler._read_json()
        planning = deterministic_plan(body["goal"])
        tasks = planning["tasks"]
        def executor(task):
            result = server.WORKER_EXECUTOR.execute(task, body["goal"])
            task["execution"] = result.to_dict()
            return result.output
        report = server.PROJECT_LOOP.run(body["goal"], tasks, executor)
        assert planning["mode"] == "deterministic_fallback"
        assert report["total_tasks"] == len(tasks)
        assert report["status"] == "completed"
    finally:
        server.WORKER_EXECUTOR = original
def test_failed_task_replanning_returns_only_valid_new_task_ids():
    from mvp.planning import replan_failed_tasks
    class FakeLLM:
        def complete(self, system_prompt, user_prompt):
            return json.dumps({"tasks": [{"id": "alternate_research", "title": "Use a different evidence source", "capability": "research"}]})
    tasks = replan_failed_tasks("Assess the market", [{"id": "research", "title": "Search web", "output": "Execution failed: TimeoutError"}], 1, FakeLLM(), {"research", "analysis"})
    assert len(tasks) == 1
    assert tasks[0]["id"] == "alternate_research"
    assert tasks[0]["status"] == "queued"

def test_failed_task_replanning_rejects_existing_ids_and_has_safe_fallback():
    from mvp.planning import replan_failed_tasks
    class DuplicateLLM:
        def complete(self, system_prompt, user_prompt):
            return json.dumps({"tasks": [{"id": "research", "title": "Repeat failed search", "capability": "research"}]})
    result = replan_failed_tasks("Assess the market", [{"id": "research", "output": "failed"}], 1, DuplicateLLM(), {"research"})
    assert result == []
    assert replan_failed_tasks("Assess the market", [{"id": "research"}], 1, None, {"research"}) == []

def test_autonomous_request_validation_rejects_malformed_fields():
    from mvp.server import validate_autonomous_request
    invalid_requests = [
        {},
        {"goal": "x" * 2001},
        {"goal": "valid", "tasks": []},
        {"goal": "valid", "tasks": [{"id": "x", "title": "Run arbitrary shell", "capability": "shell"}]},
        {"goal": "valid", "options": [{"name": "A", "score": float("nan")}]},
        {"goal": "valid", "options": "not-an-array"},
        {"goal": "valid", "requested_actions": "production_release"},
    ]
    for body in invalid_requests:
        with pytest.raises(ValueError):
            validate_autonomous_request(body)


def test_autonomous_request_validation_normalizes_valid_payload():
    from mvp.server import validate_autonomous_request
    request = validate_autonomous_request({
        "goal": "  Evaluate a game concept  ",
        "tasks": [{"id": "research", "title": "Collect evidence", "capability": "research"}],
        "options": [{"name": "Prototype", "score": 2}],
        "requested_actions": ["production_release"],
    })
    assert request["goal"] == "Evaluate a game concept"
    assert request["tasks"][0]["id"] == "research"
    assert request["options"][0]["score"] == 2.0
    assert request["requested_actions"] == ["production_release"]
