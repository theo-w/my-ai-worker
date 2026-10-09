import json

from mvp.autonomous import (
    ApprovalPolicy, AutonomousProjectLoop, DecisionOption, ProjectStatus, ProjectTask,
)
from mvp.memory import TwinMemory


def test_loop_executes_tasks_and_compares_options():
    tasks = [ProjectTask("t1", "Research", "research"),
             ProjectTask("t2", "Synthesize", "analysis")]
    options = [DecisionOption("A", "Fast prototype", score=0.8),
               DecisionOption("B", "Broader research", score=0.6)]
    report = AutonomousProjectLoop().run(
        "Validate an AI-native game",
        tasks,
        lambda task: f"done: {task.title}",
        options,
    )
    assert report.status == ProjectStatus.COMPLETED.value
    assert report.completed_tasks == 2
    assert report.recommendation.startswith("Recommend A")
    assert any("Execution iteration" in event for event in report.events)


def test_sensitive_action_pauses_for_approval():
    task = ProjectTask("t1", "Publish", "publishing")
    report = AutonomousProjectLoop().run(
        "Launch product", [task], lambda _: "published",
        requested_actions=["external_publication"],
    )
    assert report.status == ProjectStatus.NEEDS_APPROVAL.value
    assert task.status == "queued"
    assert report.questions_for_human


def test_twin_memory_persists_preferences_decisions_and_lessons(tmp_path):
    path = tmp_path / "memory.json"
    memory = TwinMemory(path=str(path))
    memory.remember_preference("decision_style", "evidence_first")
    memory.record_decision("Validate product", "Prototype", [{"name": "A"}])
    memory.record_lesson("Test retention before scaling", "prototype")
    loaded = TwinMemory(path=str(path))
    assert loaded.preferences["decision_style"] == "evidence_first"
    assert loaded.decisions[0]["recommendation"] == "Prototype"
    assert loaded.lessons[0]["lesson"].startswith("Test retention")
