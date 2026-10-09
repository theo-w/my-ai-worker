from unittest.mock import patch

from mvp.research import ResearchSource, run_live_research


def test_live_research_without_provider_is_explicitly_unavailable():
    with patch.dict("os.environ", {}, clear=True):
        result = run_live_research("AI native games")
    assert result["ok"] is False
    assert result["status"] == "provider_unconfigured"
    assert result["sources"] == []
    assert result["quality"]["accepted"] == 0
    assert "no real research" in result["message"]


def test_live_research_runs_quality_and_synthesis_pipeline():
    source = ResearchSource(
        title="Industry report", url="https://example.com/report",
        snippet="The report describes market adoption trends.",
        provider="test_provider",
    )
    with patch.dict("os.environ", {"JARVIS_SEARCH_ENDPOINT": "https://search.example/api"}), patch(
        "mvp.research.JsonHttpSearchProvider.search", return_value=[source]
    ):
        result = run_live_research("AI native games", 3)
    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["quality"]["accepted"] == 1
    assert result["synthesis"]["evidence_count"] == 1
    assert result["synthesis"]["supporting_findings"] == [
        "The report describes market adoption trends."
    ]


def test_live_research_provider_error_is_not_reported_as_success():
    with patch.dict("os.environ", {"JARVIS_SEARCH_ENDPOINT": "https://search.example/api"}), patch(
        "mvp.research.JsonHttpSearchProvider.search", side_effect=TimeoutError("timeout")
    ):
        result = run_live_research("AI native games")
    assert result["ok"] is False
    assert result["status"] == "provider_error"
    assert result["sources"] == []
