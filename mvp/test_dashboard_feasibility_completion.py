from pathlib import Path


DASHBOARD = Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")


def test_admin_token_remember_is_enabled_by_default_without_hardcoding_a_token():
    assert 'id="rememberToken" type="checkbox" checked' in DASHBOARD
    assert 'localStorage.getItem("jarvis_admin_token")' in DASHBOARD
    assert 'value="replace-with-a-real-token"' not in DASHBOARD


def test_dashboard_surfaces_multi_angle_research_coverage():
    assert "coverage.requested_angles" in DASHBOARD
    assert "调研覆盖" in DASHBOARD
    assert "覆盖不完整" in DASHBOARD
    assert "LIVE SOURCE / SIMULATION LABELS" in DASHBOARD


def test_dashboard_shows_automatic_feasibility_completion_blockers():
    assert 'feasibility.status==="incomplete"' in DASHBOARD
    assert 'feasibility.completion.blockers' in DASHBOARD
    assert 'feasibilityReportEl.value=JSON.stringify(feasibility.report||{},null,2)' in DASHBOARD
    assert "未知成本不会被当作通过" in DASHBOARD
