#!/usr/bin/env python3
"""Minimal Digital Twin policy/runtime for the JARVIS showcase MVP."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from datetime import datetime, timezone
import json
from time import monotonic
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class TwinPolicy:
    autonomy_level: str = "managed"
    approval_required_for: list[str] | None = None
    max_parallel_workers: int = 4
    decision_style: str = "evidence_first"

    def __post_init__(self):
        if self.approval_required_for is None:
            self.approval_required_for = [
                "production_release", "budget_commitment", "external_publication",
                "destructive_operation", "legal_commitment",
            ]


@dataclass
class DigitalTwin:
    name: str = "AI CEO / Digital Twin"
    role: str = "Intent, priorities and final decision layer"
    objective: str = "Turn a business goal into an executable AI workforce"
    policy: TwinPolicy | None = None

    def __post_init__(self):
        if self.policy is None:
            self.policy = TwinPolicy()

    def form_team(self, goal: str, candidates: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Select a small task-specific team without hard-coding a single workflow."""
        goal_lower = goal.lower()
        selected = list(candidates)

        if any(k in goal_lower for k in ["game", "游戏", "rpg", "npc", "玩家"]):
            preferred = ["Game Market Researcher", "Player Researcher",
                         "AI Technology Strategist", "AI Game Designer"]
            selected = [x for x in candidates if x[0] in preferred]

        return selected[: self.policy.max_parallel_workers]

    def snapshot(self, goal: str, team: list[tuple[str, str]]) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "objective": self.objective,
            "intent": goal,
            "policy": asdict(self.policy),
            "team_size": len(team),
            "decision_style": self.policy.decision_style,
        }



class AutonomousProjectLoop:
    """Bounded project loop with explicit human-approval boundaries.

    This deterministic baseline orchestrates injected task executors; it does
    not claim to perform live research or use an LLM by itself.
    """
    DEFAULT_APPROVALS = {
        "production_release", "budget_commitment", "external_publication",
        "destructive_operation", "legal_commitment",
    }

    def __init__(self, max_iterations: int = 3,
                 approval_required_for: set[str] | None = None):
        self.max_iterations = max(1, max_iterations)
        self.approval_required_for = set(approval_required_for or self.DEFAULT_APPROVALS)

    @staticmethod
    def rank_options(options: list[dict]) -> list[dict]:
        """Rank options by an explicit score and retain the trade-offs."""
        return sorted(options, key=lambda item: float(item.get("score", 0)), reverse=True)

    def run(self, goal: str, tasks: list[dict], executor,
            options: list[dict] | None = None,
            requested_actions: list[str] | None = None,
            replanner=None) -> dict:
        """Run bounded task iterations; an optional replanner can replace failed tasks."""
        options = self.rank_options(options or [])
        gated = sorted(set(requested_actions or []) & self.approval_required_for)
        events = [{"type": "goal_accepted", "goal": goal},
                  {"type": "plan_created", "task_count": len(tasks)}]
        if gated:
            events.append({"type": "approval_required", "actions": gated})
            return {
                "goal": goal, "status": "needs_approval", "completed_tasks": 0,
                "total_tasks": len(tasks), "options": options,
                "recommendation": options[0]["name"] if options else None,
                "questions_for_human": [
                    "请审批后再继续：" + "、".join(gated)
                ], "events": events,
            }

        for iteration in range(1, self.max_iterations + 1):
            events.append({"type": "iteration_started", "iteration": iteration})
            pending = [task for task in tasks if task.get("status", "queued")
                       not in ("completed", "blocked", "superseded")]
            if not pending:
                break
            for task in pending:
                task["status"] = "running"
                try:
                    output = executor(task)
                    task["output"] = str(output or "")
                    task["status"] = "completed" if task["output"].strip() else "blocked"
                except Exception as exc:
                    task["status"] = "blocked"
                    task["output"] = "Execution failed: " + type(exc).__name__
                events.append({"type": "task_finished", "task_id": task.get("id"), "status": task["status"]})

            failed = [task for task in tasks if task.get("status") == "blocked"
                      and not task.get("replan_attempted")]
            if failed and replanner and iteration < self.max_iterations:
                try:
                    replacements = replanner(goal, failed, iteration) or []
                except Exception as exc:
                    replacements = []
                    events.append({"type": "replan_failed", "error": type(exc).__name__})
                if replacements:
                    for task in failed:
                        task["status"] = "superseded"
                        task["replan_attempted"] = True
                    tasks.extend(replacements)
                    events.append({
                        "type": "plan_revised", "iteration": iteration,
                        "superseded_task_ids": [task.get("id") for task in failed],
                        "replacement_task_ids": [task.get("id") for task in replacements],
                    })
                    continue

            if all(task.get("status") in ("completed", "blocked", "superseded") for task in tasks):
                break
            events.append({"type": "plan_re_evaluated", "iteration": iteration})

        active = [task for task in tasks if task.get("status") != "superseded"]
        completed = sum(task.get("status") == "completed" for task in active)
        blocked = sum(task.get("status") == "blocked" for task in active)
        status = "completed" if active and completed == len(active) else ("blocked" if completed else "failed")
        questions = []
        if blocked:
            questions.append("部分任务受阻；请补充缺失输入或批准调整后的计划。")
        if not active:
            status = "completed"
        events.append({"type": "checkpoint_created", "completed": completed, "blocked": blocked})
        return {
            "goal": goal, "status": status, "completed_tasks": completed,
            "total_tasks": len(active), "superseded_tasks": len(tasks) - len(active),
            "options": options, "recommendation": options[0]["name"] if options else None,
            "tasks": tasks,
            "questions_for_human": questions, "events": events,
        }



