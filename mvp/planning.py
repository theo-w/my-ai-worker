"""Goal-driven task planning with validated LLM plans and deterministic fallback."""
from __future__ import annotations
import json

ALLOWED_CAPABILITIES = {"research", "analysis", "design", "implementation", "testing", "decision", "general"}

def deterministic_plan(goal: str) -> dict:
    text = goal.lower()
    if any(token in text for token in ("game", "游戏", "npc", "rpg", "玩家")):
        tasks = [
            {"id": "opportunity_research", "title": "Identify the opportunity and collect source-backed evidence", "capability": "research", "status": "queued"},
            {"id": "feasibility_analysis", "title": "Assess player value, technical feasibility, cost, and risks", "capability": "analysis", "status": "queued"},
            {"id": "prototype_design", "title": "Define the smallest testable prototype and success criteria", "capability": "design", "status": "queued"},
            {"id": "decision_report", "title": "Compare options and prepare a go/no-go recommendation", "capability": "decision", "status": "queued"},
        ]
    else:
        tasks = [
            {"id": "goal_research", "title": "Clarify the goal and collect required evidence", "capability": "research", "status": "queued"},
            {"id": "option_analysis", "title": "Analyze options, constraints, costs, and risks", "capability": "analysis", "status": "queued"},
            {"id": "execution_plan", "title": "Prepare a practical execution plan and success criteria", "capability": "design", "status": "queued"},
            {"id": "decision_report", "title": "Compare alternatives and prepare a recommendation", "capability": "decision", "status": "queued"},
        ]
    return {"mode": "deterministic_fallback", "tasks": tasks, "warnings": ["LLM planning was not used; review this baseline plan before consequential execution."]}

def validate_plan(raw: str, max_tasks: int = 8) -> dict:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Planner response must be valid JSON.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise ValueError("Planner response must contain a tasks array.")
    tasks = data["tasks"]
    if not 1 <= len(tasks) <= max_tasks:
        raise ValueError(f"Planner must return 1 to {max_tasks} tasks.")
    validated, seen = [], set()
    for index, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            raise ValueError("Every planned task must be an object.")
        title = task.get("title")
        capability = task.get("capability", "general")
        task_id = task.get("id", f"task_{index}")
        if not isinstance(title, str) or not title.strip() or len(title) > 240:
            raise ValueError("Each task needs a non-empty title under 240 characters.")
        if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 80 or task_id in seen:
            raise ValueError("Task IDs must be unique non-empty strings under 80 characters.")
        if capability not in ALLOWED_CAPABILITIES:
            raise ValueError("Unsupported task capability: " + str(capability))
        seen.add(task_id)
        validated.append({"id": task_id, "title": title.strip(), "capability": capability, "status": "queued"})
    return {"mode": "llm", "tasks": validated, "warnings": ["LLM-generated plan; inspect tasks before high-impact actions."]}

def plan_project(goal: str, llm_client=None) -> dict:
    if llm_client is None:
        return deterministic_plan(goal)
    prompt = {"goal": goal, "required_output": {"tasks": [{"id": "unique_id", "title": "specific task", "capability": "research|analysis|design|implementation|testing|decision|general"}]}, "rules": ["Return JSON only.", "Create 3 to 6 actionable tasks.", "Do not claim external research or tool access has already occurred.", "Include evidence collection and a decision/review step when relevant.", "Do not include publishing, spending, legal, or destructive actions as pre-approved tasks."]}
    try:
        raw = llm_client.complete("You are the JARVIS project planner. Produce a safe, bounded plan, not task results. Return valid JSON only.", json.dumps(prompt, ensure_ascii=False))
        return validate_plan(raw)
    except Exception as exc:
        fallback = deterministic_plan(goal)
        fallback["warnings"].append("LLM planner unavailable or invalid (" + type(exc).__name__ + "); deterministic plan used.")
        return fallback
