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
