"""Integration tests for Digital Twin goal lifecycle endpoints."""
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from mvp import server
from mvp.workforce import WorkforceRegistry


ADMIN = "admin-secret-for-twin-api-tests-0001"
RESEARCHER = "researcher-secret-for-twin-api-tests-0002"


@pytest.fixture
def twin_http(monkeypatch, tmp_path):
    monkeypatch.delenv("JARVIS_PUBLIC_DEMO", raising=False)
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", ADMIN)
    monkeypatch.setenv("JARVIS_WORKER_TOKENS", json.dumps({"researcher": RESEARCHER}))
    monkeypatch.setenv("JARVIS_WORKER_CAPABILITIES", json.dumps({"researcher": ["research"]}))
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


def create_research_goal(base):
    return request_json(base, "/api/twin/goal", ADMIN, {
        "goal": "Research AI-native game demand",
    })


def claim_and_block(base, task_id, blocker):
    status, claimed = request_json(base, "/api/workforce/claim", RESEARCHER, {
        "capabilities": ["research"], "task_id": task_id,
    })
    assert status == 200
    status, blocked = request_json(base, "/api/workforce/report", RESEARCHER, {
        "task_id": task_id, "status": "blocked",
        "lease_token": claimed["task"]["lease_token"], "blocker": blocker,
    })
    assert status == 200
    assert blocked["task"]["status"] == "blocked"


def test_twin_goal_defaults_to_single_employee_and_audits_decision(twin_http):
    base, _ = twin_http
    status, denied = request_json(base, "/api/twin/goal", payload={"goal": "Research AI-native game demand"})
    assert status == 401
    assert denied["ok"] is False

    status, result = create_research_goal(base)
    assert status == 201
    assert result["strategy"] == "single_agent"
    assert result["plan_mode"] == "single_agent_first"
    assert len(result["tasks"]) == 1
    task = result["tasks"][0]
    assert task["capability"] == "research"
    assert task["evidence_required"] is True
    assert task["success_criteria"]["project_id"] == result["project_id"]

    status, snapshot = request_json(base, "/api/workforce", ADMIN)
    assert status == 200
    decision = next(event for event in snapshot["events"] if event["type"] == "twin_decision")
    assert decision["decision"] == "single_agent_first"
    assert decision["planner"] == "deterministic_rules"
    assert decision["llm_used"] is False


def test_twin_review_escalates_unknown_blocker_without_retry(twin_http):
    base, _ = twin_http
    status, goal = create_research_goal(base)
    assert status == 201
    task = goal["tasks"][0]
    claim_and_block(base, task["id"], "Conflicting evidence requires human diagnosis")

    status, review = request_json(base, "/api/twin/review", ADMIN, {
        "project_id": goal["project_id"],
    })
    assert status == 200
    assert review["decision"] == "replan_required"
    assert review["llm_used"] is False
    assert "不会自动重试" in review["reason"]

    status, snapshot = request_json(base, "/api/workforce", ADMIN)
    assert status == 200
    event = next(event for event in reversed(snapshot["events"])
                 if event["type"] == "twin_reviewed" and event["project_id"] == goal["project_id"])
    assert event["decision"] == review["decision"]
    assert event["next_actions"][0]["task_id"] == task["id"]


def test_twin_advance_retries_only_known_transient_failure(twin_http):
    base, _ = twin_http
    status, goal = create_research_goal(base)
    assert status == 201
    task = goal["tasks"][0]
    claim_and_block(base, task["id"], "Search provider temporarily unavailable (HTTP 503)")

    status, advanced = request_json(base, "/api/twin/advance", ADMIN, {
        "project_id": goal["project_id"],
    })
    assert status == 200
    assert advanced["decision"] == "transient_retry_queued"
    assert advanced["action_task_id"] == task["id"]
    assert advanced["llm_used"] is False
    assert advanced["next_actions"][0]["status"] == "queued"

    status, snapshot = request_json(base, "/api/workforce", ADMIN)
    assert status == 200
    task_after = next(item for item in snapshot["tasks"] if item["id"] == task["id"])
    assert task_after["status"] == "queued"
    assert any(event["type"] == "twin_advanced"
               and event["project_id"] == goal["project_id"]
               and event["decision"] == "transient_retry_queued"
               for event in snapshot["events"])


def test_twin_advance_does_not_retry_unknown_blocker(twin_http):
    base, _ = twin_http
    status, goal = create_research_goal(base)
    assert status == 201
    task = goal["tasks"][0]
    claim_and_block(base, task["id"], "Research evidence conflicts; human review required")

    status, advanced = request_json(base, "/api/twin/advance", ADMIN, {
        "project_id": goal["project_id"],
    })
    assert status == 200
    assert advanced["decision"] == "human_review_required"
    assert advanced["action_task_id"] is None

    status, snapshot = request_json(base, "/api/workforce", ADMIN)
    assert status == 200
    task_after = next(item for item in snapshot["tasks"] if item["id"] == task["id"])
    assert task_after["status"] == "blocked"

def test_game_feasibility_template_requires_bilingual_evidence_and_falsifiable_experiment(twin_http):
    base, _ = twin_http
    status, result = request_json(base, "/api/twin/goal", ADMIN, {
        "goal": "Assess whether an AI-native game mechanic is worth prototyping",
        "template": "ai_game_feasibility",
    })
    assert status == 201
    assert result["template"] == "ai_game_feasibility"
    assert result["strategy"] == "single_agent"
    assert len(result["tasks"]) == 1
    task = result["tasks"][0]
    assert task["capability"] == "research"
    assert task["evidence_required"] is True
    criteria = task["success_criteria"]
    assert criteria["bilingual_sources"]["languages"] == ["zh", "en"]
    assert criteria["signal_quality"]["separate_noise_from_demand"] is True
    assert criteria["falsifiable_hypotheses"]["include_counter_evidence"] is True
    assert criteria["prototype_experiment"]["include_method_and_metrics"] is True
    assert criteria["decision_thresholds"]["include_success_failure_and_stop_conditions"] is True
    assert criteria["decision"]["allowed"] == ["GO", "ITERATE", "NO-GO"]
    assert criteria["independent_validation_required"] is True
    assert criteria["verified_truth"] is False
    assert "成功阈值" in task["description"]
    assert "中英文来源" in task["description"]


def test_twin_goal_rejects_unknown_assessment_template(twin_http):
    base, _ = twin_http
    status, result = request_json(base, "/api/twin/goal", ADMIN, {
        "goal": "Evaluate a game opportunity",
        "template": "invented_template",
    })
    assert status == 400
    assert result["ok"] is False
    assert "template must be" in result["error"]

