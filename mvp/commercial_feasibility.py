"""Commercial feasibility gate for AI-native game/play-mechanic validation.

This module turns a research recommendation into a decision contract. It does not
invent market data: missing inputs stay unknown and block a GO recommendation.
Scores are decision aids, not empirical probabilities.
"""
from __future__ import annotations

import math
import os
from urllib.parse import urlsplit
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




def estimate_model_usage_costs(model: str | None = None, base_url: str | None = None) -> dict[str, Any]:
    """Estimate inference-only cost under explicit usage assumptions.

    Official DeepSeek peak cache-miss prices are used only for recognized model
    IDs on api.deepseek.com. Other providers require explicit per-million-token
    rates via environment variables. This is a scenario estimate, not measured
    production usage; provider pricing may change.
    """
    model_name = (model if model is not None else os.getenv("JARVIS_LLM_MODEL", "")).strip()
    endpoint = (base_url if base_url is not None else os.getenv("JARVIS_LLM_BASE_URL", "")).strip()
    host = (urlsplit(endpoint).hostname or "").lower() if endpoint else ""
    if host == "api.deepseek.com":
        if model_name in {"deepseek-chat", "deepseek-reasoner"}:
            return {
                "status": "deprecated_model_alias",
                "model": model_name,
                "message": "This DeepSeek model alias was retired; switch to deepseek-flash or deepseek-v4-pro before estimating or calling the provider.",
                "pricing_source": "https://api-docs.deepseek.com/updates/",
                "pricing_checked_at": "2026-10-22",
            }
        rates = {
            "deepseek-flash": {"input_peak": 0.30, "input_off_peak": 0.15, "output_peak": 1.20, "output_off_peak": 0.60},
            "deepseek-v4-flash": {"input_peak": 0.30, "input_off_peak": 0.15, "output_peak": 1.20, "output_off_peak": 0.60},
            "deepseek-v4-flash-vision-exp": {"input_peak": 0.30, "input_off_peak": 0.15, "output_peak": 1.20, "output_off_peak": 0.60},
            "deepseek-v4-pro": {"input_peak": 1.32, "input_off_peak": 0.66, "output_peak": 3.96, "output_off_peak": 1.98},
        }
        rate = rates.get(model_name)
        source = "https://api-docs.deepseek.com/quick_start/pricing/"
        pricing_mode = "official_peak_cache_miss_rates"
    else:
        try:
            input_rate = float(os.getenv("JARVIS_LLM_INPUT_USD_PER_MILLION_TOKENS", ""))
            output_rate = float(os.getenv("JARVIS_LLM_OUTPUT_USD_PER_MILLION_TOKENS", ""))
            if not math.isfinite(input_rate) or not math.isfinite(output_rate) or input_rate < 0 or output_rate < 0:
                raise ValueError
            rate = {"input_peak": input_rate, "input_off_peak": input_rate,
                    "output_peak": output_rate, "output_off_peak": output_rate}
            source = "operator_configured_rates"
            pricing_mode = "configured_flat_rates"
        except (TypeError, ValueError):
            rate = None
            source = None
            pricing_mode = None

    if rate is None:
        return {
            "status": "pricing_unavailable",
            "model": model_name or None,
            "message": "No recognized official price schedule or configured input/output rates are available.",
            "required_env": [
                "JARVIS_LLM_INPUT_USD_PER_MILLION_TOKENS",
                "JARVIS_LLM_OUTPUT_USD_PER_MILLION_TOKENS",
            ],
        }

    usage = {
        "conservative": {"calls_per_session": 12, "input_tokens_per_call": 6000, "output_tokens_per_call": 768, "sessions_per_user_month": 60},
        "base": {"calls_per_session": 6, "input_tokens_per_call": 3000, "output_tokens_per_call": 512, "sessions_per_user_month": 20},
        "optimistic": {"calls_per_session": 3, "input_tokens_per_call": 1500, "output_tokens_per_call": 256, "sessions_per_user_month": 10},
    }
    scenarios = {}
    for name, assumptions in usage.items():
        input_cost = assumptions["input_tokens_per_call"] * rate["input_peak"] / 1_000_000
        output_cost = assumptions["output_tokens_per_call"] * rate["output_peak"] / 1_000_000
        per_session = round((input_cost + output_cost) * assumptions["calls_per_session"], 8)
        monthly_sessions = assumptions["sessions_per_user_month"] * 1000
        scenarios[name] = {
            **assumptions,
            "active_users": 1000,
            "input_rate_usd_per_million_tokens": rate["input_peak"],
            "output_rate_usd_per_million_tokens": rate["output_peak"],
            "model_cost_per_session_usd": per_session,
            "monthly_ai_inference_cost_usd_at_1000_users": round(per_session * monthly_sessions, 2),
        }
    return {
        "status": "estimated",
        "model": model_name,
        "currency": "USD",
        "pricing_mode": pricing_mode,
        "price_basis": "peak input cache-miss and output rates; cache savings excluded",
        "pricing_source": source,
        "pricing_checked_at": "2026-10-22" if source != "operator_configured_rates" else None,
        "scenarios": scenarios,
        "limitations": [
            "Inference-only; excludes search, storage, hosting, moderation, human labor, and content production.",
            "Token and session counts are illustrative assumptions, not measured usage.",
            "Peak cache-miss pricing is used to avoid relying on cache savings or off-peak scheduling.",
        ],
    }


