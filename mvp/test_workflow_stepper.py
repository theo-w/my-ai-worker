from pathlib import Path


DASHBOARD = Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")


def test_business_journey_shows_real_research_design_and_feasibility_stages():
    for label in ("真实调研", "玩法假设", "可行性验收", "决策 / 原型"):
        assert label in DASHBOARD


def test_business_journey_maps_all_runtime_phases_instead_of_skipping_research():
    assert "planning:1,team:2,research:3,design:4,evaluation:5,decision:6,prototype:7" in DASHBOARD


def test_business_journey_surfaces_blocked_stages():
    assert 'cls="blocked"' in DASHBOARD
    assert 'researchState.status' in DASHBOARD
    assert 'feasibilityState.status==="incomplete"' in DASHBOARD
    assert 'decisionState.recommendation==="HOLD_FOR_EVIDENCE"' in DASHBOARD
