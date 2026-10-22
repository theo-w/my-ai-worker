"""Tests for the conservative commercial-feasibility decision gate."""
import unittest

try:
    from .commercial_feasibility import (
        build_feasibility_contract,
        evaluate_commercial_feasibility,
        REQUIRED_DIMENSIONS,
    )
except ImportError:
    from commercial_feasibility import (
        build_feasibility_contract,
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
        "prototype_evidence_refs": [],
        "prototype_plan": {"scope": "One focused playable loop", "steps": ["Build", "Test"], "decision_gates": ["At least 3 of 5 players explain the loop"]},
        "cost_model": {
            "assumptions": ["AI cost per session", "prototype effort"],
            "scenarios": {
                "optimistic": {"prototype_person_weeks": 2, "vertical_slice_person_weeks": 6, "monthly_active_users": 100, "sessions_per_user_month": 20, "input_tokens_per_session": 2500, "output_tokens_per_session": 400, "monthly_model_cost_usd": 1, "prototype_labor_cost_usd": 3000},
                "base": {"prototype_person_weeks": 4, "vertical_slice_person_weeks": 12, "monthly_active_users": 1000, "sessions_per_user_month": 40, "input_tokens_per_session": 5000, "output_tokens_per_session": 800, "monthly_model_cost_usd": 100, "prototype_labor_cost_usd": 6000},
                "conservative": {"prototype_person_weeks": 8, "vertical_slice_person_weeks": 24, "monthly_active_users": 10000, "sessions_per_user_month": 80, "input_tokens_per_session": 10000, "output_tokens_per_session": 1800, "monthly_model_cost_usd": 10000, "prototype_labor_cost_usd": 12000},
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

    def test_missing_cost_model_blocks_go(self):
        report = strong_report()
        report["cost_model"] = {}
        result = evaluate_commercial_feasibility(report)
        self.assertNotEqual(result["decision"], "GO_TO_PROTOTYPE")


if __name__ == "__main__":
    unittest.main()
