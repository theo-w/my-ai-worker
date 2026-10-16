import json

from mvp.verification import verify_task_output


def test_non_empty_plain_output_is_not_claimed_as_verified_truth():
    result = verify_task_output({"id": "t1", "output": "A plausible answer"})
    assert result["accepted"] is True
    assert result["verified_truth"] is False


def test_evidence_gate_rejects_simulated_output():
    result = verify_task_output({
        "id": "t1", "output": json.dumps({
            "content": "sample", "simulated": True, "metadata": {},
        }),
    }, require_evidence=True)
    assert result["accepted"] is False
    assert result["simulated"] is True


def test_evidence_gate_reads_sources_inside_worker_content_envelope():
    result = verify_task_output({
        "id": "t1", "output": json.dumps({
            "content": json.dumps({"accepted_evidence": [{
                "title": "Example source", "url": "https://example.com/source",
                "snippet": "A source excerpt",
            }]}),
            "simulated": False, "metadata": {"mode": "live_research"},
        }),
    }, require_evidence=True)
    assert result["accepted"] is True
    assert result["evidence_count"] == 1
    assert result["verified_truth"] is False


def test_evidence_gate_rejects_source_records_without_explicit_live_provenance():
    result = verify_task_output({
        "id": "t1", "output": json.dumps({
            "sources": [{
                "title": "Example source", "url": "https://example.com/source",
                "snippet": "A source excerpt without executor provenance",
            }],
        }),
    }, require_evidence=True)
    assert result["accepted"] is False
    assert result["provenance"] == "unknown"
    assert any(
        check["name"] == "non_simulated_evidence" and not check["passed"]
        for check in result["checks"]
    )


def test_evidence_gate_rejects_incomplete_source():
    result = verify_task_output({
        "id": "t1", "output": json.dumps({
            "content": json.dumps({"sources": [{"url": "http://example.com"}]}),
            "simulated": False,
        }),
    }, require_evidence=True)
    assert result["accepted"] is False


def test_success_criteria_reject_missing_required_phrase_and_fields():
    result = verify_task_output(
        {"id": "t2", "output": json.dumps({"content": json.dumps({"summary": "alpha"})})},
        success_criteria={"required_phrases": ["beta"], "required_fields": ["summary", "risks"]},
    )
    assert result["accepted"] is False
    assert any(check["name"] == "required_phrases" and not check["passed"] for check in result["checks"])
    assert any(check["name"] == "required_fields" and not check["passed"] for check in result["checks"])


def test_success_criteria_accept_matching_phrase_and_minimum_length():
    result = verify_task_output(
        {"id": "t3", "output": "A report with Alpha finding"},
        success_criteria={"required_phrases": ["alpha finding"], "min_output_chars": 10},
    )
    assert result["accepted"] is True
    assert result["verified_truth"] is False


def test_independent_review_requires_explicit_accept_decision():
    task = {"id": "t4", "output": "Output to review"}
    rejected = verify_task_output(task, independent_reviewer=lambda *_: {
        "decision": "revise", "rationale": "Missing counter-evidence",
    })
    assert rejected["accepted"] is False
    assert rejected["independent_review"] == "revise"

    accepted = verify_task_output(task, independent_reviewer=lambda *_: {
        "decision": "accept", "rationale": "Criteria checked",
    })
    assert accepted["accepted"] is True
    assert accepted["independent_review"] == "accept"
    assert accepted["verified_truth"] is False


def test_independent_review_failure_closed():
    result = verify_task_output(
        {"id": "t5", "output": "Output to review"},
        independent_reviewer=lambda *_: {"decision": "maybe"},
    )
    assert result["accepted"] is False
    assert result["independent_review"] == "invalid_response"
