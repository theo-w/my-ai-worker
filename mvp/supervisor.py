"""Bounded continuous supervision loop for the JARVIS workforce.

The loop is deliberately separate from the monitor: monitor builds facts,
DigitalTwinCoordinator decides recovery, and this module schedules repeated
supervision cycles. It does not start automatically on import.
"""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Event
from time import monotonic
from typing import Callable


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_supervision_loop(
    twin,
    interval_seconds: float = 10.0,
    max_iterations: int | None = None,
    stop_event: Event | None = None,
    recovery_policy=None,
    on_cycle: Callable[[dict], None] | None = None,
) -> dict:
    """Run periodic supervision until stopped or the optional iteration cap.

    Per-cycle errors are surfaced as result records and do not silently kill
    the loop. Callback failures are isolated from supervision itself.
    """
    interval = float(interval_seconds)
    if interval < 0.1 or interval > 3600:
        raise ValueError("interval_seconds must be between 0.1 and 3600")
    if max_iterations is not None and (
        not isinstance(max_iterations, int) or isinstance(max_iterations, bool)
        or max_iterations < 1
    ):
        raise ValueError("max_iterations must be a positive integer or None")
    stop = stop_event or Event()
    cycles = []
    started = monotonic()
    while not stop.is_set() and (max_iterations is None or len(cycles) < max_iterations):
        cycle_started = monotonic()
        try:
            result = twin.supervise_once(recovery_policy=recovery_policy)
            record = {
                "cycle": len(cycles) + 1,
                "status": "ok",
                "started_at": _utc_now(),
                "duration_seconds": round(monotonic() - cycle_started, 4),
                "result": result,
            }
        except Exception as exc:
            record = {
                "cycle": len(cycles) + 1,
                "status": "error",
                "started_at": _utc_now(),
                "duration_seconds": round(monotonic() - cycle_started, 4),
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
            }
        cycles.append(record)
        if on_cycle:
            try:
                on_cycle(record)
            except Exception:
                # Observability callbacks must not terminate task supervision.
                pass
        if max_iterations is not None and len(cycles) >= max_iterations:
            break
        remaining = max(0.0, interval - (monotonic() - cycle_started))
        if stop.wait(remaining):
            break
    return {
        "status": "stopped" if stop.is_set() else "completed",
        "cycles": cycles,
        "cycle_count": len(cycles),
        "elapsed_seconds": round(monotonic() - started, 4),
    }
