from mvp.feasibility_pipeline import build_automatic_feasibility_report, build_cost_model
from mvp.commercial_feasibility import REQUIRED_DIMENSIONS, evaluate_commercial_feasibility


def _research(title, url, snippet):
    item = {
        "quality_accepted": True,
        "finding": snippet,
        "source": {"title": title, "url": url, "snippet": snippet, "provider": "test"},
    }
    return {"status": "completed", "quality": {"accepted": 1, "items": [item]}, "sources": [item["source"]]}


def test_auto_assessment_keeps_unknowns_explicit_and_never_claims_truth(monkeypatch):
    monkeypatch.delenv("JARVIS_LLM_INPUT_COST_PER_MILLION_USD", raising=False)
    monkeypatch.delenv("JARVIS_LLM_OUTPUT_COST_PER_MILLION_USD", raising=False)
    monkeypatch.delenv("JARVIS_GAME_DEV_COST_PER_PERSON_WEEK_USD", raising=False)
    primary = _research("Market overview", "https://example.org/report", "A report describes an adoption trend.")
    counter = _research("Risks", "https://example.net/risks", "A report discusses limitations.")
    report = build_automatic_feasibility_report("Assess an AI-native game", primary, counter, {})
    assert report["assessment_status"] == "completed_with_gaps"
    assert set(report["dimensions"]) == set(REQUIRED_DIMENSIONS)
    assert report["dimensions"]["player_value"]["status"] == "unknown"
    assert report["dimensions"]["market_evidence"]["evidence_refs"] == ["S1"]
    assert report["counter_evidence_refs"] == ["C1"]
    assert report["prototype_evidence_refs"] == []
    assert report["cost_model"]["status"] == "partial_estimate"
    assert report["cost_model"]["scenarios"]["base"]["monthly_model_cost_usd"] is None
    result = evaluate_commercial_feasibility(report)
    assert result["decision"] == "INSUFFICIENT_EVIDENCE"
    assert result["verified_truth"] is False


def test_cost_scenarios_are_calculated_only_with_explicit_prices(monkeypatch):
    monkeypatch.setenv("JARVIS_LLM_INPUT_COST_PER_MILLION_USD", "0.2")
    monkeypatch.setenv("JARVIS_LLM_OUTPUT_COST_PER_MILLION_USD", "0.4")
    monkeypatch.setenv("JARVIS_GAME_DEV_COST_PER_PERSON_WEEK_USD", "1500")
    model = build_cost_model()
    assert model["status"] == "priced_estimate"
    assert model["scenarios"]["base"]["monthly_model_cost_usd"] > 0
    assert model["scenarios"]["base"]["prototype_labor_cost_usd"] == 6000
    assert model["scenarios"]["base"]["pricing_configured"] is True
