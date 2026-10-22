"""Tests for the conservative commercial-feasibility decision gate."""
import unittest
from unittest.mock import patch

try:
    from .commercial_feasibility import (
        build_feasibility_contract,
        build_feasibility_draft,
        estimate_model_usage_costs,
        apply_feasibility_gate,
        evaluate_commercial_feasibility,
        REQUIRED_DIMENSIONS,
    )
except ImportError:
    from commercial_feasibility import (
        build_feasibility_contract,
        build_feasibility_draft,
        estimate_model_usage_costs,
        apply_feasibility_gate,
        evaluate_commercial_feasibility,
        REQUIRED_DIMENSIONS,
    )


def strong_report():
    return {
        "dimensions": {
            name: {"score": 4, "evidence_refs": ["evidence-1"], "rationale": "Supported by reviewed evidence"}
            for name in REQUIRED_DIMENSIONS
        },
        "independent_source_count": 4,
        "prototype_evidence_refs": ["prototype-test-1"],
        "cost_model": {
            "assumptions": ["Illustrative model price and usage assumptions; validate against provider invoices."],
            "scenarios": {
                "conservative": {
                "prototype_cost_usd": 5000,
                "model_cost_per_session_usd": 0.02,
                "monthly_cost_usd_at_1000_users": 600,
                "monthly_revenue_usd_at_1000_users": 1500,
                "break_even_users": 400,
                "gross_margin_percent": 60,
            },
                "base": {
                "prototype_cost_usd": 5000,
                "model_cost_per_session_usd": 0.02,
                "monthly_cost_usd_at_1000_users": 600,
                "monthly_revenue_usd_at_1000_users": 1500,
                "break_even_users": 400,
                "gross_margin_percent": 60,
            },
                "optimistic": {
                "prototype_cost_usd": 5000,
                "model_cost_per_session_usd": 0.02,
                "monthly_cost_usd_at_1000_users": 600,
                "monthly_revenue_usd_at_1000_users": 1500,
                "break_even_users": 400,
                "gross_margin_percent": 60,
            },
            },
        },
        "counter_evidence_refs": ["counter-1"],
    }