@dataclass
class PersistentTwinMemory:
    """Local JSON memory for explicit preferences, decisions and lessons."""
    path: str = "data/twin_memory.json"
    preferences: dict | None = None
    decisions: list[dict] | None = None
    lessons: list[dict] | None = None

    def __post_init__(self):
        self.preferences = self.preferences or {}
        self.decisions = self.decisions or []
        self.lessons = self.lessons or []
        self.load()

    def load(self):
        target = Path(self.path)
        if not target.exists():
            return
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            self.preferences = data.get("preferences", {})
            self.decisions = data.get("decisions", [])
            self.lessons = data.get("lessons", [])
        except (OSError, ValueError, TypeError):
            # Broken memory should never prevent a project from running.
            self.preferences, self.decisions, self.lessons = {}, [], []

    def save(self):
        target = Path(self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({
            "preferences": self.preferences,
            "decisions": self.decisions,
            "lessons": self.lessons,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def remember_preference(self, key: str, value):
        self.preferences[key] = value
        self.save()

    def record_decision(self, goal: str, recommendation: str, alternatives=None,
                        outcome: str = "pending"):
        item = {
            "goal": goal, "recommendation": recommendation,
            "alternatives": alternatives or [], "outcome": outcome,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self.decisions.append(item)
        self.save()
        return item

    def record_lesson(self, lesson: str, context: str = ""):
        item = {
            "lesson": lesson, "context": context,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self.lessons.append(item)
        self.save()
        return item
class DigitalTwinAPIError(RuntimeError):
    """A structured error returned by the authenticated workforce API."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class DigitalTwinCoordinator:
    """Authenticated Digital Twin controller for goal planning and supervision.

    The coordinator creates capability-tagged work items, reads workforce
    state, and summarizes verified workflow status. It does not claim that
    queued work has been executed or that model-generated output is evidence.
    """

    def __init__(self, base_url: str, admin_token: str, timeout: float = 8.0,
                 max_tasks: int = 8):
        from urllib.parse import urlparse

        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("base_url must be an HTTP(S) URL")
        if not isinstance(admin_token, str) or len(admin_token) < 24:
            raise ValueError("admin token must be at least 24 characters")
        self.base_url = base_url.rstrip("/")
        self.admin_token = admin_token
        self.timeout = max(1.0, float(timeout))
        self.max_tasks = max(1, min(int(max_tasks), 20))

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        data = None if payload is None else json.dumps(
            payload, ensure_ascii=False
        ).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=data,
            headers={
                "Authorization": "Bearer " + self.admin_token,
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            response = urlopen(request, timeout=self.timeout)
        except HTTPError as exc:
            try:
                message = json.loads(exc.read().decode("utf-8")).get("error", "API request failed")
            except (ValueError, AttributeError):
                message = "API request failed"
            raise DigitalTwinAPIError(exc.code, str(message)) from exc
        except (URLError, TimeoutError) as exc:
            raise DigitalTwinAPIError(503, "Workforce API unavailable: " + str(exc)) from exc
        with response:
            try:
                result = json.loads(response.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise DigitalTwinAPIError(502, "Workforce API returned invalid JSON") from exc
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise DigitalTwinAPIError(response.status, str(result.get("error", "API request failed")))
        return result

    @staticmethod
    def default_plan(goal: str) -> list[dict]:
        """Create a small, reusable first-pass plan from a natural-language goal."""
        if not isinstance(goal, str) or not goal.strip():
            raise ValueError("goal must be a non-empty string")
        normalized = goal.casefold()
        if any(word in normalized for word in ("game", "游戏", "rpg", "npc", "玩家", "ai-native")):
            return [
                {"title": "研究目标用户与市场需求", "capability": "research", "priority": 5,
                 "description": "寻找可追溯的市场、玩家需求与竞品资料；标注来源和不确定性。"},
                {"title": "分析玩家痛点与差异化机会", "capability": "research", "priority": 4,
                 "description": "分析玩家问题、现有替代方案与潜在差异化，不把假设当事实。"},
                {"title": "评估 AI 技术可行性与成本风险", "capability": "analysis", "priority": 4,
                 "description": "拆解关键 AI 能力、延迟、成本、安全与技术验证风险。"},
                {"title": "评估商业模式与验证路线", "capability": "analysis", "priority": 3,
                 "description": "比较变现假设、最小可行实验、成功指标与停止条件。"},
            ]
        return [
            {"title": "收集与目标相关的可靠信息", "capability": "research", "priority": 5,
             "description": "收集可追溯资料，标注来源、日期和不确定性。"},
            {"title": "分析可行方案、成本与主要风险", "capability": "analysis", "priority": 4,
             "description": "比较方案、约束、风险与可验证假设。"},
            {"title": "形成建议与下一步验证计划", "capability": "analysis", "priority": 3,
             "description": "基于已回传结果整理建议，明确证据缺口，不补造事实。"},
        ]

    def start_goal(self, goal: str, tasks: list[dict] | None = None) -> dict:
        """Create an auditable task plan in the real workforce queue."""
        plan = list(tasks if tasks is not None else self.default_plan(goal))
        if not isinstance(goal, str) or not goal.strip():
            raise ValueError("goal must be a non-empty string")
        if not plan or len(plan) > self.max_tasks:
            raise ValueError("task plan must contain between 1 and max_tasks items")
        created = []
        for item in plan:
            if not isinstance(item, dict) or not str(item.get("title", "")).strip():
                raise ValueError("each task needs a non-empty title")
            capability = item.get("capability", "general")
            if not isinstance(capability, str) or not capability.strip():
                raise ValueError("task capability must be a non-empty string")
            payload = {
                "title": str(item["title"]).strip(),
                "description": str(item.get("description", ""))[:8000],
                "capability": capability.strip(),
                "priority": item.get("priority", 3),
                "approval_required": bool(item.get("approval_required", False)),
                "success_criteria": item.get("success_criteria", {}),
                "evidence_required": bool(item.get("evidence_required", capability.strip() == "research")),
            }
            created.append(self._request("POST", "/api/workforce/tasks", payload)["task"])
        return {
            "goal": goal.strip(),
            "status": "planned",
            "created_tasks": created,
            "task_count": len(created),
            "note": "任务已进入真实队列；创建成功不代表员工已执行或结果已验证。",
        }

    def inspect(self) -> dict:
        """Read queue state and report only states backed by the server snapshot."""
        snapshot = self._request("GET", "/api/workforce")
        tasks = snapshot.get("tasks", [])
        counts = {"queued": 0, "assigned": 0, "completed": 0, "blocked": 0, "failed": 0}
        results = []
        for task in tasks:
            status = task.get("status", "queued")
            if status in counts:
                counts[status] += 1
            output = task.get("output", "")
            provenance = "unknown"
            if isinstance(output, str) and output:
                try:
                    envelope = json.loads(output)
                    if isinstance(envelope, dict) and isinstance(envelope.get("simulated"), bool):
                        provenance = "simulated" if envelope["simulated"] else "executor_reported_live"
                except (ValueError, TypeError):
                    pass
            try:
                from .verification import verify_task_output
            except ImportError:
                from verification import verify_task_output
            verification = verify_task_output(
                task,
                require_evidence=(task.get("capability") == "research"
                                  or bool(task.get("evidence_required"))),
                success_criteria=task.get("success_criteria"),
                provenance=provenance,
            )
            results.append({
                "task_id": task.get("id"),
                "title": task.get("title"),
                "capability": task.get("capability"),
                "status": status,
                "assigned_to": task.get("assigned_to"),
                "attempts": task.get("attempts"),
                "provenance": provenance,
                "has_output": bool(output),
                "output": output,
                "blocker": task.get("blocker", ""),
                "success_criteria": task.get("success_criteria", {}),
                "evidence_required": task.get("evidence_required", False),
                "verification": verification,
            })
        active = counts["queued"] + counts["assigned"]
        if active:
            status = "in_progress"
        elif counts["blocked"] or counts["failed"] or any(
            not item["verification"]["accepted"] for item in results
            if item["status"] == "completed"
        ):
            status = "needs_attention"
        elif counts["completed"]:
            status = "completed"
        else:
            status = "idle"
        return {"status": status, "counts": counts, "tasks": results,
                "events": snapshot.get("events", [])}

    def execute_goal(self, goal: str, employees: list, max_cycles: int = 8,
                     tasks: list[dict] | None = None,
                     execution_profile: dict | None = None,
                     revision_policy=None, independent_reviewer=None) -> dict:
        """Select a bounded execution mode, then supervise and verify the goal.

        Parallel execution is opt-in via explicit estimated benefits; a larger
        task list alone does not justify coordination overhead.
        """
        try:
            from .execution_strategy import TaskProfile, choose_execution_mode
        except ImportError:
            from execution_strategy import TaskProfile, choose_execution_mode
        if not isinstance(max_cycles, int) or not 1 <= max_cycles <= 20:
            raise ValueError("max_cycles must be an integer between 1 and 20")
        if not isinstance(goal, str) or not goal.strip():
            raise ValueError("goal must be a non-empty string")
        if not employees or any(not callable(getattr(worker, "run_once", None))
                                for worker in employees):
            raise ValueError("employees must contain agents exposing run_once()")

        plan_items = list(tasks if tasks is not None else self.default_plan(goal))
        supplied = dict(execution_profile or {})
        evidence_required = bool(supplied.pop("evidence_required", False)) or any(
            item.get("capability") == "research" or item.get("evidence_required", False)
            for item in plan_items
        )
        human_approval_required = bool(supplied.pop("human_approval_required", False)) or any(
            item.get("human_approval_required", False) for item in plan_items
        )
        profile_fields = {
            "complexity": min(5, max(1, len(plan_items))),
            "parallelizable": bool(len(plan_items) > 1 and all(
                item.get("parallelizable", False) for item in plan_items
            )),
            "quality_requirement": 3,
            "risk_level": 1,
            "evidence_required": evidence_required,
            "human_approval_required": human_approval_required,
            "independent_review_available": callable(independent_reviewer),
            "expected_parallel_quality_gain": 0.0,
            "expected_parallel_time_savings": 0.0,
            "team_cost_multiplier": 1.5,
        }
        profile_fields.update(supplied)
        profile_fields["evidence_required"] = evidence_required
        profile_fields["human_approval_required"] = human_approval_required
        profile = TaskProfile(**profile_fields)
        decision = choose_execution_mode(profile)
        events = [{"type": "goal_started", "task_count": len(plan_items)},
                  {"type": "execution_mode_selected", **decision.to_dict()}]
        if decision.mode == "approval_required":
            events.append({"type": "approval_required",
                           "reason": "The execution policy requires human approval before work starts."})
            return {
                "goal": goal.strip(), "status": "needs_approval", "cycles": 0,
                "counts": {"queued": 0, "assigned": 0, "completed": 0, "blocked": 0, "failed": 0},
                "tasks": [], "worker_runs": [], "events": events,
                "execution_decision": decision.to_dict(),
            }

        started_at = monotonic()
        plan = self.start_goal(goal, tasks=plan_items)
        ids = {task["id"] for task in plan["created_tasks"]}
        all_goal_ids = set(ids)
        worker_runs = []
        cycles = 0
        for cycle in range(1, max_cycles + 1):
            cycles = cycle
            before = {t["task_id"]: t["status"] for t in self.inspect()["tasks"]
                      if t["task_id"] in ids}
            if before and all(s in ("completed", "blocked", "failed") for s in before.values()):
                break
            pending = [t for t in self.inspect()["tasks"]
                       if t["task_id"] in ids and t["status"] in ("queued", "assigned")]
            needed = {t["capability"] for t in pending}
            compatible = [worker for worker in employees
                          if needed.intersection(set(getattr(worker, "capabilities", [])))
                          or "general" in getattr(worker, "capabilities", [])]
            if decision.mode == "single_agent":
                # One polling agent per cycle keeps coordination overhead low;
                # rotate by cycle so capability-specialized workers still get a turn.
                compatible = compatible[(cycle - 1) % len(compatible):] + compatible[:(cycle - 1) % len(compatible)] if compatible else []
                compatible = compatible[:1]
            if decision.mode == "parallel_team" and compatible:
                # Only use concurrent polling when the profile explicitly
                # justified parallelism. Each worker still claims its own task.
                with ThreadPoolExecutor(max_workers=min(len(compatible), self.max_tasks)) as pool:
                    futures = {pool.submit(worker.run_once): worker for worker in compatible}
                    cycle_results = []
                    for future in as_completed(futures):
                        try:
                            result = future.result()
                        except Exception as exc:
                            result = {"status": "agent_error",
                                      "error": type(exc).__name__ + ": " + str(exc)}
                        cycle_results.append(result)
                        worker_runs.append({"cycle": cycle, **result})
            else:
                cycle_results = []
                for employee in compatible:
                    try:
                        result = employee.run_once()
                    except Exception as exc:
                        result = {"status": "agent_error",
                                  "error": type(exc).__name__ + ": " + str(exc)}
                    cycle_results.append(result)
                    worker_runs.append({"cycle": cycle, **result})
            events.append({"type": "cycle_finished", "cycle": cycle,
                           "execution_mode": decision.mode, "worker_results": cycle_results})
            if revision_policy is not None:
                try:
                    revision_snapshot = self.inspect()
                    revision = revision_policy(
                        goal,
                        [t for t in revision_snapshot["tasks"] if t["task_id"] in ids],
                        cycle,
                    ) or {}
                    if not isinstance(revision, dict):
                        raise ValueError("revision_policy must return an object")
                    for action in revision.get("merge", [])[:10]:
                        target_id = action.get("target_task_id")
                        source_ids = action.get("source_task_ids", [])
                        reason = str(action.get("reason", "Plan consolidation"))
                        if target_id not in ids or not isinstance(source_ids, list) or any(sid not in ids for sid in source_ids):
                            events.append({"type": "revision_rejected", "action": "merge",
                                           "reason": "Task IDs must belong to the current goal."})
                            continue
                        try:
                            merged = self.merge_tasks(target_id, source_ids, reason)
                            ids.difference_update(source_ids)
                            events.append({"type": "tasks_merged", "target_task_id": target_id,
                                           "source_task_ids": source_ids, "reason": reason})
                        except (DigitalTwinAPIError, ValueError) as exc:
                            events.append({"type": "revision_rejected", "action": "merge",
                                           "reason": str(exc)[:300]})
                    for action in revision.get("cancel", [])[:10]:
                        task_id = action.get("task_id")
                        reason = str(action.get("reason", "No longer valuable"))
                        if task_id not in ids:
                            continue
                        try:
                            self.cancel_task(task_id, reason)
                            ids.discard(task_id)
                            events.append({"type": "task_cancelled", "task_id": task_id,
                                           "reason": reason})
                        except (DigitalTwinAPIError, ValueError) as exc:
                            events.append({"type": "revision_rejected", "action": "cancel",
                                           "task_id": task_id, "reason": str(exc)[:300]})
                except Exception as exc:
                    events.append({"type": "revision_policy_failed",
                                   "cycle": cycle, "error": type(exc).__name__})
            after = {t["task_id"]: t["status"] for t in self.inspect()["tasks"]
                     if t["task_id"] in ids}
            if after and all(s in ("completed", "blocked", "failed") for s in after.values()):
                break
            if before == after and not any(x.get("status") == "completed" for x in cycle_results):
                events.append({"type": "stalled", "cycle": cycle,
                               "reason": "No progress; check worker capability and credentials."})
                break
        snapshot = self.inspect()
        # Keep terminally cancelled/superseded work visible in the final audit.
        scoped = [t for t in snapshot["tasks"] if t["task_id"] in all_goal_ids]
        if decision.verification in ("evidence_gate", "independent_review"):
            try:
                from .verification import verify_task_output
            except ImportError:
                from verification import verify_task_output
            for task in scoped:
                if task["status"] == "completed":
                    task["verification"] = verify_task_output(
                        {"id": task["task_id"], "title": task.get("title"),
                         "capability": task.get("capability"),
                         "output": task.get("output", ""),
                         "success_criteria": task.get("success_criteria", {})},
                        require_evidence=(decision.verification == "evidence_gate"
                                          or task.get("capability") == "research"
                                          or bool(task.get("evidence_required"))),
                        success_criteria=task.get("success_criteria"),
                        independent_reviewer=(independent_reviewer
                                               if decision.verification == "independent_review"
                                               else None),
                    )
        counts = {s: sum(t["status"] == s for t in scoped)
                  for s in ("queued", "assigned", "completed", "blocked", "failed",
                            "cancelled", "superseded", "approval_required")}
        if not ids:
            # A goal with no remaining active work must not be reported as completed
            # merely because all work was cancelled or superseded.
            status = ("cancelled" if counts["cancelled"] else
                      "superseded" if counts["superseded"] else "needs_attention")
        elif counts["queued"] or counts["assigned"]:
            status = "needs_attention" if any(e["type"] == "stalled" for e in events) else "in_progress"
        elif counts["blocked"] or counts["failed"] or counts["completed"] != len(ids):
            status = "needs_attention"
        elif any(not t.get("verification", {}).get("accepted", False)
                 for t in scoped if t.get("status") == "completed"):
            status = "needs_attention"
            events.append({"type": "verification_rejected",
                           "task_ids": [t["task_id"] for t in scoped
                                        if t["status"] == "completed"
                                        and not t.get("verification", {}).get("accepted", False)],
                           "reason": "Completed worker output did not pass the required evidence gate."})
        else:
            status = "completed"
        events.append({"type": "goal_finished", "status": status, "counts": counts})
        metrics = {
            "elapsed_seconds": round(max(0.0, monotonic() - started_at), 4),
            "cycles": cycles,
            "worker_runs": len(worker_runs),
            "task_count": len(scoped),
            "accepted_outputs": sum(
                t["status"] == "completed" and t.get("verification", {}).get("accepted", False)
                for t in scoped
            ),
            "rejected_outputs": sum(
                t["status"] == "completed" and not t.get("verification", {}).get("accepted", False)
                for t in scoped
            ),
            "cancelled_tasks": counts["cancelled"],
            "superseded_tasks": counts["superseded"],
            "cost": None,
            "cost_note": "No cost is reported unless the executor provides a normalized, auditable cost field.",
        }
        events.append({"type": "execution_metrics", **metrics})
        return {
            "goal": goal.strip(), "status": status, "cycles": cycles, "counts": counts,
            "tasks": scoped, "worker_runs": worker_runs, "events": events,
            "execution_decision": decision.to_dict(), "metrics": metrics,
            "evidence_note": "执行器输出不自动等于已核实证据；必须检查来源与可复现性。",
        }

    def cancel_task(self, task_id: str, reason: str) -> dict:
        """Cancel pending work through the authenticated admin API."""
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        return self._request("POST", "/api/workforce/cancel", {
            "task_id": task_id, "reason": reason.strip()[:1000],
        })

    def merge_tasks(self, target_task_id: str, source_task_ids: list[str],
                    reason: str) -> dict:
        """Merge only compatible, unstarted tasks; server enforces final invariants."""
        if not isinstance(target_task_id, str) or not target_task_id.strip():
            raise ValueError("target_task_id must be a non-empty string")
        if not isinstance(source_task_ids, list) or not source_task_ids:
            raise ValueError("source_task_ids must be a non-empty list")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be a non-empty string")
        return self._request("POST", "/api/workforce/merge", {
            "target_task_id": target_task_id,
            "source_task_ids": source_task_ids,
            "reason": reason.strip()[:1000],
        })

    def give_feedback(self, task_id: str, message: str, kind: str = "correction") -> dict:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("task_id must be a non-empty string")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")
        return self._request("POST", "/api/workforce/feedback", {
            "task_id": task_id, "actor": "digital-twin",
            "message": message.strip()[:4000], "kind": kind,
        })

