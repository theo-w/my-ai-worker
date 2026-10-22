from unittest.mock import patch

from mvp.research import ResearchSource, run_live_research_batch


def source(title, url, snippet):
    return ResearchSource(title=title, url=url, snippet=snippet, provider="test_provider")


def test_batch_research_covers_multiple_angles_and_deduplicates_sources():
    first = source("Competitor overview", "https://example.com/market", "The report compares existing games and their market positioning.")
    duplicate = source("Same report", "https://example.com/market#section", "Duplicate excerpt.")
    player = source("Player feedback", "https://players.example.org/reviews", "Players discuss the value and limitations of persistent NPC memory.")

    def fake_search(self, query, limit=5):
        if "competitors" in query:
            return [first, duplicate]
        if "target players" in query:
            return [player]
        if "cost" in query:
            return [first]
        return []

    queries = [
        "AI RPG competitors existing games market alternatives",
        "AI RPG target players needs user feedback reviews",
        "AI RPG cost and counter evidence",
    ]
    with patch.dict("os.environ", {"JARVIS_SEARCH_ENDPOINT": "https://search.example/api"}, clear=True), patch(
        "mvp.research.JsonHttpSearchProvider.search", new=fake_search
    ):
        result = run_live_research_batch(queries, 3)

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert len(result["queries"]) == 3
    assert len(result["sources"]) == 2
    assert result["coverage"]["requested_angles"] == 3
    assert result["coverage"]["successful_angles"] == 3
    assert result["coverage"]["comprehensive"] is True
    assert len(result["sources"][0]["research_queries"]) == 2


def test_batch_research_surfaces_partial_provider_failures():
    first = source("Competitor overview", "https://example.com/market", "The report compares existing games and their market positioning.")

    def fake_search(self, query, limit=5):
        if "cost" in query:
            raise TimeoutError("provider timeout")
        return [first]

    with patch.dict("os.environ", {"JARVIS_SEARCH_ENDPOINT": "https://search.example/api"}, clear=True), patch(
        "mvp.research.JsonHttpSearchProvider.search", new=fake_search
    ):
        result = run_live_research_batch([
            "AI RPG competitor market",
            "AI RPG cost risks",
        ], 3)

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert len(result["query_errors"]) == 1
    assert result["coverage"]["successful_angles"] == 1
    assert result["coverage"]["comprehensive"] is False


def test_batch_research_without_provider_fails_closed():
    with patch.dict("os.environ", {}, clear=True):
        result = run_live_research_batch(["AI native game market"])

    assert result["ok"] is False
    assert result["status"] == "provider_unconfigured"
    assert result["sources"] == []
    assert result["quality"]["accepted"] == 0
    assert result["queries"] == ["AI native game market"]
