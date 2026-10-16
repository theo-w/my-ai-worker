from mvp.run import WORKERS
from mvp.twin import DigitalTwin


def test_digital_twin_forms_task_specific_team():
    twin = DigitalTwin()
    team = twin.form_team("评估 AI 原生 RPG", WORKERS)
    assert len(team) == 4
    assert team[0][0] == "Game Market Researcher"


def test_digital_twin_snapshot_contains_policy_and_intent():
    twin = DigitalTwin()
    snapshot = twin.snapshot("AI RPG", WORKERS)
    assert snapshot["name"] == "AI CEO / Digital Twin"
    assert snapshot["intent"] == "AI RPG"
    assert snapshot["policy"]["decision_style"] == "evidence_first"
