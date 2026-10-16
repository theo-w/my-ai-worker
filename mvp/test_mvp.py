from mvp.run import evaluate, run_worker, WORKERS


def test_team_has_four_workers():
    assert len(WORKERS) == 4


def test_workers_produce_evidence():
    evidence = []
    for worker, capability in WORKERS:
        evidence.extend(run_worker(worker, capability, "AI RPG"))
    assert len(evidence) == 8
    assert all(item.simulated for item in evidence)


def test_empty_evidence_is_demo_only():
    decision = evaluate("AI RPG", [])
    assert decision.recommendation == "DEMO_GO_TO_PROTOTYPE"
    assert decision.confidence == 50


def test_simulated_evidence_does_not_pass_real_gate():
    evidence = []
    for worker, capability in WORKERS:
        evidence.extend(run_worker(worker, capability, "AI RPG"))
    decision = evaluate("AI RPG", evidence)
    assert decision.recommendation == "HOLD_FOR_EVIDENCE"
    assert decision.confidence == 42
