import threading

import pytest

from mvp.supervisor import run_supervision_loop


class FakeTwin:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def supervise_once(self, recovery_policy=None):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return {"cycle_data": outcome, "policy_received": recovery_policy is not None}


def test_supervision_loop_runs_bounded_cycles_and_reports_each_cycle():
    twin = FakeTwin([1, 2, 3])
    seen = []
    result = run_supervision_loop(twin, interval_seconds=0.1, max_iterations=3,
                                  on_cycle=seen.append)
    assert result["status"] == "completed"
    assert result["cycle_count"] == 3
    assert [cycle["status"] for cycle in result["cycles"]] == ["ok"] * 3
    assert [cycle["cycle"] for cycle in seen] == [1, 2, 3]


def test_supervision_loop_records_error_and_continues():
    twin = FakeTwin([RuntimeError("temporary outage"), "recovered"])
    result = run_supervision_loop(twin, interval_seconds=0.1, max_iterations=2)
    assert [cycle["status"] for cycle in result["cycles"]] == ["error", "ok"]
    assert result["cycles"][0]["error_type"] == "RuntimeError"
    assert result["cycles"][1]["result"]["cycle_data"] == "recovered"


def test_supervision_loop_can_stop_between_cycles():
    stop = threading.Event()
    twin = FakeTwin([1, 2, 3])
    result = run_supervision_loop(
        twin, interval_seconds=1, stop_event=stop,
        on_cycle=lambda cycle: stop.set(),
    )
    assert result["status"] == "stopped"
    assert result["cycle_count"] == 1


@pytest.mark.parametrize("interval", [0, -1, 3601])
def test_supervision_loop_rejects_unsafe_intervals(interval):
    with pytest.raises(ValueError):
        run_supervision_loop(FakeTwin([1]), interval_seconds=interval)


def test_supervision_loop_rejects_invalid_iteration_limit():
    with pytest.raises(ValueError):
        run_supervision_loop(FakeTwin([1]), max_iterations=0)

def test_supervisor_cli_uses_configured_api_and_stops_after_one_cycle(monkeypatch, capsys):
    import sys
    import mvp.twin

    class CliTwin:
        def __init__(self, base_url, admin_token):
            assert base_url == "http://127.0.0.1:8765"
            assert admin_token == "admin-token-for-supervisor-test"

        def supervise_once(self, recovery_policy=None):
            return {"maintenance": {"requeued": [], "failed": []}}

    monkeypatch.setenv("JARVIS_WORKFORCE_URL", "http://127.0.0.1:8765")
    monkeypatch.setenv("JARVIS_ADMIN_TOKEN", "admin-token-for-supervisor-test")
    monkeypatch.setattr(sys, "argv", ["mvp.supervisor", "--max-iterations", "1"])
    monkeypatch.setattr(mvp.twin, "DigitalTwinCoordinator", CliTwin)

    from mvp.supervisor import main
    assert main() == 0
    output = capsys.readouterr().out
    assert '"cycle_count": 1' in output
    assert '"supervisor_stopped"' in output

