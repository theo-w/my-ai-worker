from pathlib import Path


DASHBOARD = Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")


def test_feasibility_summary_has_visual_dimension_and_gate_cards():
    for token in ("feasibility-visual", "fv-dimensions", "fv-blockers", "八维度检查"):
        assert token in DASHBOARD


def test_evaluated_verdicts_are_translated_for_fast_reading():
    for token in ("建议进入有限原型验证", "建议调整后再验证", "证据不足，暂不决策"):
        assert token in DASHBOARD


def test_visual_scores_are_only_rendered_with_evidence_and_rationale():
    assert "item.evidence_refs.length>0" in DASHBOARD
    assert "String(item.rationale||\"\").trim()" in DASHBOARD
