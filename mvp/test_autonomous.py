import json

from mvp.autonomous import (
    ApprovalPolicy, AutonomousProjectLoop, DecisionOption, ProjectStatus, ProjectTask,
)
from mvp.memory import TwinMemory, DecisionRecord


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


def test_twin_memory_persists_decisions_and_lessons(tmp_path):
    path = tmp_path / "memory.json"
    memory = TwinMemory(path=str(path))
    memory.remember("decision_style=evidence_first", kind="preference")
    memory.record_decision(DecisionRecord(
        goal="Validate product",
        recommendation="Prototype",
        confidence=70,
        rationale="Test demand cheaply",
    ))
    memory.remember("Test retention before scaling", kind="lesson")
    loaded = TwinMemory(path=str(path))
    assert loaded.recall("decision_style")[0].content == "decision_style=evidence_first"
    assert loaded.recent_decisions()[0].recommendation == "Prototype"
    assert "retention" in loaded.recall("retention")[0].content
