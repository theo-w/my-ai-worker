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
    monkeypatch.delenv("JARVIS_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("JARVIS_LLM_MODEL", raising=False)
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



def test_model_assessment_rejects_unknown_source_ids_and_requires_direct_evidence():
    import json
    from mvp.feasibility_pipeline import analyze_feasibility_with_llm

    dimensions = {
        name: {"score": 3, "evidence_refs": ["S1"], "rationale": "Source suggests a plausible hypothesis.", "confidence": "low"}
        for name in REQUIRED_DIMENSIONS
    }
    dimensions["player_value"] = {"score": 5, "evidence_refs": ["FAKE-999"], "rationale": "Unsupported player demand.", "confidence": "high"}
    class FakeLLM:
        def complete(self, system_prompt, user_prompt):
            assert "Never invent user interviews" in system_prompt
            assert "[S1]" in user_prompt and "[C1]" in user_prompt
            return json.dumps({"dimensions": dimensions, "unresolved_questions": ["Run a player test."]})

    primary = _research("Market overview", "https://example.org/report", "A report describes an adoption trend.")
    counter = _research("Risks", "https://example.net/risks", "A report discusses limitations.")
    analysis = analyze_feasibility_with_llm("Assess an AI-native game", primary, counter, {}, FakeLLM())
    assert analysis["dimensions"]["market_evidence"]["score"] == 3
    assert analysis["dimensions"]["player_value"]["score"] is None
    assert analysis["dimensions"]["player_value"]["evidence_refs"] == []
    report = build_automatic_feasibility_report("Assess an AI-native game", primary, counter, {}, analysis)
    assert report["dimensions"]["market_evidence"]["score"] == 3
    assert report["dimensions"]["player_value"]["status"] == "unknown"
    assert report["dimensions"]["retention_and_replayability"]["status"] == "unknown"
    assert report["analysis_mode"] == "model_assisted_review"



def test_known_deepseek_model_uses_documented_peak_rate_snapshot(monkeypatch):
    monkeypatch.setenv("JARVIS_LLM_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("JARVIS_LLM_MODEL", "deepseek-flash")
    monkeypatch.delenv("JARVIS_LLM_INPUT_COST_PER_MILLION_USD", raising=False)
    monkeypatch.delenv("JARVIS_LLM_OUTPUT_COST_PER_MILLION_USD", raising=False)
    monkeypatch.delenv("JARVIS_GAME_DEV_COST_PER_PERSON_WEEK_USD", raising=False)
    model = build_cost_model()
    assert model["pricing_inputs"]["input_cost_per_million_tokens_usd"] == 0.30
    assert model["pricing_inputs"]["output_cost_per_million_tokens_usd"] == 1.20
    assert model["pricing_inputs"]["source_url"] == "https://api-docs.deepseek.com/quick_start/pricing/"
    assert model["scenarios"]["base"]["monthly_model_cost_usd"] > 0
    assert model["scenarios"]["base"]["prototype_labor_cost_assumption_usd"] == 6000
    assert model["scenarios"]["base"]["prototype_labor_cost_usd"] is None


def test_unknown_provider_model_does_not_guess_token_prices(monkeypatch):
    monkeypatch.setenv("JARVIS_LLM_BASE_URL", "https://provider.example/v1")
    monkeypatch.setenv("JARVIS_LLM_MODEL", "custom-model")
    monkeypatch.delenv("JARVIS_LLM_INPUT_COST_PER_MILLION_USD", raising=False)
    monkeypatch.delenv("JARVIS_LLM_OUTPUT_COST_PER_MILLION_USD", raising=False)
    model = build_cost_model()
    assert model["pricing_inputs"]["input_cost_per_million_tokens_usd"] is None
    assert model["pricing_inputs"]["output_cost_per_million_tokens_usd"] is None
    assert model["scenarios"]["base"]["monthly_model_cost_usd"] is None
