from unittest.mock import patch

import json
import pytest

from mvp.research import JsonHttpSearchProvider, ResearchAdapter, ResearchSource, research_environment_status


def test_research_adapter_without_provider_returns_no_sources():
    adapter = ResearchAdapter()
    assert adapter.available is False
    assert adapter.search_sources("market size") == []


def test_json_http_provider_parses_source_results():
    provider = JsonHttpSearchProvider("https://search.example/api", api_key="secret")
    payload = {"results": [{
        "title": "Market report", "url": "https://example.com/report",
        "snippet": "A source excerpt", "published_at": "2026-09-01"
    }]}
    class FakeResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps(payload).encode()

    with patch("urllib.request.urlopen", return_value=FakeResponse()) as urlopen:
        results = provider.search("AI games", 3)
    assert len(results) == 1
    assert isinstance(results[0], ResearchSource)
    assert results[0].title == "Market report"
    assert results[0].provider == "json_http"
    request = urlopen.call_args.args[0]
    assert request.get_header("Authorization") == "Bearer secret"


def test_provider_requires_https():
    with pytest.raises(ValueError):
        JsonHttpSearchProvider("http://insecure.example/api")


def test_environment_status_does_not_expose_api_key():
    with patch.dict("os.environ", {
        "JARVIS_SEARCH_ENDPOINT": "https://search.example/api",
        "JARVIS_SEARCH_API_KEY": "do-not-print"
    }):
        status = research_environment_status()
    assert status["configured"] is True
    assert "do-not-print" not in str(status)
