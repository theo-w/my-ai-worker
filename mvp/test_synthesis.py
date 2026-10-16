from synthesis import synthesize


def test_synthesis_requires_source_backed_evidence():
    result = synthesize("Should we prototype?", [
        {"worker": "Market", "finding": "Simulated", "confidence": 0.9,
         "quality_accepted": False},
    ])
    assert result.supporting_findings == []
    assert result.evidence_count == 1


def test_synthesis_collects_accepted_findings():
    result = synthesize("Should we prototype?", [
        {"worker": "Market", "finding": "Market signal", "confidence": 0.8,
         "quality_accepted": True},
        {"worker": "Player", "finding": "Player signal", "confidence": 0.9,
         "quality_accepted": True},
    ])
    assert len(result.supporting_findings) == 2
    assert result.conflicts
