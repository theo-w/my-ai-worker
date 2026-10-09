"""Bounded autonomous project loop for JARVIS.

This is a deterministic orchestration baseline, not an LLM or live execution
claim. Real tools can be injected behind the WorkerExecutor protocol later.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Callable


class ProjectStatus(str, Enum):
    PLANNING = "planning"
    RUNNING = "running"
    NEEDS_APPROVAL = "needs_approval"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProjectTask:
    id: str
    title: str
    capability: str
    status: str = "queued"
    output: str = ""
    requires_approval: bool = False


@dataclass
class DecisionOption:
    name: str
    summary: str
    benefits: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    cost_level: str = "unknown"
    time_level: str = "unknown"
    score: float = 0.0


@dataclass
class ProjectReport:
    goal: str
    status: str
    completed_tasks: int
    total_tasks: int
    options: list[dict]
    recommendation: str
    questions_for_human: list[str]
    events: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ApprovalPolicy:
    approval_required_for: set[str] = field(default_factory=lambda: {
        "production_release", "budget_commitment", "external_publication",
        "destructive_operation", "legal_commitment",
    })
    max_iterations: int = 3


class AutonomousProjectLoop:
    """Plan, execute, observe, and re-plan with bounded iterations."""

    def __init__(self, policy: ApprovalPolicy | None = None):
        self.policy = policy or ApprovalPolicy()

    def run(self, goal: str, tasks: list[ProjectTask],
            executor: Callable[[ProjectTask], str],
            options: list[DecisionOption] | None = None,
            requested_actions: list[str] | None = None) -> ProjectReport:
        events = [f"Goal accepted: {goal}", "Plan created"]
        questions: list[str] = []
        requested_actions = requested_actions or []
        gated = sorted(set(requested_actions) & self.policy.approval_required_for)
        if gated:
            questions.append(
                "Approval required before: " + ", ".join(gated)
            )
            events.append("Paused at human approval boundary")
            return ProjectReport(goal, ProjectStatus.NEEDS_APPROVAL.value, 0,
                                 len(tasks), [asdict(x) for x in (options or [])],
                                 self._recommend(options or []), questions, events)

        status = ProjectStatus.RUNNING
        iterations = 0
        while iterations < self.policy.max_iterations:
            iterations += 1
            events.append(f"Execution iteration {iterations}")
            pending = [task for task in tasks if task.status not in {"completed", "blocked"}]
            if not pending:
                break
            for task in pending:
                try:
                    task.status = "running"
                    task.output = executor(task)
                    task.status = "completed" if task.output.strip() else "blocked"
                    events.append(f"{task.id}: {task.status}")
                except Exception as exc:  # executor boundary; keep project state visible
                    task.status = "blocked"
                    task.output = f"Execution error: {type(exc).__name__}"
                    events.append(f"{task.id}: blocked")
            if all(task.status in {"completed", "blocked"} for task in tasks):
                break
            # The next iteration represents observe/evaluate/re-plan.
            events.append("Observed outcomes; plan re-evaluated")

        completed = sum(task.status == "completed" for task in tasks)
        if completed == len(tasks):
            status = ProjectStatus.COMPLETED
        elif completed:
            status = ProjectStatus.BLOCKED
            questions.append("Some tasks are blocked; provide missing inputs or approve a revised plan.")
        else:
            status = ProjectStatus.FAILED
            questions.append("No tasks completed; review tool access and task definitions.")
        events.append("Project checkpoint produced")
        return ProjectReport(goal, status.value, completed, len(tasks),
                             [asdict(x) for x in (options or [])],
                             self._recommend(options or []), questions, events)

    @staticmethod
    def _recommend(options: list[DecisionOption]) -> str:
        if not options:
            return "Insufficient information to rank options."
        ranked = sorted(options, key=lambda option: option.score, reverse=True)
        best = ranked[0]
        others = ", ".join(option.name for option in ranked[1:])
        return (f"Recommend {best.name} (score {best.score:.2f})."
                + (f" Alternatives considered: {others}." if others else ""))
