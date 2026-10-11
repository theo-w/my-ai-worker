"""Durable task mailbox and feedback protocol for JARVIS Digital Employees.

Workers poll for assignments, acknowledge work, and report completion/blockers.
The twin owns task state, leases, retry policy, and the auditable event stream.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
import json
import uuid


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


class WorkforceRegistry:
    def __init__(self, path: str = "data/workforce.json",
                 lease_seconds: int = 300, max_attempts: int = 3):
        self.path = Path(path)
        self.lease_seconds = max(10, int(lease_seconds))
        self.max_attempts = max(1, int(max_attempts))
        self.lock = RLock()
        self.tasks: dict[str, dict] = {}
        self.events: list[dict] = []
        self.load()

    def _event(self, event_type: str, **details):
        self.events.append({"type": event_type, "at": _stamp(), **details})
        self.events = self.events[-2000:]

    def load(self):
        with self.lock:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.tasks = data.get("tasks", {})
                self.events = data.get("events", [])
            except FileNotFoundError:
                return
            except (OSError, ValueError, TypeError):
                self.tasks, self.events = {}, []
                self._event("state_recovered", reason="invalid_or_unreadable_store")

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps({"tasks": self.tasks, "events": self.events},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def create_task(self, title: str, description: str = "", capability: str = "general",
                    priority: int = 3, assigned_to: str | None = None,
                    approval_required: bool = False) -> dict:
        title = title.strip()
        if not title or len(title) > 200:
            raise ValueError("title must be between 1 and 200 characters")
        if len(description) > 5000:
            raise ValueError("description must be at most 5000 characters")
        if not capability.strip() or len(capability) > 100:
            raise ValueError("capability must be between 1 and 100 characters")
        priority = max(1, min(int(priority), 5))
        with self.lock:
            task_id = uuid.uuid4().hex[:12]
            task = {
                "id": task_id, "title": title, "description": description,
                "capability": capability.strip(), "priority": priority,
                "status": "approval_required" if approval_required else "queued",
                "assigned_to": assigned_to, "attempts": 0,
                "max_attempts": self.max_attempts, "created_at": _stamp(),
                "updated_at": _stamp(), "lease_until": None, "output": "",
                "blocker": "", "feedback": [], "history": [],
            }
            self.tasks[task_id] = task
            self._event("task_created", task_id=task_id, title=title,
                        assigned_to=assigned_to, approval_required=approval_required)
            self.save()
            return dict(task)

    def approve_task(self, task_id: str) -> dict:
        with self.lock:
            task = self._get(task_id)
            if task["status"] != "approval_required":
                raise ValueError("task is not awaiting approval")
            task["status"] = "queued"
            task["updated_at"] = _stamp()
            self._event("task_approved", task_id=task_id)
            self.save()
            return dict(task)

    def claim(self, worker_id: str, capabilities: list[str] | None = None) -> dict | None:
        worker_id = worker_id.strip()
        if not worker_id or len(worker_id) > 120:
            raise ValueError("worker_id must be between 1 and 120 characters")
        caps = {c.strip() for c in (capabilities or []) if isinstance(c, str) and c.strip()}
        with self.lock:
            self.maintain(save=False)
            eligible = [t for t in self.tasks.values()
                        if t["status"] == "queued"
                        and (not t.get("assigned_to") or t["assigned_to"] == worker_id)
                        and (not caps or t["capability"] in caps or "general" in caps)]
            if not eligible:
                self.save()
                return None
            task = sorted(eligible, key=lambda t: (-t["priority"], t["created_at"]))[0]
            task["status"] = "assigned"
            task["assigned_to"] = worker_id
            task["attempts"] += 1
            task["lease_until"] = _stamp(_now() + timedelta(seconds=self.lease_seconds))
            task["updated_at"] = _stamp()
            task["history"].append({"event": "assigned", "worker_id": worker_id,
                                    "at": _stamp(), "attempt": task["attempts"]})
            self._event("task_assigned", task_id=task["id"], worker_id=worker_id,
                        attempt=task["attempts"])
            self.save()
            return dict(task)

    def report(self, task_id: str, worker_id: str, status: str,
               output: str = "", blocker: str = "") -> dict:
        if status not in {"completed", "blocked", "failed", "in_progress"}:
            raise ValueError("status must be completed, blocked, failed, or in_progress")
        if len(output) > 20000 or len(blocker) > 3000:
            raise ValueError("output or blocker is too long")
        with self.lock:
            task = self._get(task_id)
            if task["status"] != "assigned" or task.get("assigned_to") != worker_id:
                raise ValueError("task is not leased to this worker")
            task["output"] = output
            task["blocker"] = blocker
            task["updated_at"] = _stamp()
            if status == "in_progress":
                task["lease_until"] = _stamp(_now() + timedelta(seconds=self.lease_seconds))
                task["status"] = "assigned"
            elif status == "blocked":
                task["status"] = "queued" if task["attempts"] < task["max_attempts"] else "blocked"
                task["lease_until"] = None
                if task["status"] == "queued":
                    task["assigned_to"] = None
            else:
                task["status"] = status
                task["lease_until"] = None
            task["history"].append({"event": "worker_report", "worker_id": worker_id,
                                    "status": status, "at": _stamp(),
                                    "blocker": blocker})
            self._event("worker_reported", task_id=task_id, worker_id=worker_id,
                        status=status, blocker=blocker)
            self.save()
            return dict(task)

    def feedback(self, task_id: str, actor: str, message: str,
                 kind: str = "note") -> dict:
        if not actor.strip() or len(actor) > 120 or not message.strip() or len(message) > 5000:
            raise ValueError("actor and message are required and must be within limits")
        if kind not in {"note", "question", "correction", "approval_request"}:
            raise ValueError("unsupported feedback kind")
        with self.lock:
            task = self._get(task_id)
            item = {"actor": actor, "message": message.strip(), "kind": kind, "at": _stamp()}
            task["feedback"].append(item)
            task["updated_at"] = _stamp()
            self._event("feedback_received", task_id=task_id, actor=actor, kind=kind)
            self.save()
            return dict(item)

    def maintain(self, save: bool = True) -> dict:
        """Reclaim expired worker leases and make bounded retries available."""
        now = _now()
        requeued, failed = [], []
        with self.lock:
            for task in self.tasks.values():
                if task["status"] != "assigned" or not task.get("lease_until"):
                    continue
                try:
                    expired = datetime.fromisoformat(task["lease_until"]) <= now
                except (TypeError, ValueError):
                    expired = True
                if not expired:
                    continue
                task["lease_until"] = None
                task["updated_at"] = _stamp()
                task["history"].append({"event": "lease_expired", "at": _stamp()})
                if task["attempts"] < task["max_attempts"]:
                    task["status"] = "queued"
                    task["assigned_to"] = None
                    requeued.append(task["id"])
                    self._event("task_requeued_after_lease_expiry", task_id=task["id"])
                else:
                    task["status"] = "failed"
                    failed.append(task["id"])
                    self._event("task_failed_after_retries", task_id=task["id"])
            if save:
                self.save()
        return {"requeued": requeued, "failed": failed}

    def snapshot(self) -> dict:
        with self.lock:
            self.maintain(save=False)
            counts = {}
            for task in self.tasks.values():
                counts[task["status"]] = counts.get(task["status"], 0) + 1
            self.save()
            return {"counts": counts, "tasks": list(self.tasks.values()),
                    "events": self.events[-100:], "lease_seconds": self.lease_seconds}

    def _get(self, task_id: str) -> dict:
        task = self.tasks.get(task_id)
        if task is None:
            raise ValueError("unknown task_id")
        return task
