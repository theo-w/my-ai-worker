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
    assert found[0].url == "https://apps.apple.com/us/app/id402176548"
    assert found[0].snippet.startswith("Memory")
    # 原始评价字段:质量门判定"直接用户需求信号"的依据
    assert found[0].raw_review_text.startswith("Memory") and found[0].review_id == "10"
    assert found[0].collection_method.startswith("App Store Customer Reviews RSS")


def test_sources_without_search_adapter_rejected():
    """主机可达不等于能当搜索源:Reddit 与 Steam 没有搜索适配器,应明确拒绝。"""
    for url in ("https://www.reddit.com/r/x/top.json",
                "https://store.steampowered.com/appreviews/1?json=1"):
        try:
            build_search_provider(url)
        except ValueError as exc:
            assert "没有可用的搜索适配器" in str(exc)
        else:
            raise AssertionError("应拒绝: " + url)


def test_appstore_review_passes_quality_gate():
    """真实评价结构应通过质量门并计为直接用户需求信号。"""
    from mvp.quality import evaluate_evidence, assess_user_demand_source

    source = {
        "title": "App Store 评价 · 2★",
        "url": "https://apps.apple.com/us/app/id402176548",
        "snippet": "Memory feels broken after updates.",
        "provider": "app_store_rss",
        "published_at": "2026-11-10T00:50:15-07:00",
        "raw_review_text": "Memory feels broken after updates.",
        "review_id": "10",
        "collection_method": "App Store Customer Reviews RSS(feed 级时间戳,近似)",
    }
    evidence = [{"worker": "Live Research Adapter", "finding": source["snippet"],
                 "confidence": 0.75, "simulated": False, "source": source}]
    quality = evaluate_evidence(evidence)
    assert quality["items"][0]["quality_accepted"] is True, str(quality["items"][0])
    demand = assess_user_demand_source(source)
    assert demand["user_demand_eligible"] is True, str(demand)
