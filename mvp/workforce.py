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
        self.workers: dict[str, dict] = {}
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
                self.workers = data.get("workers", {})
            except FileNotFoundError:
                return
            except (OSError, ValueError, TypeError):
                self.tasks, self.events, self.workers = {}, [], {}
                self._event("state_recovered", reason="invalid_or_unreadable_store")

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps({"tasks": self.tasks, "events": self.events, "workers": self.workers},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def create_task(self, title: str, description: str = "", capability: str = "general",
                    priority: int = 3, assigned_to: str | None = None,
                    approval_required: bool = False, success_criteria: dict | None = None,
                    evidence_required: bool = False) -> dict:
        title = title.strip()
        if not title or len(title) > 200:
            raise ValueError("title must be between 1 and 200 characters")
        if len(description) > 5000:
            raise ValueError("description must be at most 5000 characters")
        if not capability.strip() or len(capability) > 100:
            raise ValueError("capability must be between 1 and 100 characters")
        priority = max(1, min(int(priority), 5))
        if success_criteria is None:
            success_criteria = {}
        if not isinstance(success_criteria, dict) or len(json.dumps(success_criteria)) > 4000:
            raise ValueError("success_criteria must be an object up to 4000 serialized characters")
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
                "success_criteria": success_criteria, "evidence_required": bool(evidence_required),
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

    def claim(self, worker_id: str, capabilities: list[str] | None = None, task_id: str | None = None) -> dict | None:
        worker_id = worker_id.strip()
        if not worker_id or len(worker_id) > 120:
            raise ValueError("worker_id must be between 1 and 120 characters")
        caps = {c.strip() for c in (capabilities or []) if isinstance(c, str) and c.strip()}
        with self.lock:
            self.maintain(save=False)
            eligible = [t for t in self.tasks.values()
                        if t["status"] == "queued"
                        and (task_id is None or t["id"] == task_id)
                        and (not t.get("assigned_to") or t["assigned_to"] == worker_id)
                        and (not caps or t["capability"] in caps or "general" in caps)]
            if not eligible:
                self.save()
                return None
            task = sorted(eligible, key=lambda t: (-t["priority"], t["created_at"]))[0]
            task["status"] = "assigned"
            task["assigned_to"] = worker_id
            task["attempts"] += 1
            # A fresh fencing token distinguishes this lease from every prior attempt,
            # including a retry claimed by the same worker identity.
            task["_lease_token"] = uuid.uuid4().hex
            task["lease_until"] = _stamp(_now() + timedelta(seconds=self.lease_seconds))
            task["updated_at"] = _stamp()
            task["history"].append({"event": "assigned", "worker_id": worker_id,
                                    "at": _stamp(), "attempt": task["attempts"]})
            self._event("task_assigned", task_id=task["id"], worker_id=worker_id,
                        attempt=task["attempts"])
            self.save()
            claimed = {key: value for key, value in task.items() if key != "_lease_token"}
            claimed["lease_token"] = task["_lease_token"]
            return claimed

    def report(self, task_id: str, worker_id: str, status: str,
               output: str = "", blocker: str = "", lease_token: str | None = None) -> dict:
        if status not in {"completed", "blocked", "failed", "in_progress"}:
            raise ValueError("status must be completed, blocked, failed, or in_progress")
        if len(output) > 20000 or len(blocker) > 3000:
            raise ValueError("output or blocker is too long")
        with self.lock:
            # A worker must not be able to submit a late result after its lease
            # expired merely because the background supervisor has not ticked yet.
            self.maintain(save=True)
            task = self._get(task_id)
            if task["status"] != "assigned" or task.get("assigned_to") != worker_id:
                raise ValueError("task is not leased to this worker")
            if not isinstance(lease_token, str) or not lease_token or lease_token != task.get("_lease_token"):
                raise ValueError("lease token is missing or stale")
            task["output"] = output
            task["blocker"] = blocker
            task["updated_at"] = _stamp()
            if status == "in_progress":
                task["lease_until"] = _stamp(_now() + timedelta(seconds=self.lease_seconds))
                task["status"] = "assigned"
            elif status == "blocked":
                # A blocked result is a planning decision, not an implicit retry.
                # The twin must inspect feedback and explicitly decide what happens next.
                task["_lease_token"] = None
                task["status"] = "blocked"
                task["lease_until"] = None
                task["assigned_to"] = None
            else:
                # Worker completion is a submitted candidate result, not acceptance.
                # The task stays non-terminal until the admin records validation.
                task["status"] = "awaiting_validation" if status == "completed" else status
                task["lease_until"] = None
                task["_lease_token"] = None
                task["assigned_to"] = None
            task["history"].append({"event": "worker_report", "worker_id": worker_id,
                                    "status": status, "at": _stamp(),
                                    "blocker": blocker})
            self._event("worker_reported", task_id=task_id, worker_id=worker_id,
                        status=status, blocker=blocker)
            self.save()
            return {key: value for key, value in task.items() if key != "_lease_token"}


    def renew_lease(self, task_id: str, worker_id: str,
                    lease_token: str | None) -> dict:
        """Renew an active, unexpired task lease only for its current token holder."""
        worker_id = worker_id.strip()
        # Do not allow a heartbeat to revive a lease after its deadline.
        self.maintain()
        with self.lock:
            task = self._get(task_id)
            if task["status"] != "assigned" or task.get("assigned_to") != worker_id:
                raise ValueError("task is not leased to this worker")
            if (not isinstance(lease_token, str) or not lease_token
                    or lease_token != task.get("_lease_token")):
                raise ValueError("lease token is missing or stale")
            task["lease_until"] = _stamp(_now() + timedelta(seconds=self.lease_seconds))
            task["updated_at"] = _stamp()
            task["history"].append({
                "event": "lease_renewed", "worker_id": worker_id,
                "at": _stamp(), "attempt": task["attempts"],
            })
            self._event("task_lease_renewed", task_id=task_id, worker_id=worker_id,
                        attempt=task["attempts"])
            self.save()
            return {key: value for key, value in task.items() if key != "_lease_token"}


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
                task["_lease_token"] = None
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


    def record_verification(self, task_id: str, verification: dict) -> dict:
        """Persist a structural verification record without claiming factual truth."""
        if not isinstance(verification, dict) or len(json.dumps(verification)) > 8000:
            raise ValueError("verification must be an object up to 8000 serialized characters")
        if "accepted" not in verification or not isinstance(verification.get("accepted"), bool):
            raise ValueError("verification.accepted must be a boolean")
        safe = dict(verification)
        # Structural acceptance is not proof that the output is factually true.
        safe["verified_truth"] = False
        with self.lock:
            task = self._get(task_id)
            if task["status"] != "awaiting_validation":
                raise ValueError("task must be awaiting_validation before verification")
            task["verification"] = safe
            task["verified_truth"] = False
            task["status"] = "completed" if safe["accepted"] else "blocked"
            if not safe["accepted"]:
                task["blocker"] = str(safe.get("notes") or "Validation rejected the submitted result")[:3000]
            else:
                task["blocker"] = ""
            task["updated_at"] = _stamp()
            task["history"].append({
                "event": "verification_recorded",
                "accepted": safe["accepted"],
                "verified_truth": False,
                "at": _stamp(),
            })
            self._event("verification_recorded", task_id=task_id,
                        accepted=safe["accepted"], verified_truth=False)
            self.save()
            return {key: value for key, value in task.items() if key != "_lease_token"}

    def retry_task(self, task_id: str, reason: str) -> dict:
        """Explicitly requeue blocked/failed work after twin triage, within retry limits."""
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise ValueError("reason must be between 1 and 1000 characters")
        with self.lock:
            task = self._get(task_id)
            if task["status"] not in {"blocked", "failed"}:
                raise ValueError("only blocked or failed tasks can be retried")
            if task["attempts"] >= task["max_attempts"]:
                raise ValueError("task retry limit reached")
            prior_status = task["status"]
            task["status"] = "queued"
            task["assigned_to"] = None
            task["lease_until"] = None
            task["_lease_token"] = None
            task["blocker"] = ""
            task["updated_at"] = _stamp()
            task["history"].append({
                "event": "retry_approved", "reason": reason.strip(),
                "previous_status": prior_status, "at": _stamp(),
            })
            self._event("task_retry_approved", task_id=task_id, reason=reason.strip(),
                        previous_status=prior_status, attempts=task["attempts"])
            self.save()
            return {key: value for key, value in task.items() if key != "_lease_token"}

    def cancel_task(self, task_id: str, reason: str) -> dict:
        """Cancel queued/assigned work; preserve an audit trail and reject late reports."""
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise ValueError("reason must be between 1 and 1000 characters")
        with self.lock:
            task = self._get(task_id)
            if task["status"] not in {"queued", "assigned", "approval_required"}:
                raise ValueError("only queued, assigned, or approval-required tasks can be cancelled")
            prior_status = task["status"]
            task["status"] = "cancelled"
            task["lease_until"] = None
            task["_lease_token"] = None
            task["blocker"] = reason.strip()
            task["updated_at"] = _stamp()
            task["history"].append({"event": "cancelled", "reason": reason.strip(),
                                    "previous_status": prior_status, "at": _stamp()})
            self._event("task_cancelled", task_id=task_id, reason=reason.strip(),
                        previous_status=prior_status)
            self.save()
            return {key: value for key, value in task.items() if key != "_lease_token"}

    def merge_tasks(self, target_task_id: str, source_task_ids: list[str],
                    reason: str) -> dict:
        """Supersede queued duplicate tasks into one target without losing history."""
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise ValueError("reason must be between 1 and 1000 characters")
        if not isinstance(source_task_ids, list) or len(source_task_ids) > 20:
            raise ValueError("source_task_ids must be a list of at most 20 task IDs")
        if target_task_id in source_task_ids or len(set(source_task_ids)) != len(source_task_ids):
            raise ValueError("target and source task IDs must be distinct")
        with self.lock:
            target = self._get(target_task_id)
            if target["status"] not in {"queued", "approval_required"}:
                raise ValueError("target task must not have started")
            sources = [self._get(task_id) for task_id in source_task_ids]
            if any(task["status"] not in {"queued", "approval_required"} for task in sources):
                raise ValueError("source tasks must not have started")
            if any(task["capability"] != target["capability"] for task in sources):
                raise ValueError("only tasks with matching capabilities can be merged")
            descriptions = [target.get("description", "").strip()]
            descriptions.extend(
                f"[Merged from {task['id']}] {task.get('title', '')}: {task.get('description', '').strip()}"
                for task in sources
            )
            target["description"] = "\n\n".join(part for part in descriptions if part)[:5000]
            target["priority"] = max([target["priority"]] + [task["priority"] for task in sources])
            target["history"].append({"event": "tasks_merged", "source_task_ids": source_task_ids,
                                      "reason": reason.strip(), "at": _stamp()})
            target["updated_at"] = _stamp()
            for task in sources:
                task["status"] = "superseded"
                task["lease_until"] = None
                task["_lease_token"] = None
                task["blocker"] = "Merged into " + target_task_id
                task["updated_at"] = _stamp()
                task["history"].append({"event": "superseded_by_merge", "target_task_id": target_task_id,
                                        "reason": reason.strip(), "at": _stamp()})
            self._event("tasks_merged", target_task_id=target_task_id,
                        source_task_ids=source_task_ids, reason=reason.strip())
            self.save()
            public = lambda task: {key: value for key, value in task.items() if key != "_lease_token"}
            return {"target": public(target), "sources": [public(task) for task in sources]}

    def heartbeat_worker(self, worker_id: str, status: str = "idle",
                         current_task_id: str | None = None, progress: str = "",
                         last_error: str = "") -> dict:
        """Persist a bounded, token-free heartbeat for an authenticated worker."""
        worker_id = worker_id.strip()
        if not worker_id or len(worker_id) > 120:
            raise ValueError("worker_id must be between 1 and 120 characters")
        if status not in {"idle", "working", "waiting_tool", "blocked"}:
            raise ValueError("unsupported worker status")
        if len(progress) > 500 or len(last_error) > 1000:
            raise ValueError("progress or last_error is too long")
        with self.lock:
            prior = self.workers.get(worker_id, {})
            worker = {
                "worker_id": worker_id,
                "status": status,
                "current_task_id": current_task_id,
                "progress": progress.strip(),
                "last_error": last_error.strip(),
                "last_heartbeat_at": _stamp(),
                "capabilities": prior.get("capabilities", []),
            }
            self.workers[worker_id] = worker
            self._event("worker_heartbeat", worker_id=worker_id, status=status,
                        current_task_id=current_task_id)
            self.save()
            return dict(worker)


    def snapshot(self) -> dict:
        with self.lock:
            self.maintain(save=False)
            counts = {}
            for task in self.tasks.values():
                counts[task["status"]] = counts.get(task["status"], 0) + 1
            self.save()
            safe_tasks = [
                {key: value for key, value in task.items() if key != "_lease_token"}
                for task in self.tasks.values()
            ]
            return {"counts": counts, "tasks": safe_tasks,
                    "events": self.events[-100:], "workers": list(self.workers.values()), "lease_seconds": self.lease_seconds}

    def _get(self, task_id: str) -> dict:
        task = self.tasks.get(task_id)
        if task is None:
            raise ValueError("unknown task_id")
        return task
