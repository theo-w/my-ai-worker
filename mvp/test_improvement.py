from copy import deepcopy

from mvp.improvement import build_improvement_report


def test_observe_only_report_proposes_bounded_experiment_for_repeated_blockers():
    snapshot = {
        "tasks": [
            {"id": "a", "status": "blocked", "blocker": "Source temporarily unavailable"},
            {"id": "b", "status": "failed", "blocker": "  SOURCE temporarily   unavailable "},
            {"id": "c", "status": "succeeded", "verified_truth": False},
        ]
    }
    before = deepcopy(snapshot)

    report = build_improvement_report(snapshot)

    assert report["mode"] == "observe_only"
    assert report["metrics"]["task_count"] == 3
    assert report["metrics"]["blocked_or_failed_count"] == 2
    assert report["observations"][0]["signal"] == "repeated_blocker_text"
    assert report["observations"][0]["sample_count"] == 2
    assert report["proposals"][0]["adoption"] == "requires_independent_evaluation_and_human_approval"
    assert report["actions_taken"] == []
    assert snapshot == before


def test_observe_only_report_does_not_overreact_to_single_failure():
    report = build_improvement_report({
        "tasks": [{"task_id": "one", "status": "blocked", "blocker": "Permission denied"}]
    })

    assert report["observations"] == []
    assert report["proposals"] == []
    assert report["actions_taken"] == []


def test_report_identifies_retry_and_validation_signals_without_claiming_truth():
    report = build_improvement_report({
        "tasks": [
            {"id": "retry-1", "status": "failed", "attempts": 2, "blocker": "timeout"},
            {"id": "retry-2", "status": "blocked", "attempts": 3, "blocker": "quota exhausted",
             "verification": {"accepted": False}},
            {"id": "pending", "status": "awaiting_validation"},
            {"id": "done", "status": "completed", "verified_truth": True},
        ]
    })

    signals = {item["signal"] for item in report["observations"]}
    proposal_ids = {item["id"] for item in report["proposals"]}
    assert "repeated_retries" in signals
    assert "rejected_or_blocked_outputs" in signals
    assert "evaluate-retry-policy" in proposal_ids
    assert "evaluate-evidence-contract" in proposal_ids
    assert report["metrics"]["awaiting_validation_count"] == 1
    assert report["metrics"]["verified_truth_count"] == 1
    assert "do not prove root cause" in report["truth_claim"]


def test_report_bounds_inputs_and_proposal_count():
    tasks = [
        {"id": str(i), "status": "blocked", "blocker": "same blocker", "attempts": 2}
        for i in range(30)
    ]
    report = build_improvement_report({"tasks": tasks}, min_samples=1, max_proposals=1)

    assert report["observations"][0]["sample_count"] == 30
    assert len(report["proposals"]) == 1
    assert len(report["observations"][0]["task_ids"]) <= 10
    assert len(report["proposals"][0]["evidence_task_ids"]) <= 10
