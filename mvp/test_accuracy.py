"""Tests for provenance labels and conservative evidence decisions."""
from mvp.accuracy import classify_output, decision_gate, validate_source_record

def test_llm_output_is_never_auto_classified_as_verified_evidence():
    result = classify_output("llm")
    assert result["trust_level"] == "model_generated_unverified"
    assert result["verified_truth"] is False
    assert result["usable_as_factual_evidence"] is False

def test_simulated_and_tool_outputs_keep_explicit_trust_labels():
    assert classify_output("simulation", simulated=True)["trust_level"] == "simulated"
    assert classify_output("tool")["trust_level"] == "tool_output_unverified"
    accepted = classify_output("research", source_backed=True, quality_accepted=True)
    assert accepted["trust_level"] == "quality_gated_source"
    assert accepted["verified_truth"] is False

def test_source_validator_checks_structure_not_truth():
    ok, reasons = validate_source_record({"title": "Example", "url": "https://example.com/a", "snippet": "A short excerpt"})
    assert ok is True and reasons == []
    ok, reasons = validate_source_record({"title": "Example", "url": "javascript:alert(1)", "snippet": ""})
    assert ok is False
    assert any("HTTPS" in reason for reason in reasons)

def test_decision_gate_fails_closed_for_simulation_and_insufficient_evidence():
    assert decision_gate(required_evidence=2, accepted_evidence=5, all_evidence_simulated=True, policy_checks_passed=True)["status"] == "demo_only"
    assert decision_gate(required_evidence=2, accepted_evidence=1, all_evidence_simulated=False, policy_checks_passed=True)["status"] == "hold_for_evidence"
    assert decision_gate(required_evidence=1, accepted_evidence=1, all_evidence_simulated=False, policy_checks_passed=False)["allowed"] is False

def test_llm_executor_marks_generated_text_as_unverified():
    from mvp.executor import LLMWorkerExecutor
    class FakeLLM:
        model = "test-model"
        def complete(self, system_prompt, user_prompt):
            return "The market is growing rapidly."
    result = LLMWorkerExecutor(FakeLLM()).execute({"id": "analysis", "capability": "analysis"}, "Assess market")
    data = result.to_dict()
    assert data["metadata"]["trust_level"] == "model_generated_unverified"
    assert data["metadata"]["verified_truth"] is False
    assert data["metadata"]["usable_as_factual_evidence"] is False
    assert data["metadata"]["external_tools_used"] is False