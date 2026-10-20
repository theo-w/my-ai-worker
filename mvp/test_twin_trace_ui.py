"""Regression tests for the Digital Twin controls in the trace dashboard."""
from pathlib import Path


TRACE = Path(__file__).with_name("trace.html").read_text(encoding="utf-8")


def test_trace_dashboard_exposes_goal_review_and_advance_controls():
    assert 'id="twinGoal"' in TRACE
    assert 'id="twinStrategy"' in TRACE
    assert 'id="twinProject"' in TRACE
    assert '"/api/twin/goal"' in TRACE
    assert '"/api/twin/review"' in TRACE
    assert '"/api/twin/advance"' in TRACE


def test_trace_dashboard_sends_admin_token_without_browser_storage():
    assert 'Authorization:"Bearer "+token' in TRACE
    assert "localStorage" not in TRACE
    assert "sessionStorage" not in TRACE


def test_trace_dashboard_explains_safety_boundaries():
    assert "未知阻塞会升级人工处理" in TRACE
    assert "不会自动修改任务" in TRACE
    assert "分身复核" in TRACE
