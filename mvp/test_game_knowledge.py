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

    def test_rejects_invalid_source_and_empty_query(self):
        with tempfile.TemporaryDirectory() as directory:
            store = GameKnowledgeBase(str(Path(directory) / "knowledge.json"))
            result = store.ingest_sources("test", [{"title": "missing URL", "url": "http://invalid", "snippet": "x"}])
            self.assertEqual(result["inserted"], 0)
            self.assertEqual(store.search("")["matches"], [])
            self.assertEqual(store.count(), 0)


if __name__ == "__main__":
    unittest.main()
