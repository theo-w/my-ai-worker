"""Unit tests for the Supabase-backed game knowledge adapter."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

try:
    from .supabase_game_knowledge import SupabaseGameKnowledgeBase
except ImportError:
    from supabase_game_knowledge import SupabaseGameKnowledgeBase


class FakeResponse:
    def __init__(self, body=b"[]"):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class SupabaseKnowledgeTests(unittest.TestCase):
    def test_loads_and_upserts_through_rest_api(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []

            def fake_urlopen(request, timeout=8):
                calls.append((request.get_method(), request.full_url, request.data))
                if request.get_method() == "GET":
                    return FakeResponse(b"[]")
                return FakeResponse(b"")

            with patch("supabase_game_knowledge.urlopen", fake_urlopen):
                store = SupabaseGameKnowledgeBase(
                    "https://project.supabase.co", "sb_secret_test",
                    path=str(Path(directory) / "knowledge.json"),
                )
                result = store.ingest_sources("NPC memory", [{
                    "title": "NPC memory",
                    "url": "https://example.com/npc",
                    "snippet": "Persistent NPC memory and replayability.",
                    "provider": "test",
                }])
            self.assertEqual(result["inserted"], 1)
            self.assertEqual(store.summary()["storage_backend"], "supabase")
            self.assertEqual(store.summary()["record_count"], 1)
            self.assertEqual(calls[0][0], "GET")
            self.assertEqual(calls[1][0], "POST")
            self.assertNotIn("sb_secret_test", str(store.summary()))

    def test_reports_json_fallback_when_supabase_is_unreachable(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("supabase_game_knowledge.urlopen", side_effect=URLError("offline")):
                store = SupabaseGameKnowledgeBase(
                    "https://project.supabase.co", "sb_secret_test",
                    path=str(Path(directory) / "knowledge.json"),
                )
            summary = store.summary()
            self.assertEqual(summary["storage_backend"], "json_fallback")
            self.assertTrue(summary["storage_error"])
            self.assertNotIn("sb_secret_test", str(summary))


if __name__ == "__main__":
    unittest.main()
