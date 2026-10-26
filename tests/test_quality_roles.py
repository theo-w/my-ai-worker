"""Regression tests for evidence role classification and conservative readiness."""
import unittest

from mvp.quality import classify_source_role, evaluate_evidence
from mvp.commercial_feasibility import build_feasibility_draft


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

    def test_media_article_is_never_original_user_demand(self):
        result = evaluate_evidence([{
            "worker": "research",
            "finding": "An editorial claim",
            "confidence": 0.9,
            "simulated": False,
            "source": {
                "url": "https://www.pcgamer.com/example-review/",
                "title": "Editorial review",
                "snippet": "Players may dislike the loop.",
            },
        }])
        row = result["items"][0]
        self.assertEqual(row["source_role"], "secondary_analysis")
        self.assertFalse(row["user_demand_eligible"])
        self.assertEqual(result["accepted_user_demand_records"], 0)
        self.assertEqual(result["raw_user_content_records"], 0)
        self.assertEqual(result["decision_readiness"], "insufficient_user_demand_evidence")

    def test_search_snippet_on_user_platform_is_not_raw_review_record(self):
        result = evaluate_evidence([{
            "worker": "research",
            "finding": "A player comment excerpt",
            "confidence": 0.9,
            "simulated": False,
            "source": {
                "url": "https://www.reddit.com/r/gaming/comments/example/post/",
                "title": "Player post",
                "snippet": "The game loop is repetitive.",
            },
        }])
        row = result["items"][0]
        self.assertFalse(row["user_demand_eligible"])
        self.assertFalse(row["raw_user_content_available"])
        self.assertIn("搜索摘要不算原始评价数据", row["user_demand_eligibility_reason"])

    def test_raw_user_record_requires_identifiers_and_collection_method(self):
        source = {
            "url": "https://www.reddit.com/r/gaming/comments/example/post/",
            "title": "Player post",
            "snippet": "The game loop is repetitive.",
            "raw_review_text": "The game loop is repetitive.",
            "review_id": "reddit-comment-123",
            "review_created_at": "2026-10-20T12:00:00Z",
            "collection_method": "official API",
        }
        result = evaluate_evidence([{
            "worker": "research", "finding": source["raw_review_text"],
            "confidence": 0.9, "simulated": False, "source": source,
        }])
        row = result["items"][0]
        self.assertTrue(row["user_demand_eligible"])
        self.assertTrue(row["raw_user_content_available"])
        self.assertEqual(result["accepted_user_demand_records"], 1)

    def test_media_only_feasibility_draft_has_original_user_review_blocker(self):
        draft = build_feasibility_draft("AI 游戏玩法可行性", sources=[{
            "url": "https://www.pcgamer.com/example-review/",
            "title": "Editorial review",
            "snippet": "A media analysis of the game.",
            "provider": "test",
        }])
        self.assertEqual(draft["report"]["original_user_review_record_count"], 0)
        self.assertEqual(draft["report"]["user_demand_evidence_status"], "missing_original_user_reviews")
        self.assertTrue(any("原始用户评价" in blocker for blocker in draft["completion"]["blockers"]))

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
