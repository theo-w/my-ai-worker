from mvp.self_improvement import evaluate_improvement, summarize_outcomes


def test_summary_counts_only_explicitly_verified_successes():
    summary = summarize_outcomes([
        {"status": "completed", "verified": True, "provenance": "live"},
        {"status": "completed", "verified": False, "provenance": "llm"},
        {"status": "blocked", "failure_category": "missing_sources"},
        {"status": "failed", "provenance": "simulated"},
    ])
    assert summary["sample_count"] == 4
    assert summary["verified_successes"] == 1
    assert summary["failure_categories"] == {
        "missing_sources": 1,
        "unspecified": 1,
    }
    assert summary["simulated_count"] == 1
    assert summary["lesson_quality"] == "observed_only"


def test_improvement_is_eligible_for_review_only_after_gate_passes():
    result = evaluate_improvement(
        {"hypothesis": "Require independent source checks"},
        {"score": 0.60},
        {"score": 0.68, "sample_count": 10, "regressions": 0},
    )
    assert result["accepted"] is True
    assert result["decision"] == "eligible_for_review"
    assert abs(result["gain"] - 0.08) < 1e-9
    assert result["auto_applied"] is False
    assert result["requires_human_promotion"] is True


def test_regression_blocks_improvement_even_if_average_score_rises():
    result = evaluate_improvement(
        {"hypothesis": "Change retry policy"},
        {"score": 0.60},
        {"score": 0.75, "sample_count": 10, "regressions": 1},
    )
    assert result["accepted"] is False
    assert "benchmark_regressions_detected" in result["reasons"]


def test_iteration_budget_and_sample_floor_are_enforced():
    result = evaluate_improvement(
        {"hypothesis": "Tune single-agent threshold"},
        {"score": 0.60},
        {"score": 0.80, "sample_count": 2, "regressions": 0},
        iteration=4,
        max_iterations=3,
        min_samples=3,
    )
    assert result["accepted"] is False
    assert "iteration_budget_exceeded" in result["reasons"]
    assert "insufficient_evaluation_samples" in result["reasons"]


def test_missing_hypothesis_and_invalid_score_fail_closed():
    result = evaluate_improvement(
        {},
        {"score": 1.2},
        {"score": 0.9, "sample_count": 5, "regressions": 0},
    )
    assert result["accepted"] is False
    assert "missing_hypothesis" in result["reasons"]
    assert "score_must_be_between_0_and_1" in result["reasons"]
