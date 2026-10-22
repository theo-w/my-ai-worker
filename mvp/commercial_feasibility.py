"""Commercial feasibility gate for AI-native game/play-mechanic validation.

This module turns a research recommendation into a decision contract. It does not
invent market data: missing inputs stay unknown and block a GO recommendation.
Scores are decision aids, not empirical probabilities.
"""
from __future__ import annotations

import math
from typing import Any

REQUIRED_DIMENSIONS = (
    "player_value",
    "differentiation",
    "technical_feasibility",
    "market_evidence",
    "unit_economics",
    "production_cost",
    "retention_and_replayability",
    "risk_and_compliance",
)

GRILL_ME_QUESTIONS = {
    "player_value": [
        "玩家会因为什么具体体验而选择这个玩法，而不是现有替代品？",
        "哪类玩家最在意这个价值？有什么真实行为证据，而不只是口头赞同？",
        "如果移除 AI，这个玩法还成立吗？AI 带来的增量价值是什么？",
    ],
    "differentiation": [
        "核心体验与已有游戏相比，真正不同的因果机制是什么？",
        "玩家或竞品分析者能否举出最强反例，说明它其实并不独特？",
    ],
    "technical_feasibility": [
        "关键 AI 能力在目标延迟、质量和可控性下能否实现？",
        "失败、越界输出、上下文丢失和高并发时如何降级？",
        "是否已有可运行原型或技术实验支持，而非仅有架构设想？",
    ],
    "market_evidence": [
        "目标市场与最窄的首批用户是谁？他们现在如何解决这个问题？",
        "有哪些独立、可追溯的支持证据与反对证据？",
        "哪些证据来自真实行为、付费或留存，哪些只是讨论热度？",
    ],
    "unit_economics": [
        "每名活跃玩家、每次核心循环、每小时游玩对应多少推理与服务成本？",
        "在保守、中性、乐观情景下，收入或可接受价格能否覆盖变动成本？",
        "成本随留存、会话长度和模型调用频率如何变化？",
    ],
    "production_cost": [
        "验证原型、垂直切片和可发布版本分别需要多少人周、现金与时间？",
        "哪些内容、模型评估、审核、运维和持续更新成本容易被漏算？",
        "最小实验能否用更低成本证伪最关键的假设？",
    ],
    "retention_and_replayability": [
        "新鲜感过后，玩家为什么会回来？玩法是否产生可持续的新状态或策略？",
        "哪些可观察指标能证明重复游玩价值，而不只是首次惊喜？",
    ],
    "risk_and_compliance": [
        "是否涉及隐私、用户生成内容安全、版权、未成年人或平台政策风险？",
        "哪些风险可能让产品即使技术可行也无法商业化？",
    ],
}

DEFAULT_THRESHOLDS = {
    "min_dimension_score": 3,
    "min_overall_score": 3.5,
    "min_independent_sources": 3,
    "require_prototype_evidence": True,
    "require_cost_model": True,
    "require_counter_evidence": True,
}


def build_feasibility_contract(goal: str, budget: float | None = None,
                               timebox_days: int | None = None) -> dict[str, Any]:
    """Create a task-specific research contract before workers start."""
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("goal must be a non-empty string")
    return {
        "goal": goal.strip(),
        "budget_limit": budget if isinstance(budget, (int, float)) and budget >= 0 else None,
        "timebox_days": timebox_days if isinstance(timebox_days, int) and timebox_days > 0 else None,
        "dimensions": list(REQUIRED_DIMENSIONS),
        "questions": {key: list(value) for key, value in GRILL_ME_QUESTIONS.items()},
        "thresholds": dict(DEFAULT_THRESHOLDS),
        "decision_options": ["GO_TO_PROTOTYPE", "ITERATE", "NO_GO", "INSUFFICIENT_EVIDENCE"],
        "status": "contract_ready",
        "note": "The contract defines what must be investigated; it is not itself evidence of feasibility.",
    }