class CommercialFeasibilityTests(unittest.TestCase):
    def test_contract_exposes_grill_me_questions_and_dimensions(self):
        contract = build_feasibility_contract("评估 AI 原生玩法", budget=1000, timebox_days=14)
        self.assertEqual(contract["status"], "contract_ready")
        self.assertEqual(set(contract["dimensions"]), set(REQUIRED_DIMENSIONS))
        self.assertTrue(contract["questions"]["unit_economics"])
        self.assertEqual(contract["budget_limit"], 1000)

    def test_automatic_draft_marks_unknowns_and_costs_incomplete(self):
        draft = build_feasibility_draft(
            "评估长期记忆 NPC RPG",
            sources=[{
                "title": "Market report",
                "url": "https://example.org/report",
                "provider": "test",
                "research_queries": ["competitors", "counter evidence"],
            }],
        )
        self.assertFalse(draft["completion"]["complete"])
        self.assertEqual(draft["evaluation"]["decision"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(draft["report"]["independent_source_count"], 0)
        self.assertEqual(len(draft["report"]["dimensions"]), len(REQUIRED_DIMENSIONS))
        self.assertEqual(draft["report"]["candidate_counter_evidence_refs"], ["S1"])
        self.assertEqual(draft["report"]["counter_evidence_refs"], [])
        self.assertEqual(draft["report"]["cost_model"]["status"], "needs_inputs")
        self.assertTrue(any("成本情景" in item for item in draft["completion"]["blockers"]))

    def test_generic_go_is_blocked_until_feasibility_gate_is_complete(self):
        draft = build_feasibility_draft("评估长期记忆 NPC RPG")
        decision = apply_feasibility_gate(
            {"recommendation": "GO_TO_PROTOTYPE", "confidence": 78, "risks": [], "next_step": "prototype"},
            draft,
        )
        self.assertEqual(decision["recommendation"], "HOLD_FOR_EVIDENCE")
        self.assertLessEqual(decision["confidence"], 50)
        self.assertIn("成本情景", " ".join(draft["completion"]["blockers"]))

    def test_demo_handoff_stays_explicitly_demo_only(self):
        draft = build_feasibility_draft("Evaluate an AI-native game")
        decision = apply_feasibility_gate(
            {"recommendation": "DEMO_GO_TO_PROTOTYPE", "confidence": 50, "risks": [], "next_step": "demo"},
            draft,
        )
        self.assertEqual(decision["recommendation"], "DEMO_GO_TO_PROTOTYPE")
        self.assertIn("模拟演示", " ".join(decision["risks"]))
        self.assertIn("仅限演示", decision["next_step"])

    def test_deepseek_flash_usage_cost_estimate_uses_official_peak_rates(self):
        with patch.dict("os.environ", {
            "JARVIS_LLM_BASE_URL": "https://api.deepseek.com/v1",
            "JARVIS_LLM_MODEL": "deepseek-flash",
        }, clear=True):
            estimate = estimate_model_usage_costs()
        self.assertEqual(estimate["status"], "estimated")
        self.assertEqual(estimate["scenarios"]["conservative"]["input_rate_usd_per_million_tokens"], 0.30)
        self.assertEqual(estimate["scenarios"]["conservative"]["output_rate_usd_per_million_tokens"], 1.20)
        self.assertGreater(
            estimate["scenarios"]["conservative"]["monthly_ai_inference_cost_usd_at_1000_users"],
            estimate["scenarios"]["base"]["monthly_ai_inference_cost_usd_at_1000_users"],
        )
        self.assertGreater(
            estimate["scenarios"]["base"]["monthly_ai_inference_cost_usd_at_1000_users"],
            estimate["scenarios"]["optimistic"]["monthly_ai_inference_cost_usd_at_1000_users"],
        )
        self.assertIn("api-docs.deepseek.com", estimate["pricing_source"])

    def test_retired_deepseek_alias_is_not_given_a_fabricated_estimate(self):
        estimate = estimate_model_usage_costs("deepseek-chat", "https://api.deepseek.com/v1")
        self.assertEqual(estimate["status"], "deprecated_model_alias")
        self.assertIn("deepseek-flash", estimate["message"])

    def test_configured_rates_support_other_llm_providers(self):
        with patch.dict("os.environ", {
            "JARVIS_LLM_INPUT_USD_PER_MILLION_TOKENS": "0.5",
            "JARVIS_LLM_OUTPUT_USD_PER_MILLION_TOKENS": "1.5",
        }, clear=True):
            estimate = estimate_model_usage_costs("custom-model", "https://llm.example/v1")
        self.assertEqual(estimate["status"], "estimated")
        self.assertEqual(estimate["pricing_mode"], "configured_flat_rates")

    def test_missing_evidence_never_passes(self):
        result = evaluate_commercial_feasibility({"dimensions": {}})
        self.assertEqual(result["decision"], "INSUFFICIENT_EVIDENCE")
        self.assertTrue(result["missing_dimensions"])
        self.assertFalse(result["verified_truth"])

    def test_strong_complete_report_only_passes_to_prototype(self):
        result = evaluate_commercial_feasibility(strong_report())
        self.assertEqual(result["decision"], "GO_TO_PROTOTYPE")
        self.assertFalse(result["verified_truth"])
        self.assertTrue(any(c["name"] == "cost_model" and c["passed"] for c in result["checks"]))

    def test_weak_dimension_requests_iteration_not_automatic_no_go(self):
        report = strong_report()
        report["dimensions"]["player_value"]["score"] = 1
        result = evaluate_commercial_feasibility(report)
        self.assertEqual(result["decision"], "ITERATE")
        self.assertIn("player_value", result["weak_dimensions"])

    def test_explicit_critical_blocker_can_return_no_go(self):
        report = strong_report()
        report["critical_blockers"] = [{"reason": "Core mechanic cannot be delivered within legal constraints"}]
        result = evaluate_commercial_feasibility(report)
        self.assertEqual(result["decision"], "NO_GO")

    def test_empty_cost_scenarios_do_not_pass_cost_gate(self):
        report = strong_report()
        report["cost_model"]["scenarios"] = {
            "conservative": {}, "base": {}, "optimistic": {}
        }
        result = evaluate_commercial_feasibility(report)
        cost_check = next(c for c in result["checks"] if c["name"] == "cost_model")
        self.assertFalse(cost_check["passed"])
        self.assertTrue(cost_check["errors"])
        self.assertNotEqual(result["decision"], "GO_TO_PROTOTYPE")

    def test_missing_cost_model_blocks_go(self):
        report = strong_report()
        report["cost_model"] = {}
        result = evaluate_commercial_feasibility(report)
        self.assertNotEqual(result["decision"], "GO_TO_PROTOTYPE")


if __name__ == "__main__":
    unittest.main()
