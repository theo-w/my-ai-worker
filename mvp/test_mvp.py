from mvp.run import evaluate, run_worker, WORKERS


def test_team_has_four_workers():
    assert len(WORKERS) == 4


def test_workers_produce_evidence():
    evidence = []
    for worker, capability in WORKERS:
        evidence.extend(run_worker(worker, capability, "AI RPG"))
    assert len(evidence) == 8
    assert all(item.simulated for item in evidence)


def test_empty_evidence_holds_in_strict_mode():
    decision = evaluate("AI RPG", [])
    assert decision.recommendation == "HOLD_FOR_EVIDENCE"
    assert decision.confidence == 42


def test_empty_evidence_allows_only_explicit_demo_handoff():
    decision = evaluate("AI RPG", [], demo_mode=True)
    assert decision.recommendation == "DEMO_GO_TO_PROTOTYPE"
    assert decision.confidence == 50


def test_simulated_evidence_does_not_pass_real_gate():
    evidence = []
    for worker, capability in WORKERS:
        evidence.extend(run_worker(worker, capability, "AI RPG"))
    decision = evaluate("AI RPG", evidence)
    assert decision.recommendation == "HOLD_FOR_EVIDENCE"
    assert decision.confidence == 42



def test_autonomous_loop_completes_tasks_and_ranks_options():
    from mvp.twin import AutonomousProjectLoop
    tasks = [
        {"id": "research", "title": "Research", "status": "queued"},
        {"id": "synthesis", "title": "Synthesis", "status": "queued"},
    ]
    report = AutonomousProjectLoop().run(
        "Validate a product",
        tasks,
        lambda task: "completed: " + task["title"],
        options=[
            {"name": "A", "score": 0.8, "risks": ["higher cost"]},
            {"name": "B", "score": 0.5, "risks": []},
        ],
    )
    assert report["status"] == "completed"
    assert report["completed_tasks"] == 2
    assert report["recommendation"] == "A"


def test_autonomous_loop_pauses_at_approval_boundary():
    from mvp.twin import AutonomousProjectLoop
    tasks = [{"id": "release", "title": "Release", "status": "queued"}]
    report = AutonomousProjectLoop().run(
        "Ship product", tasks, lambda _: "published",
        requested_actions=["external_publication"],
    )
    assert report["status"] == "needs_approval"
    assert tasks[0]["status"] == "queued"
    assert report["questions_for_human"]


def test_persistent_twin_memory_round_trip(tmp_path):
    from mvp.twin import PersistentTwinMemory
    path = str(tmp_path / "memory.json")
    memory = PersistentTwinMemory(path=path)
    memory.remember_preference("decision_style", "evidence_first")
    memory.record_decision("Validate", "Prototype", [{"name": "A"}])
    memory.record_lesson("Validate retention before scaling", "prototype")
    restored = PersistentTwinMemory(path=path)
    assert restored.preferences["decision_style"] == "evidence_first"
    assert restored.decisions[0]["recommendation"] == "Prototype"
    assert "retention" in restored.lessons[0]["lesson"]


def test_demo_mode_allows_labeled_handoff_without_real_evidence():
    evidence = []
    for worker, capability in WORKERS:
        evidence.extend(run_worker(worker, capability, "AI RPG"))
    decision = evaluate("AI RPG", evidence, demo_mode=True)
    assert decision.recommendation == "DEMO_GO_TO_PROTOTYPE"
    assert "demo only" in decision.next_step.lower()