def evaluate_commercial_feasibility(report: dict[str, Any],
                                    thresholds: dict[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate an evidence-backed report conservatively.

    Each dimension must provide score (1..5), evidence references, and a concise
    rationale. Missing values are unknown, never silently converted to zero or
    treated as a pass. Cost model and counter-evidence must be explicit.
    """
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    policy = dict(DEFAULT_THRESHOLDS)
    if isinstance(thresholds, dict):
        policy.update(thresholds)

    dimensions = report.get("dimensions", {})
    dimensions = dimensions if isinstance(dimensions, dict) else {}
    checks: list[dict[str, Any]] = []
    scores: list[float] = []
    missing: list[str] = []
    weak: list[str] = []

    for name in REQUIRED_DIMENSIONS:
        item = dimensions.get(name)
        if not isinstance(item, dict):
            missing.append(name)
            checks.append({"name": name, "status": "unknown", "passed": False,
                           "reason": "dimension not assessed"})
            continue
        score = item.get("score")
        refs = item.get("evidence_refs", [])
        rationale = item.get("rationale")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 1 <= score <= 5:
            missing.append(name)
            checks.append({"name": name, "status": "unknown", "passed": False,
                           "reason": "score must be between 1 and 5"})
            continue
        if not isinstance(refs, list) or not refs or not isinstance(rationale, str) or not rationale.strip():
            missing.append(name)
            checks.append({"name": name, "status": "unknown", "passed": False,
                           "reason": "score lacks evidence references or rationale"})
            continue
        scores.append(float(score))
        passed = score >= policy["min_dimension_score"]
        if not passed:
            weak.append(name)
        checks.append({"name": name, "status": "pass" if passed else "fail",
                       "passed": passed, "score": score, "evidence_refs": refs})

    source_count = report.get("independent_source_count")
    source_ok = isinstance(source_count, int) and source_count >= policy["min_independent_sources"]
    checks.append({"name": "independent_sources", "passed": source_ok,
                   "status": "pass" if source_ok else "fail",
                   "observed": source_count, "required": policy["min_independent_sources"]})

    prototype_ok = bool(report.get("prototype_evidence_refs"))
    if policy["require_prototype_evidence"]:
        checks.append({"name": "prototype_evidence", "passed": prototype_ok,
                       "status": "pass" if prototype_ok else "fail"})
    cost_model = report.get("cost_model")
    assumptions = cost_model.get("assumptions") if isinstance(cost_model, dict) else None
    scenarios = cost_model.get("scenarios") if isinstance(cost_model, dict) else None
    required_cost_fields = (
        "prototype_cost_usd",
        "model_cost_per_session_usd",
        "monthly_cost_usd_at_1000_users",
        "monthly_revenue_usd_at_1000_users",
        "break_even_users",
        "gross_margin_percent",
    )
    scenario_errors = []
    if not isinstance(assumptions, list) or not assumptions or any(
        not isinstance(item, (str, dict)) or (isinstance(item, str) and not item.strip())
        for item in assumptions
    ):
        scenario_errors.append("cost assumptions must be a non-empty list")
    if not isinstance(scenarios, dict):
        scenario_errors.append("cost scenarios are missing")
    else:
        for scenario_name in ("conservative", "base", "optimistic"):
            scenario = scenarios.get(scenario_name)
            if not isinstance(scenario, dict):
                scenario_errors.append(f"{scenario_name} scenario is missing")
                continue
            for field in required_cost_fields:
                value = scenario.get(field)
                valid_number = isinstance(value, (int, float)) and not isinstance(value, bool)
                if not valid_number:
                    scenario_errors.append(f"{scenario_name}.{field} must be numeric")
                    continue
                if not math.isfinite(value) or value < 0:
                    scenario_errors.append(f"{scenario_name}.{field} must be finite and non-negative")
            margin = scenario.get("gross_margin_percent")
            if isinstance(margin, (int, float)) and not isinstance(margin, bool) and margin > 100:
                scenario_errors.append(f"{scenario_name}.gross_margin_percent must not exceed 100")
    cost_ok = not scenario_errors
    if policy["require_cost_model"]:
        checks.append({"name": "cost_model", "passed": cost_ok, "status": "pass" if cost_ok else "fail",
                       "errors": scenario_errors})
    counter_refs = report.get("counter_evidence_refs")
    counter_ok = isinstance(counter_refs, list) and bool(counter_refs)
    if policy["require_counter_evidence"]:
        checks.append({"name": "counter_evidence", "passed": counter_ok,
                       "status": "pass" if counter_ok else "fail"})

    average = round(sum(scores) / len(scores), 2) if scores else None
    hard_fail = any(not check.get("passed", False) for check in checks)
    blockers = report.get("critical_blockers", [])
    explicit_critical_blocker = isinstance(blockers, list) and any(
        (isinstance(item, str) and item.strip()) or
        (isinstance(item, dict) and isinstance(item.get("reason"), str) and item["reason"].strip())
        for item in blockers
    )
    if missing:
        decision = "INSUFFICIENT_EVIDENCE"
    elif explicit_critical_blocker:
        decision = "NO_GO"
    elif weak or hard_fail or average is None or average < policy["min_overall_score"]:
        # A weak score is a signal to test or refine, not automatically to abandon.
        decision = "ITERATE"
    else:
        decision = "GO_TO_PROTOTYPE"

    return {
        "decision": decision,
        "average_dimension_score": average,
        "dimension_count_scored": len(scores),
        "checks": checks,
        "missing_dimensions": missing,
        "weak_dimensions": weak,
        "verified_truth": False,
        "limitations": [
            "Scores are structured judgments, not measured probabilities.",
            "GO_TO_PROTOTYPE authorizes a bounded prototype experiment, not full production.",
            "Any critical unknown or unverified cost assumption must remain visible to the decision-maker.",
        ],
    }
