#!/usr/bin/env python3
"""Minimal Digital Twin policy/runtime for the JARVIS showcase MVP."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class TwinPolicy:
    autonomy_level: str = "managed"
    approval_required_for: list[str] | None = None
    max_parallel_workers: int = 4
    decision_style: str = "evidence_first"

    def __post_init__(self):
        if self.approval_required_for is None:
            self.approval_required_for = ["production_release", "budget_commitment"]


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
            requested_actions: list[str] | None = None) -> dict:
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
            pending = [task for task in tasks if task.get("status", "queued") not in ("completed", "blocked")]
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
            if all(task.get("status") in ("completed", "blocked") for task in tasks):
                break
            events.append({"type": "plan_re_evaluated", "iteration": iteration})

        completed = sum(task.get("status") == "completed" for task in tasks)
        blocked = sum(task.get("status") == "blocked" for task in tasks)
        status = "completed" if completed == len(tasks) else ("blocked" if completed else "failed")
        questions = []
        if blocked:
            questions.append("部分任务受阻；请补充缺失输入或批准调整后的计划。")
        if not tasks:
            status = "completed"
        events.append({"type": "checkpoint_created", "completed": completed, "blocked": blocked})
        return {
            "goal": goal, "status": status, "completed_tasks": completed,
            "total_tasks": len(tasks), "options": options,
            "recommendation": options[0]["name"] if options else None,
            "questions_for_human": questions, "events": events,
        }
