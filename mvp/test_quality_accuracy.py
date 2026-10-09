"""Quality-gate tests: provenance is necessary but not proof of truth."""
from mvp.quality import score_evidence, evaluate_evidence

def test_valid_https_source_can_pass_mechanical_gate_but_not_claim_truth():
    result = score_evidence({
        "finding": "Claim copied from excerpt", "confidence": 0.8, "simulated": False,
        "source": {"title": "Example", "url": "https://example.com/report", "snippet": "Relevant excerpt"},
    })
    assert result.accepted is True
    assert not any("truth" in reason.lower() for reason in result.reasons)

def test_http_or_missing_source_metadata_cannot_pass_gate():
    for source in [
        {"title": "Example", "url": "http://example.com/report", "snippet": "Relevant excerpt"},
        {"title": "Example", "url": "https://example.com/report", "snippet": ""},
        {"url": "https://example.com/report", "snippet": "Relevant excerpt"},
    ]:
        result = score_evidence({"finding": "Claim", "confidence": 0.95, "simulated": False, "source": source})
        assert result.accepted is False

def test_simulated_source_never_passes_gate_even_with_complete_metadata():
    result = score_evidence({
        "finding": "Demo claim", "confidence": 1.0, "simulated": True,
        "source": {"title": "Example", "url": "https://example.com/report", "snippet": "Relevant excerpt"},
    })
    assert result.accepted is False
    assert any("simulated" in reason for reason in result.reasons)

def test_evaluate_evidence_counts_only_gate_accepted_items():
    report = evaluate_evidence([
        {"finding": "Claim", "confidence": 0.8, "simulated": False, "source": {"title": "Example", "url": "https://example.com", "snippet": "Excerpt"}},
        {"finding": "Demo", "confidence": 0.99, "simulated": True, "source": {"title": "Example", "url": "https://example.com", "snippet": "Excerpt"}},
    ])
    assert report["accepted"] == 1
    assert report["rejected"] == 1