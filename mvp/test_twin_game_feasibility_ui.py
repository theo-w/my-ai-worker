"""Regression tests for the AI-native game feasibility template selector."""
from pathlib import Path


TRACE = Path(__file__).with_name("trace.html").read_text(encoding="utf-8")


def test_game_feasibility_template_is_selectable_and_sent_to_api():
    assert 'id="twinTemplate"' in TRACE
    assert 'value="ai_game_feasibility"' in TRACE
    assert 'template:$("twinTemplate").value' in TRACE
    assert "AI 原生游戏可行性评估" in TRACE
