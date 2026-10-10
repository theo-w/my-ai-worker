from mvp.run import WORKERS
from mvp.twin import (
    AutonomousProjectLoop,
    DigitalTwin,
    PersistentTwinMemory,
)


def test_digital_twin_forms_task_specific_team():
    twin = DigitalTwin()
    team = twin.form_team("评估 AI 原生 RPG", WORKERS)
    assert len(team) == 4
    assert team[0][0] == "Game Market Researcher"


def test_digital_twin_snapshot_contains_policy_and_intent():
    twin = DigitalTwin()
    snapshot = twin.snapshot("AI RPG", WORKERS)
    assert snapshot["name"] == "AI CEO / Digital Twin"
    assert snapshot["intent"] == "AI RPG"
    assert snapshot["policy"]["decision_style"] == "evidence_first"


def test_project_loop_replans_a_failed_task_and_keeps_audit_events():
    loop = AutonomousProjectLoop(max_iterations=3)
    tasks = [{"id": "first", "title": "Inspect project", "status": "queued"}]

    def executor(task):
        if task["id"] == "first":
            raise RuntimeError("temporary failure")
        return "verified test artifact"

    def replanner(goal, failed_tasks, iteration):
        assert goal == "Ship the smallest MVP"
        assert failed_tasks[0]["id"] == "first"
        assert iteration == 1
        return [{"id": "replacement", "title": "Retry with smaller scope", "status": "queued"}]

    report = loop.run(
        "Ship the smallest MVP", tasks, executor, replanner=replanner
    )

    assert report["status"] == "completed"
    assert report["completed_tasks"] == 1
    assert report["superseded_tasks"] == 1
    assert report["tasks"][0]["status"] == "superseded"
    assert report["tasks"][1]["status"] == "completed"
    event_types = [event["type"] for event in report["events"]]
    assert "task_finished" in event_types
    assert "plan_revised" in event_types
    assert event_types[-1] == "checkpoint_created"


def test_project_loop_blocks_high_impact_actions_before_execution():
    loop = AutonomousProjectLoop()
    called = []
    report = loop.run(
        "Deploy to production",
        [{"id": "deploy", "title": "Deploy", "status": "queued"}],
        lambda task: called.append(task) or "should not run",
        requested_actions=["production_release"],
    )

    assert report["status"] == "needs_approval"
    assert called == []
    assert any(event["type"] == "approval_required" for event in report["events"])


def test_persistent_twin_memory_round_trips_preferences_decisions_and_lessons(tmp_path):
    path = tmp_path / "twin-memory.json"
    memory = PersistentTwinMemory(path=str(path))
    memory.remember_preference("delivery_priority", "fastest_mvp")
    decision = memory.record_decision(
        "Ship MVP", "Fix reset and test state consistency",
        alternatives=["Polish animations"], outcome="pending",
    )
    memory.record_lesson("Never equate simulated output with verified evidence", "CI")

    reloaded = PersistentTwinMemory(path=str(path))
    assert reloaded.preferences["delivery_priority"] == "fastest_mvp"
    assert reloaded.decisions[0]["goal"] == "Ship MVP"
    assert reloaded.decisions[0]["recommendation"] == decision["recommendation"]
    assert reloaded.lessons[0]["context"] == "CI"
