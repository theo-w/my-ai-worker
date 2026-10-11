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


def test_evidence_gate_rejects_incomplete_source():
    result = verify_task_output({
        "id": "t1", "output": json.dumps({
            "content": json.dumps({"sources": [{"url": "http://example.com"}]}),
            "simulated": False,
        }),
    }, require_evidence=True)
    assert result["accepted"] is False
