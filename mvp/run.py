#!/usr/bin/env python3
"""Small, dependency-free JARVIS Game Validation MVP."""

from dataclasses import dataclass
import sys


@dataclass
class Evidence:
    worker: str
    finding: str
    confidence: float
    simulated: bool = True


@dataclass
class Decision:
    recommendation: str
    confidence: int
    risks: list[str]
    next_step: str


WORKERS = [
    ("Game Market Researcher", "game_market_research"),
    ("Player Researcher", "player_research"),
    ("AI Technology Strategist", "game_ai_technology_feasibility"),
    ("AI Game Designer", "ai_gameplay_feasibility"),
]


def run_worker(worker: str, capability: str, goal: str) -> list[Evidence]:
    findings = {
        "game_market_research": [
            "AI-native interaction is increasingly viable as a differentiating game mechanic.",
            "The opportunity is strongest when AI changes the core loop rather than adding a chat feature.",
        ],
        "player_research": [
            "Persistent NPC relationships can create strong player attachment and retention hypotheses.",
            "Players still need clear goals, progression, and predictable gameplay value around AI interaction.",
        ],
        "game_ai_technology_feasibility": [
            "LLM dialogue plus persistent memory is technically feasible for a focused prototype.",
            "Latency, inference cost, memory consistency, and safety are the main technical risks.",
        ],
        "ai_gameplay_feasibility": [
            "Long-term NPC relationships can create gameplay unavailable in conventional scripted RPGs.",
            "The prototype should prove that AI changes decisions and outcomes, not merely dialogue volume.",
        ],
    }
    return [Evidence(worker, item, 0.78) for item in findings[capability]]


def evaluate(goal: str, evidence: list[Evidence]) -> Decision:
    return Decision(
        recommendation=recommendation,
        confidence=78 if recommendation == "GO_TO_PROTOTYPE" else (50 if demo_fallback else 42),
        risks=[
            "AI interaction may feel novel but not replayable",
            "NPC memory and behavior can drift",
            "Inference cost and latency may limit production economics",
        ],
        next_step="AI Game Prototype Sprint" if recommendation in {"GO_TO_PROTOTYPE", "DEMO_GO_TO_PROTOTYPE"} else "Evidence Collection Sprint",
    )


def run(goal: str) -> None:
    print("JARVIS")
    print("=" * 60)
    print(f"Goal: {goal}\n")
    print("Forming AI Game Strategy Team...")
    for worker, _ in WORKERS:
        print(f"  ✓ {worker}")

    evidence: list[Evidence] = []
    print("\nRunning workers...")
    for worker, capability in WORKERS:
        items = run_worker(worker, capability, goal)
        evidence.extend(items)
        print(f"  ✓ {worker}: {len(items)} evidence items")

    decision = evaluate(goal, evidence)

    print("\nEVIDENCE")
    print("-" * 60)
    print(f"Workers active: {len(WORKERS)}")
    print(f"Evidence collected: {len(evidence)} (SIMULATED)")

    print("\nDECISION")
    print("-" * 60)
    print(f"Recommendation: {decision.recommendation}")
    print(f"Confidence: {decision.confidence}%")

    print("\nRISKS")
    for risk in decision.risks:
        print(f"- {risk}")

    print("\nNEXT STEP")
    print(decision.next_step)


if __name__ == "__main__":
    goal = " ".join(sys.argv[1:]).strip()
    if not goal:
        goal = "评估一个 AI 原生游戏机会"
    run(goal)
