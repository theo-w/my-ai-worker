"""End-to-end acceptance checks for JARVIS autonomous project loop."""
from mvp.twin import AutonomousProjectLoop, PersistentTwinMemory


def test_goal_to_checkpoint_and_multiple_options():
    tasks = [
        {"id": "research", "title": "Collect evidence", "status": "queued"},
        {"id": "decision", "title": "Compare options", "status": "queued"},
    ]
    calls = []

    def executor(task):
        calls.append(task["id"])
        return "artifact:" + task["id"]

    report = AutonomousProjectLoop().run(
        "Evaluate a new product",
        tasks,
        executor,
        options=[
            {"name": "Lean prototype", "score": 0.82, "risks": ["limited scope"]},
            {"name": "Full launch", "score": 0.43, "risks": ["high cost"]},
        ],
    )
    assert report["status"] == "completed"
    assert report["completed_tasks"] == report["total_tasks"] == 2
    assert calls == ["research", "decision"]
    assert report["recommendation"] == "Lean prototype"
    assert report["events"][-1]["type"] == "checkpoint_created"


def test_failure_is_visible_and_does_not_fake_success():
    tasks = [
        {"id": "ok", "title": "Prepare input", "status": "queued"},
        {"id": "blocked", "title": "Need unavailable tool", "status": "queued"},
    ]

    def executor(task):
        if task["id"] == "blocked":
            raise RuntimeError("tool unavailable")
        return "prepared artifact"

    report = AutonomousProjectLoop().run("Test recovery", tasks, executor)
    assert report["status"] == "blocked"
    assert report["completed_tasks"] == 1
    assert any("受阻" in question for question in report["questions_for_human"])
    assert tasks[1]["output"] == "Execution failed: RuntimeError"


def test_sensitive_action_pauses_before_execution():
    tasks = [{"id": "publish", "title": "Publish", "status": "queued"}]
    called = []
    report = AutonomousProjectLoop().run(
        "Release project", tasks, lambda task: called.append(task) or "published",
        requested_actions=["external_publication"],
    )
    assert report["status"] == "needs_approval"
    assert called == []
    assert tasks[0]["status"] == "queued"


def test_twin_memory_survives_reload(tmp_path):
    path = str(tmp_path / "twin-memory.json")
    memory = PersistentTwinMemory(path=path)
    memory.remember_preference("decision_style", "evidence_first")
    memory.record_decision("Evaluate product", "Lean prototype", [{"name": "Full launch"}])
    memory.record_lesson("Validate demand before scaling", "product validation")

    restored = PersistentTwinMemory(path=path)
    assert restored.preferences["decision_style"] == "evidence_first"
    assert restored.decisions[0]["recommendation"] == "Lean prototype"
    assert "Validate demand" in restored.lessons[0]["lesson"]
