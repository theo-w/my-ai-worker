import json
from io import BytesIO
from urllib.request import Request

from mvp.research import JsonHttpSearchProvider


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({
            "results": [{
                "title": "Example source",
                "url": "https://example.com/article",
                "content": "A source-backed excerpt.",
                "published_date": "2026-10-01",
            }]
        }).encode("utf-8")


def test_tavily_uses_post_and_maps_native_response(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = JsonHttpSearchProvider(
        "https://api.tavily.com/search", api_key="test-secret", timeout=3
    )

    results = provider.search("AI-native games", limit=4)

    request = captured["request"]
    assert request.get_method() == "POST"
    assert request.full_url == "https://api.tavily.com/search"
    assert json.loads(request.data.decode("utf-8")) == {
        "api_key": "test-secret",
        "query": "AI-native games",
        "max_results": 4,
        "search_depth": "basic",
        "include_answer": False,
    }
    assert captured["timeout"] == 3
    assert len(results) == 1
    assert results[0].provider == "tavily"
    assert results[0].snippet == "A source-backed excerpt."
    assert results[0].published_at == "2026-10-01"


def test_tavily_requires_api_key():
    provider = JsonHttpSearchProvider("https://api.tavily.com/search")
    try:
        provider.search("test")
    except ValueError as exc:
        assert "JARVIS_SEARCH_API_KEY" in str(exc)
    else:
        raise AssertionError("Tavily must reject missing API keys")
