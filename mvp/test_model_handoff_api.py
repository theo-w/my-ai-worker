"""HTTP-level smoke tests for the manual model handoff endpoint."""
from __future__ import annotations

import json
from threading import Thread
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import pytest

from mvp.server import Handler


@pytest.fixture(scope="module")
def api_base_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def post_json(base_url: str, path: str, payload: dict) -> tuple[int, dict]:
    request = Request(
        base_url + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=3) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def hidden_gap_reply() -> dict:
    return {
        "intent": "用弯鱼钩穿过墙脚破洞拨动内侧门闩",
        "action_kind": "hidden_gap",
        "entities": ["hole", "hook", "latch"],
        "reasoning": "弯钩可以穿过检修孔勾住内侧插销",
        "uncertainties": ["鱼钩是否足够坚固"],
        "counterexample": "洞口可能被堵住，或鱼钩无法触及门闩",
    }


def test_model_handoff_endpoint_accepts_rule_validated_hidden_gap(api_base_url):
    status, result = post_json(api_base_url, "/api/model-handoff", {
        "action": "清理墙脚被堵住的破洞，把弯曲鱼钩伸进去勾住门内侧的插销并拉开",
        "state": {"inspected": ["hole", "hook"], "talked": [], "selected": ["hole", "hook"]},
        "model_reply": json.dumps(hidden_gap_reply(), ensure_ascii=False),
    })

    assert status == 200
    assert result["ok"] is True
    assert result["validation"]["ok"] is True
    assert result["validation"]["type"] == "隐藏环境解法"
    assert result["trust"]["model_output_is_authoritative"] is False


def test_model_handoff_endpoint_fails_closed_when_inspection_is_missing(api_base_url):
    status, result = post_json(api_base_url, "/api/model-handoff", {
        "action": "清理墙脚被堵住的破洞，把弯曲鱼钩伸进去勾住门内侧的插销并拉开",
        "state": {"inspected": [], "talked": [], "selected": []},
        "model_reply": json.dumps(hidden_gap_reply(), ensure_ascii=False),
    })

    assert status == 200
    assert result["ok"] is True
    assert result["validation"]["ok"] is False
    assert result["validation"]["world_state"]["warehouse_open"] is False
    assert result["validation"]["state_changes"] == []
