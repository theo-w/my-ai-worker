#!/usr/bin/env python3
"""Minimal Digital Twin policy/runtime for the JARVIS showcase MVP."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from datetime import datetime, timezone
import json


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
