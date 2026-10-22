"""Tests for persistent, provenance-first game knowledge retrieval."""
import json
import tempfile
import unittest
from pathlib import Path

try:
    from .game_knowledge import GameKnowledgeBase
except ImportError:
    from game_knowledge import GameKnowledgeBase


class GameKnowledgeTests(unittest.TestCase):
    def test_ingests_source_and_retrieves_related_chinese_query(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GameKnowledgeBase(str(Path(directory) / "knowledge.json"))
            result = store.ingest_sources("AI 原生游戏 NPC 记忆", [{
                "title": "Persistent NPC memory in AI games",
                "url": "https://example.com/npc-memory#section",
                "snippet": "NPC memory and player-driven replayability in AI games.",
                "provider": "test",
            }], evidence=[{
                "quality_accepted": True,
                "source": {"url": "https://example.com/npc-memory", "snippet": "source excerpt"},
            }])
            self.assertEqual(result["inserted"], 1)
            matches = store.search("AI 游戏 NPC 记忆", 5)["matches"]
            self.assertTrue(matches)
            self.assertEqual(matches[0]["knowledge_status"], "source_backed_unverified")
            self.assertTrue(matches[0]["quality_accepted_at_capture"])

    def test_deduplicates_by_normalized_url_and_survives_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "knowledge.json")
            store = GameKnowledgeBase(path)
            source = {"title": "Retention", "url": "https://example.com/retention#x",
                      "snippet": "Replayability and retention signals", "provider": "test"}
            first = store.ingest_sources("retention", [source])
            second = store.ingest_sources("retention update", [{**source, "snippet": "Updated excerpt"}])
            self.assertEqual(first["inserted"], 1)
            self.assertEqual(second["updated"], 1)
            reloaded = GameKnowledgeBase(path)
            self.assertEqual(reloaded.count(), 1)
            self.assertEqual(reloaded.search("retention replayability")["matches"][0]["snippet"], "Updated excerpt")

    def test_stable_recrawl_keeps_original_content_and_query(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GameKnowledgeBase(str(Path(directory) / "knowledge.json"))
            first = {"title": "NPC memory in AI games",
                     "url": "https://example.com/npc-memory",
                     "snippet": "Persistent NPC memory enables players to revisit story choices.",
                     "provider": "test"}
            store.ingest_sources("NPC memory feasibility", [first])
            second = {**first, "title": "NPC memory in AI games",
                      "snippet": "Persistent NPC memory enables players to revisit story choices."}
            result = store.ingest_sources("NPC memory market check", [second])
            row = store.search("NPC memory feasibility", 1)["matches"][0]
            self.assertEqual(result["unchanged"], 1)
            self.assertEqual(result["updated"], 0)
            self.assertEqual(row["query"], "NPC memory feasibility")
            self.assertEqual(row["last_check_status"], "no_material_change")
            self.assertEqual(row["seen_count"], 2)

    def test_material_source_change_updates_current_and_emits_history(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GameKnowledgeBase(str(Path(directory) / "knowledge.json"))
            original = {"title": "Game review",
                        "url": "https://example.com/reviews",
                        "snippet": "Players praise the stable performance and engaging story.",
                        "provider": "test"}
            store.ingest_sources("game sentiment", [original])
            changed = {**original, "snippet":
                       "Recent players report severe crashes, broken matchmaking, and falling ratings."}
            result = store.ingest_sources("game sentiment latest", [changed])
            row = store.search("crashes matchmaking ratings", 1)["matches"][0]
            self.assertEqual(result["updated"], 1)
            self.assertEqual(len(result["changes"]), 1)
            self.assertEqual(result["changes"][0]["change_type"], "material_source_update")
            self.assertIn("severe crashes", row["snippet"])
            self.assertEqual(row["last_check_status"], "material_change")
            self.assertEqual(row["query"], "game sentiment latest")

    def test_rejects_invalid_source_and_empty_query(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GameKnowledgeBase(str(Path(directory) / "knowledge.json"))
            result = store.ingest_sources("test", [{"title": "missing URL", "url": "http://invalid", "snippet": "x"}])
            self.assertEqual(result["inserted"], 0)
            self.assertEqual(store.search("")["matches"], [])
            self.assertEqual(store.count(), 0)


if __name__ == "__main__":
    unittest.main()
