"""Explicit executor boundary for JARVIS project tasks.

The default executor is deliberately simulated. Real integrations should be
registered by capability and return concrete outputs; missing capabilities
fail closed instead of being reported as successful work.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Protocol


@dataclass
class WorkerExecutionResult:
    task_id: str
    capability: str
    status: str
    output: str
    simulated: bool
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class WorkerExecutor(Protocol):
    def execute(self, task: dict, goal: str) -> WorkerExecutionResult:
        """Execute one task and return an auditable result."""


class SimulatedWorkerExecutor:
    """Explicit demo executor; never represents its output as real evidence."""

    def execute(self, task: dict, goal: str) -> WorkerExecutionResult:
        task_id = str(task.get("id", "unnamed"))
        capability = str(task.get("capability", "general"))
        title = str(task.get("title", capability))
        return WorkerExecutionResult(
            task_id=task_id,
            capability=capability,
            status="completed",
            output=f"[SIMULATED] Demo output for: {title}. Goal: {goal}",
            simulated=True,
            metadata={"mode": "simulation", "external_tools_used": False},
        )


class RegistryWorkerExecutor:
    """Dispatch tasks to explicitly registered capability handlers.

    A handler must return a non-empty string. Unregistered capabilities raise
    LookupError so the project loop records a blocked task rather than success.
    """

    def __init__(self, handlers: dict[str, Callable[[dict, str], str]] | None = None):
        self.handlers = dict(handlers or {})

    def register(self, capability: str, handler: Callable[[dict, str], str]) -> None:
        if not capability.strip():
            raise ValueError("Capability must not be empty.")
        self.handlers[capability] = handler

    def execute(self, task: dict, goal: str) -> WorkerExecutionResult:
        task_id = str(task.get("id", "unnamed"))
        capability = str(task.get("capability", "general"))
        handler = self.handlers.get(capability)
        if handler is None:
            raise LookupError(f"No executor registered for capability: {capability}")
        output = handler(task, goal)
        if not isinstance(output, str) or not output.strip():
            raise ValueError(f"Executor returned no usable output for: {capability}")
        return WorkerExecutionResult(
            task_id=task_id,
            capability=capability,
            status="completed",
            output=output,
            simulated=False,
            metadata={"mode": "registered_adapter", "external_tools_used": "adapter-defined"},
        )


class LLMWorkerExecutor:
    """Execute task instructions with an LLM; output is not external evidence."""

    def __init__(self, client):
        self.client = client

    def execute(self, task: dict, goal: str) -> WorkerExecutionResult:
        import json
        task_id = str(task.get("id", "unnamed"))
        capability = str(task.get("capability", "general"))
        title = str(task.get("title", capability))
        context = {
            "goal": goal,
            "task": task,
            "instruction": (
                "Complete the assigned task. Separate assumptions from verified facts. "
                "Do not invent citations, URLs, experiments, or external actions. "
                "If external evidence is needed but not supplied, say so explicitly."
            ),
        }
        output = self.client.complete(
            "You are a careful JARVIS digital worker. Return a concise, structured result. "
            "Model-generated claims are not independently verified evidence.",
            json.dumps(context, ensure_ascii=False),
        )
        if not isinstance(output, str) or not output.strip():
            raise ValueError("LLM returned no usable output for task: " + task_id)
        try:
            from .accuracy import classify_output
        except ImportError:
            from accuracy import classify_output
        trust = classify_output("llm")
        return WorkerExecutionResult(
            task_id=task_id,
            capability=capability,
            status="completed",
            output=output,
            simulated=False,
            metadata={
                "mode": "llm",
                "provider": "openai_compatible",
                "model": getattr(self.client, "model", "configured"),
                "external_tools_used": False,
                "output_is_verified_evidence": False,
                **trust,
            },
        )
