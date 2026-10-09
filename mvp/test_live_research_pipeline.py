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


def test_live_research_deduplicates_sources_and_llm_synthesis_uses_accepted_evidence():
    source = ResearchSource(
        title="Industry report", url="https://example.com/report#section",
        snippet="The report describes market adoption trends.",
        provider="test_provider",
    )

    class FakeLLM:
        model = "test-model"
        def complete(self, system_prompt, user_prompt):
            assert "source IDs" in system_prompt
            assert "https://example.com/report#section" in user_prompt
            assert "S1" in user_prompt
            return "Market adoption needs further validation [S1]."

    env = {
        "JARVIS_SEARCH_ENDPOINT": "https://search.example/api",
        "JARVIS_LLM_BASE_URL": "https://llm.example/v1",
        "JARVIS_LLM_API_KEY": "test-key",
        "JARVIS_LLM_MODEL": "test-model",
    }
    with patch.dict("os.environ", env), patch(
        "mvp.research.JsonHttpSearchProvider.search",
        return_value=[source, ResearchSource(
            title="Duplicate report", url="https://example.com/report",
            snippet="Duplicate excerpt.", provider="test_provider"
        )],
    ), patch(
        "mvp.llm.OpenAICompatibleLLM.from_environment", return_value=FakeLLM()
    ):
        result = run_live_research("AI native games", 5)

    assert len(result["sources"]) == 1
    assert result["quality"]["accepted"] == 1
    assert result["llm_synthesis"]["status"] == "completed"
    assert "[S1]" in result["llm_synthesis"]["text"]
    assert result["llm_synthesis"]["source_urls"] == ["https://example.com/report#section"]


def test_llm_research_synthesis_skips_when_no_accepted_evidence():
    from mvp.research import _synthesize_with_llm

    result = _synthesize_with_llm("AI native games", [])
    assert result["status"] == "skipped_no_accepted_evidence"
    assert result["text"] is None
