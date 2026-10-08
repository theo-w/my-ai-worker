from mvp.run import evaluate, run_worker, WORKERS


def test_team_has_four_workers():
    assert len(WORKERS) == 4


def test_workers_produce_evidence():
    evidence = []
    for worker, capability in WORKERS:
        evidence.extend(run_worker(worker, capability, "AI RPG"))
    assert len(evidence) == 8
    assert all(item.simulated for item in evidence)


def test_decision_goes_to_prototype():
    decision = evaluate("AI RPG", [])
    assert decision.recommendation == "GO_TO_PROTOTYPE"
    assert decision.confidence == 78
    assert decision.next_step == "AI Game Prototype Sprint"
