import unittest

from mvp.execution_strategy import TaskProfile, choose_execution_mode


class AdaptiveExecutionStrategyTests(unittest.TestCase):
    def test_simple_task_prefers_single_agent(self):
        result = choose_execution_mode(TaskProfile())
        self.assertEqual(result.mode, "single_agent")
        self.assertEqual(result.verification, "standard")

    def test_complex_parallelizable_task_uses_team_when_gain_justifies_cost(self):
        result = choose_execution_mode(TaskProfile(
            complexity=5, parallelizable=True, quality_requirement=4,
            risk_level=3, expected_parallel_quality_gain=0.8,
            expected_parallel_time_savings=0.8, team_cost_multiplier=1.5,
        ))
        self.assertEqual(result.mode, "parallel_team")
        self.assertEqual(result.verification, "independent_review")
        self.assertTrue(result.rationale)

    def test_team_not_created_for_low_expected_gain(self):
        result = choose_execution_mode(TaskProfile(
            complexity=5, parallelizable=True, expected_parallel_quality_gain=0.05,
            expected_parallel_time_savings=0.05, team_cost_multiplier=2.0,
        ))
        self.assertEqual(result.mode, "single_agent")

    def test_evidence_gate_is_independent_of_team_choice(self):
        result = choose_execution_mode(TaskProfile(complexity=1, evidence_required=True))
        self.assertEqual(result.mode, "single_agent")
        self.assertEqual(result.verification, "evidence_gate")

    def test_human_approval_overrides_execution_mode(self):
        result = choose_execution_mode(TaskProfile(
            complexity=5, parallelizable=True, human_approval_required=True,
            expected_parallel_quality_gain=1, expected_parallel_time_savings=1,
        ))
        self.assertEqual(result.mode, "approval_required")

    def test_profile_validation(self):
        for kwargs in ({"complexity": 6}, {"expected_parallel_time_savings": 1.1},
                       {"team_cost_multiplier": 0.9}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                TaskProfile(**kwargs)


if __name__ == "__main__":
    unittest.main()
