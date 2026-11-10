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


def test_json_http_provider_parses_github_items():
    """GitHub 搜索 API:items/full_name/html_url/description(可为 null)应被正确归一化。"""
    provider = JsonHttpSearchProvider("https://api.github.com/search/repositories")
    payload = {"total_count": 2, "items": [
        {"full_name": "org/repo", "name": "repo",
         "html_url": "https://github.com/org/repo",
         "description": "AI game tooling",
         "pushed_at": "2026-10-01T00:00:00Z"},
        {"full_name": "org/nodesc", "name": "nodesc",
         "html_url": "https://github.com/org/nodesc",
         "description": None, "pushed_at": None},
    ]}

    class FakeResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return json.dumps(payload).encode()

    with patch("urllib.request.urlopen", return_value=FakeResponse()) as urlopen:
        results = provider.search("ai game", 5)
    assert [r.title for r in results] == ["org/repo", "org/nodesc"]
    assert [r.url for r in results] == ["https://github.com/org/repo", "https://github.com/org/nodesc"]
    assert all(r.provider == "github" for r in results)
    assert "(无描述)" in results[1].snippet
    request = urlopen.call_args.args[0]
    assert "per_page=5" in request.full_url and "q=" in request.full_url
