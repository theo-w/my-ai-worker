# 测试 App Store RSS 适配器:解析真实评价、拒绝不可访问源
import json
from unittest.mock import patch

from mvp.research import AppStoreRssSearchProvider, build_search_provider


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return json.dumps(self.payload).encode("utf-8")


def test_appstore_parses_real_reviews():
    payload = {"feed": {"entry": [
        {"id": {"label": "10"}, "title": {"label": "Loved it"},
         "content": {"label": "Memory feels broken after updates."},
         "rating": {"label": "2"}},
        {"id": {"label": "11"}, "title": {"label": "Meh"},
         "content": {"label": "NPC forgets everything."},
         "rating": {"label": "3"}},
    ]}}
    with patch("urllib.request.urlopen", return_value=FakeResponse(payload)):
        provider = AppStoreRssSearchProvider(
            "https://itunes.apple.com/us/rss/customerreviews/id=402176548/sortby=mostrecent/json")
        found = provider.search("npc memory", 5)
    assert [s.provider for s in found] == ["app_store_rss", "app_store_rss"]
    assert found[0].url == "10" and found[0].snippet.startswith("Memory")


def test_unreachable_sources_rejected():
    for url in ("https://www.reddit.com/r/x/top.json",
                "https://store.steampowered.com/appreviews/1?json=1"):
        try:
            build_search_provider(url)
        except ValueError as exc:
            assert "不可访问" in str(exc)
        else:
            raise AssertionError("应拒绝: " + url)