def build_feasibility_draft(goal: str, sources: list[dict[str, Any]] | None = None,
                            query_errors: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build a conservative assessment draft without fabricating scores or costs.

    Retrieved URLs are candidates, not proof of independent sources or semantic
    support. Dollar estimates remain unknown until model pricing, usage, labor,
    and monetization assumptions are supplied.
    """
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("goal must be a non-empty string")
    source_rows = sources if isinstance(sources, list) else []
    errors = query_errors if isinstance(query_errors, list) else []
    registry = []
    counter_candidates = []
    for index, source in enumerate(source_rows, start=1):
        if not isinstance(source, dict):
            continue
        queries = source.get("research_queries", [])
        queries = queries if isinstance(queries, list) else []
        row = {
            "id": "S" + str(index),
            "title": str(source.get("title", "")),
            "url": str(source.get("url", "")),
            "provider": str(source.get("provider", "unknown")),
            "research_queries": queries,
            "status": "retrieved_semantic_support_unverified",
        }
        registry.append(row)
        if any("counter evidence" in str(query).casefold() or "负面反馈" in str(query) for query in queries):
            counter_candidates.append(row["id"])

    dimensions = {
        name: {
            "score": None,
            "evidence_refs": [],
            "rationale": "尚未完成独立评估；搜索摘要本身不能证明该维度成立。",
            "status": "unknown",
        }
        for name in REQUIRED_DIMENSIONS
    }
    cost_fields = (
        "prototype_cost_usd",
        "model_cost_per_session_usd",
        "monthly_cost_usd_at_1000_users",
        "monthly_revenue_usd_at_1000_users",
        "break_even_users",
        "gross_margin_percent",
    )
    usage_estimate = estimate_model_usage_costs()
    scenarios = {
        scenario_name: {field: None for field in cost_fields}
        for scenario_name in ("conservative", "base", "optimistic")
    }
    if usage_estimate.get("status") == "estimated":
        for scenario_name, estimate in usage_estimate["scenarios"].items():
            scenarios[scenario_name]["model_cost_per_session_usd"] = estimate["model_cost_per_session_usd"]
            scenarios[scenario_name]["monthly_ai_inference_cost_usd_at_1000_users"] = estimate["monthly_ai_inference_cost_usd_at_1000_users"]
            scenarios[scenario_name]["usage_assumptions"] = {
                key: estimate[key] for key in (
                    "calls_per_session", "input_tokens_per_call", "output_tokens_per_call",
                    "sessions_per_user_month", "active_users"
                )
            }
    cost_assumptions = [
        "每次会话的调用数与 token 数是可编辑的情景假设，不是线上测量结果。",
        "AI 推理成本不包括搜索、存储、托管、审核、人力与内容制作。",
        "制作成本、月度总成本、收入、盈亏平衡点和毛利率仍需要实际输入。",
    ]
    if usage_estimate.get("status") == "estimated":
        cost_assumptions.append("推理价格来源：" + str(usage_estimate.get("pricing_source")) +
                                "；按峰时未缓存输入价格与输出价格估算，未计缓存折扣。")
    else:
        cost_assumptions.append(usage_estimate.get("message", "模型价格未知，尚不能估算美元推理成本。"))
    required_inputs = [
        "原型与垂直切片的人周、团队成本和时间盒",
        "月活跃用户、会话频率、留存、转化与净收入假设",
    ]
    if usage_estimate.get("status") != "estimated":
        required_inputs.insert(0, "模型输入/输出价格（按百万 token）")
        required_inputs.insert(1, "每次会话的模型调用数、输入/输出 token 数及重试比例")
    report = {
        "goal": goal.strip(),
        "dimensions": dimensions,
        "evidence_registry": registry,
        "independent_source_count": 0,
        "source_independence_review": "not_run",
        "prototype_evidence_refs": [],
        "cost_model": {
            "status": "partial_estimate" if usage_estimate.get("status") == "estimated" else "needs_inputs",
            "assumptions": cost_assumptions,
            "required_inputs": required_inputs,
            "pricing_estimate": usage_estimate,
            "scenarios": scenarios,
        },
        "counter_evidence_refs": [],
        "candidate_counter_evidence_refs": counter_candidates,
        "research_query_errors": errors,
        "critical_blockers": [],
    }
    evaluation = evaluate_commercial_feasibility(report)
    blockers = [
        "8 个评估维度尚未有可追溯的评分与理由",
        "来源独立性和关键主张的语义支持尚未独立核验",
        "缺少可运行原型/玩家实验的证据",
        ("AI 推理成本仅为透明假设下的粗估；制作成本、月度总成本、收入与盈亏平衡仍未验证"
         if usage_estimate.get("status") == "estimated"
         else "成本情景缺少可用模型价格与已验证的使用量、商业假设"),
        "反证仍是候选来源，尚未完成逐条审查",
    ]
    if errors:
        blockers.append(f"{len(errors)} 个调研角度搜索失败，需要补查")
    return {
        "status": "incomplete",
        "contract": build_feasibility_contract(goal),
        "report": report,
        "evaluation": evaluation,
        "completion": {"complete": False, "blockers": blockers},
    }



def apply_feasibility_gate(decision: dict[str, Any], assessment: dict[str, Any]) -> dict[str, Any]:
    """Prevent a generic evidence heuristic from bypassing the commercial gate."""
    result = dict(decision) if isinstance(decision, dict) else {}
    evaluation = assessment.get("evaluation") if isinstance(assessment, dict) else None
    completion = assessment.get("completion") if isinstance(assessment, dict) else None
    complete = isinstance(completion, dict) and completion.get("complete") is True
    gate_decision = evaluation.get("decision") if isinstance(evaluation, dict) else None
    if result.get("recommendation") == "DEMO_GO_TO_PROTOTYPE":
        risks = result.get("risks", [])
        risks = list(risks) if isinstance(risks, list) else []
        risks.append("仅为模拟演示建议，不是经证据支持的商业决策。")
        result["risks"] = risks
        result["next_step"] = "仅限演示；真实项目仍须补齐独立证据、反证、成本情景与原型验证。"
        return result
    if not complete or gate_decision != "GO_TO_PROTOTYPE":
        result["recommendation"] = "HOLD_FOR_EVIDENCE"
        try:
            result["confidence"] = min(50, max(0, int(result.get("confidence", 0))))
        except (TypeError, ValueError):
            result["confidence"] = 0
        risks = result.get("risks", [])
        risks = list(risks) if isinstance(risks, list) else []
        risks.append("商业可行性闸门未完成；不得将阶段性来源或通用启发式升级为 GO。")
        result["risks"] = risks
        result["next_step"] = "补齐独立证据、反证、成本情景与原型验证后重新评估。"
    return result


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
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not math.isfinite(score) or not 1 <= score <= 5:
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
    source_ok = isinstance(source_count, int) and not isinstance(source_count, bool) and source_count >= policy["min_independent_sources"]
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
                if not math.isfinite(value):
                    scenario_errors.append(f"{scenario_name}.{field} must be finite")
                elif field == "gross_margin_percent" and not -100 <= value <= 100:
                    scenario_errors.append(f"{scenario_name}.gross_margin_percent must be between -100 and 100")
                elif field != "gross_margin_percent" and value < 0:
                    scenario_errors.append(f"{scenario_name}.{field} must be non-negative")
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
