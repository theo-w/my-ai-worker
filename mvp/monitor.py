"""Read-only workforce observability for the Digital Twin and employees.

Use the authenticated admin API to inspect current task state, inputs, outputs,
event history and operational alerts. This module never logs bearer tokens.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ACTIVE = {"queued", "assigned", "approval_required"}
TERMINAL = {"completed", "blocked", "failed", "superseded"}


def build_monitor_report(snapshot: dict, now: datetime | None = None,
                         heartbeat_timeout_seconds: int = 30) -> dict:
    """Build a safe status view from a workforce snapshot without changing it."""
    now = now or datetime.now(timezone.utc)
    tasks = snapshot.get("tasks", [])
    if isinstance(tasks, dict):
        tasks = list(tasks.values())
    counts: dict[str, int] = {}
    alerts = []
    rows = []
    for task in tasks:
        status = str(task.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
        updated_at = task.get("updated_at")
        age_seconds = None
        try:
            age_seconds = max(0, int((now - datetime.fromisoformat(updated_at)).total_seconds()))
        except (TypeError, ValueError):
            pass
        lease_expired = False
        try:
            lease_expired = bool(task.get("lease_until")) and datetime.fromisoformat(task["lease_until"]) <= now
        except (TypeError, ValueError):
            lease_expired = True
        if status == "assigned" and lease_expired:
            alerts.append({"severity": "warning", "type": "lease_expired",
                           "task_id": task.get("id"), "message": "员工任务租约已过期，等待监督器回收。"})
        if status in ("blocked", "failed"):
            alerts.append({"severity": "warning", "type": status,
                           "task_id": task.get("id"),
                           "message": str(task.get("blocker") or "任务未成功完成")[:500]})
        if status in ACTIVE and age_seconds is not None and age_seconds > 900:
            alerts.append({"severity": "warning", "type": "stale_task",
                           "task_id": task.get("id"), "message": "任务超过 15 分钟没有更新。"})
        raw_output = task.get("output", "")
        provenance = "unknown"
        output = raw_output
        if isinstance(raw_output, str) and raw_output:
            try:
                envelope = json.loads(raw_output)
                if isinstance(envelope, dict) and "content" in envelope:
                    output = envelope.get("content", "")
                    provenance = "simulated" if envelope.get("simulated") is True else "executor_reported_live"
            except (ValueError, TypeError):
                pass
        rows.append({
            "task_id": task.get("id"),
            "title": task.get("title"),
            "capability": task.get("capability"),
            "status": status,
            "assigned_to": task.get("assigned_to"),
            "attempts": task.get("attempts", 0),
            "max_attempts": task.get("max_attempts"),
            "input": {"description": task.get("description", "")},
            "output": output,
            "provenance": provenance,
            "blocker": task.get("blocker", ""),
            "updated_at": updated_at,
            "age_seconds": age_seconds,
            "lease_until": task.get("lease_until"),
            "feedback": task.get("feedback", []),
            "history": task.get("history", []),
        })
    active_count = sum(counts.get(key, 0) for key in ACTIVE)
    blocked_count = counts.get("blocked", 0) + counts.get("failed", 0)
    # An active queue can still require attention if any task is blocked/failed.
    if blocked_count:
        twin_status = "needs_attention"
    elif active_count:
        twin_status = "in_progress"
    elif counts.get("completed", 0):
        twin_status = "completed"
    else:
        twin_status = "idle"
    raw_workers = snapshot.get("workers", [])
    if isinstance(raw_workers, dict):
        raw_workers = list(raw_workers.values())
    workers = []
    for worker in raw_workers:
        last = worker.get("last_heartbeat_at")
        age = None
        try:
            age = max(0, int((now - datetime.fromisoformat(last)).total_seconds()))
        except (TypeError, ValueError):
            pass
        online = age is not None and age <= heartbeat_timeout_seconds
        item = {
            "worker_id": worker.get("worker_id"),
            "status": worker.get("status", "unknown"),
            "online": online,
            "availability": "online" if online else ("suspected_offline" if age is not None else "heartbeat_missing"),
            "last_heartbeat_at": last,
            "heartbeat_age_seconds": age,
            "current_task_id": worker.get("current_task_id"),
            "progress": worker.get("progress", ""),
            "last_error": worker.get("last_error", ""),
            "capabilities": worker.get("capabilities", []),
        }
        workers.append(item)
        if age is None:
            alerts.append({"severity": "warning", "type": "worker_heartbeat_missing",
                           "worker_id": worker.get("worker_id"),
                           "message": "Worker is registered but has not sent a readable heartbeat."})
        elif age > heartbeat_timeout_seconds:
            alerts.append({"severity": "warning", "type": "worker_suspected_offline",
                           "worker_id": worker.get("worker_id"),
                           "message": f"Worker heartbeat is {age}s old; process may be unavailable."})
    events = snapshot.get("events", [])
    employee_ids = ({w.get("worker_id") for w in workers} |
                    {t.get("assigned_to") for t in rows if t.get("assigned_to")})
    worker_by_id = {w["worker_id"]: w for w in workers if w.get("worker_id")}
    employees = []
    for worker_id in sorted(x for x in employee_ids if x):
        active_ids = [t["task_id"] for t in rows
                      if t["assigned_to"] == worker_id and t["status"] == "assigned"]
        worker = worker_by_id.get(worker_id, {})
        heartbeat_status = worker.get("status")
        # An assignment does not prove the worker process is alive.
        if heartbeat_status:
            observed_status = heartbeat_status
        elif active_ids:
            observed_status = "working_unconfirmed"
        else:
            observed_status = "unknown"
        employees.append({
            "worker_id": worker_id,
            "status": observed_status,
            "online": worker.get("online"),
            "availability": worker.get("availability", "unknown"),
            "last_heartbeat_at": worker.get("last_heartbeat_at"),
            "heartbeat_age_seconds": worker.get("heartbeat_age_seconds"),
            "active_task_ids": active_ids,
            "active_task_count": len(active_ids),
            "assignment_consistent": (
                bool(active_ids) == (heartbeat_status == "working")
                if heartbeat_status is not None else None
            ),
            "progress": worker.get("progress", ""),
            "last_error": worker.get("last_error", ""),
        })
    return {
        "observed_at": now.isoformat(),
        "twin": {
            "status": twin_status,
            "total_tasks": len(rows),
            "active_tasks": active_count,
            "completed_tasks": counts.get("completed", 0),
            "blocked_or_failed_tasks": blocked_count,
            "counts_by_status": counts,
        },
        "employees": employees,
        "workers": workers,
        "tasks": rows,
        "alerts": alerts,
        "recent_events": events[-100:],
        "event_count": len(events),
        "evidence_policy": "executor_reported_live is not independent verification; check source metadata and provenance.",
    }


def fetch_snapshot(base_url: str, admin_token: str, timeout: float = 8.0) -> dict:
    request = Request(
        base_url.rstrip("/") + "/api/workforce",
        headers={"Authorization": "Bearer " + admin_token, "Accept": "application/json"},
        method="GET",
    )
    try:
        response = urlopen(request, timeout=timeout)
    except HTTPError as exc:
        raise RuntimeError("Workforce API returned HTTP " + str(exc.code)) from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("Workforce API unavailable: " + str(exc)) from exc
    with response:
        try:
            data = json.loads(response.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise RuntimeError("Workforce API returned invalid JSON") from exc
    if not isinstance(data, dict) or data.get("ok") is not True:
        raise RuntimeError("Workforce API response was not successful")
    return data


def main():
    parser = argparse.ArgumentParser(description="Monitor JARVIS Digital Twin and employee state.")
    parser.add_argument("--once", action="store_true", help="print one status snapshot and exit")
    parser.add_argument("--interval", type=float, default=5.0, help="poll interval in seconds")
    args = parser.parse_args()
    base_url = os.getenv("JARVIS_WORKFORCE_URL", "").strip()
    token = os.getenv("JARVIS_ADMIN_TOKEN", "").strip()
    if not base_url or not token:
        parser.error("Set JARVIS_WORKFORCE_URL and JARVIS_ADMIN_TOKEN.")
    while True:
        try:
            report = build_monitor_report(fetch_snapshot(base_url, token))
            print(json.dumps(report, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(json.dumps({"status": "monitor_error", "error": type(exc).__name__ + ": " + str(exc)},
                             ensure_ascii=False), flush=True)
        if args.once:
            break
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    main()
