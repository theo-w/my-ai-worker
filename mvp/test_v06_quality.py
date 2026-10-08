"""v0.6 evidence quality gate smoke tests."""
from quality import evaluate_evidence


def test_simulated_evidence_is_not_real_research():
    result = evaluate_evidence([
        {
            "worker": "Player Researcher",
            "finding": "Example finding",
            "confidence": 0.8,
            "simulated": True,
            "source": None,
        }
    ])
    assert result["accepted"] == 0
    assert result["rejected"] == 1


def test_source_backed_evidence_can_pass():
    result = evaluate_evidence([
        {
            "worker": "Market Researcher",
            "finding": "Example finding",
            "confidence": 0.9,
            "simulated": False,
            "source": {
                "title": "Example source",
                "url": "https://example.com/report",
                "snippet": "Relevant excerpt",
            },
        }
    ])
    assert result["accepted"] == 1
    assert result["coverage"] == 1.0
