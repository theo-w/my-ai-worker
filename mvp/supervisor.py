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


def main() -> int:
    """Run supervision against a separately running workforce API."""
    import argparse
    import json
    import os
    import sys

    parser = argparse.ArgumentParser(
        description="Continuously monitor and recover the JARVIS workforce queue."
    )
    parser.add_argument("--interval-seconds", type=float, default=10.0)
    parser.add_argument("--max-iterations", type=int, default=None,
                        help="Stop after this many cycles; omit to run until interrupted.")
    args = parser.parse_args()

    base_url = os.getenv("JARVIS_WORKFORCE_URL", "").strip()
    admin_token = os.getenv("JARVIS_ADMIN_TOKEN", "").strip()
    if not base_url or not admin_token:
        parser.error("Set JARVIS_WORKFORCE_URL and JARVIS_ADMIN_TOKEN.")
    try:
        try:
            from .twin import DigitalTwinCoordinator
        except ImportError:
            from twin import DigitalTwinCoordinator
        twin = DigitalTwinCoordinator(base_url, admin_token)
        result = run_supervision_loop(
            twin,
            interval_seconds=args.interval_seconds,
            max_iterations=args.max_iterations,
            on_cycle=lambda cycle: print(json.dumps(cycle, ensure_ascii=False), flush=True),
        )
        print(json.dumps({
            "event": "supervisor_stopped",
            "status": result["status"],
            "cycle_count": result["cycle_count"],
            "elapsed_seconds": result["elapsed_seconds"],
        }, ensure_ascii=False), flush=True)
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"event": "supervisor_interrupted"}, ensure_ascii=False), flush=True)
        return 130
    except Exception as exc:
        # Surface API/auth/configuration failures as one concise process error.
        print(
            "Supervisor stopped with an error (" + type(exc).__name__ + "): " + str(exc),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
