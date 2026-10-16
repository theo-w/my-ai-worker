"""Adaptive execution-mode selection for goal-driven AI work.

This module selects a work pattern from task signals rather than assuming a
fixed virtual-company structure. It is deterministic policy code, not an LLM
and not a substitute for evidence verification.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


ExecutionMode = Literal["single_agent", "parallel_team", "approval_required"]
VerificationMode = Literal["standard", "independent_review", "evidence_gate"]


@dataclass(frozen=True)
class TaskProfile:
    """Signals used to choose an execution pattern.

    Scores are bounded to 1..5 unless otherwise noted. Parallel benefit inputs
    are estimates in [0, 1], and team_cost_multiplier is relative to one agent.
    """
    complexity: int = 1
    parallelizable: bool = False
    quality_requirement: int = 3
    risk_level: int = 1
    evidence_required: bool = False
    human_approval_required: bool = False
    independent_review_available: bool = True
    expected_parallel_quality_gain: float = 0.0
    expected_parallel_time_savings: float = 0.0
    team_cost_multiplier: float = 1.0

    def __post_init__(self):
        for name in ("complexity", "quality_requirement", "risk_level"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
                raise ValueError(f"{name} must be an integer from 1 to 5")
        for name in ("expected_parallel_quality_gain", "expected_parallel_time_savings"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if not isinstance(self.team_cost_multiplier, (int, float)) or self.team_cost_multiplier < 1:
            raise ValueError("team_cost_multiplier must be at least 1")


@dataclass(frozen=True)
class ExecutionDecision:
    mode: ExecutionMode
    verification: VerificationMode
    parallel_benefit_score: float
    rationale: tuple[str, ...]
    profile: dict

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "verification": self.verification,
            "parallel_benefit_score": round(self.parallel_benefit_score, 3),
            "rationale": list(self.rationale),
            "profile": self.profile,
        }


def choose_execution_mode(profile: TaskProfile) -> ExecutionDecision:
    """Choose the least-complex mode that meets quality and safety needs.

    Team formation is justified only by measurable expected gains. Verification
    is a separate axis: a single agent can still require a strict evidence gate.
    """
    reasons: list[str] = []
    # Higher complexity contributes to the case for decomposition, but cannot
    # by itself justify a team when work is not parallelizable or gains are weak.
    complexity_bonus = 0.10 * (profile.complexity - 1) / 4
    estimated_gain = (
        0.45 * profile.expected_parallel_quality_gain
        + 0.45 * profile.expected_parallel_time_savings
        + complexity_bonus
    )
    cost_penalty = 0.20 * (profile.team_cost_multiplier - 1)
    benefit_score = max(0.0, min(1.0, estimated_gain - cost_penalty))

    if profile.human_approval_required:
        mode: ExecutionMode = "approval_required"
        reasons.append("The requested action crosses a human-approval boundary.")
    elif (
        profile.complexity >= 3
        and profile.parallelizable
        and profile.team_cost_multiplier <= 2.5
        and benefit_score >= 0.25
    ):
        mode = "parallel_team"
        reasons.append("Parallel decomposition has an estimated benefit above its coordination cost.")
    else:
        mode = "single_agent"
        if not profile.parallelizable:
            reasons.append("The task is not meaningfully parallelizable.")
        elif profile.complexity < 3:
            reasons.append("The task is not complex enough to justify coordination overhead.")
        elif profile.team_cost_multiplier > 2.5:
            reasons.append("The estimated team cost is too high for the expected gain.")
        else:
            reasons.append("Estimated parallel benefit does not clear the team-formation threshold.")

    if profile.evidence_required:
        verification: VerificationMode = "evidence_gate"
        reasons.append("Required claims must pass source/evidence checks before acceptance.")
    elif profile.risk_level >= 4 or profile.quality_requirement >= 4:
        if profile.independent_review_available:
            verification = "independent_review"
            reasons.append("High risk or quality requirements justify a separate review step.")
        else:
            verification = "evidence_gate"
            reasons.append("High risk or quality requirements require a strict gate; independent reviewer unavailable.")
    else:
        verification = "standard"
        reasons.append("Standard verification is proportionate to the stated risk and quality target.")

    return ExecutionDecision(
        mode=mode,
        verification=verification,
        parallel_benefit_score=benefit_score,
        rationale=tuple(reasons),
        profile=asdict(profile),
    )
