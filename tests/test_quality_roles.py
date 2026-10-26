"""Regression tests for evidence role classification and conservative readiness."""
import unittest

from mvp.quality import classify_source_role, evaluate_evidence


class EvidenceRoleTests(unittest.TestCase):
    def test_community_post_is_primary_signal(self):
        role = classify_source_role({
            "url": "https://www.reddit.com/r/gaming/comments/example/post/",
            "title": "Player feedback",
            "snippet": "I stopped playing because the loop felt repetitive.",
        })
        self.assertEqual(role["source_role"], "primary_user_signal")
        self.assertTrue(role["role_is_heuristic"])

    def test_editorial_article_is_not_primary_user_signal(self):
        role = classify_source_role({
            "url": "https://www.pcgamer.com/example-review/",
            "title": "Review",
            "snippet": "The game has a repetitive loop.",
        })
        self.assertEqual(role["source_role"], "secondary_analysis")

    def test_unknown_source_does_not_count_as_user_demand(self):
        result = evaluate_evidence([{
            "worker": "test",
            "finding": "A claim",
            "confidence": 0.9,
            "simulated": False,
            "source": {
                "url": "https://example.org/post",
                "title": "Some page",
                "snippet": "A snippet",
            },
        }])
        self.assertEqual(result["decision_readiness"], "insufficient_user_demand_evidence")
        self.assertFalse(result["truth_verified"])
        self.assertEqual(result["accepted_source_role_counts"]["primary_user_signal"], 0)

    def test_quality_pass_does_not_claim_truth(self):
        result = evaluate_evidence([{
            "worker": "test",
            "finding": "A claim",
            "confidence": 0.9,
            "simulated": False,
            "source": {
                "url": "https://www.reddit.com/r/gaming/comments/example/post/",
                "title": "Player feedback",
                "snippet": "I stopped playing because the loop felt repetitive.",
            },
        }])
        self.assertFalse(result["truth_verified"])
        self.assertIn("does not prove truth", result["note"])


if __name__ == "__main__":
    unittest.main()
