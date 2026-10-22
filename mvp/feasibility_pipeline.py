"""Automatic, evidence-first feasibility assessment for the JARVIS MVP.

This module uses deterministic code for traceability, explicit unknowns and cost
arithmetic. It never turns model prose, search snippets, or an unrun prototype
into verified facts.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

try:
    from .commercial_feasibility import REQUIRED_DIMENSIONS
except ImportError:
    from commercial_feasibility import REQUIRED_DIMENSIONS


DIMENSION_UNKNOWN_REASONS = {
    "player_value": "No direct target-player interview, behavior, willingness-to-pay, or retention evidence is attached to this run.",
    "differentiation": "Competitor alternatives and their comparable mechanics have not yet been independently mapped.",
    "technical_feasibility": "No runnable prototype, latency/reliability measurement, or adversarial test result is attached.",
    "market_evidence": "Search excerpts alone do not establish demand, real user behavior, conversion, or willingness to pay.",
    "unit_economics": "Provider prices, session usage, retention, conversion, and monetization inputs are not fully verified.",
    "production_cost": "Effort ranges are planning assumptions; team rates, content scope, QA, moderation, and operating quotes remain unknown.",
    "retention_and_replayability": "No longitudinal playtest or repeat-session data is attached.",
    "risk_and_compliance": "Privacy, safety, IP, age-rating, and platform-policy review has not been completed.",
}


def _positive_float(name: str) -> float | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def build_cost_model() -> dict:
    """Build transparent scenarios; cash costs remain unknown without configured rates."""
    input_price = _positive_float("JARVIS_LLM_INPUT_COST_PER_MILLION_USD")
    output_price = _positive_float("JARVIS_LLM_OUTPUT_COST_PER_MILLION_USD")
    person_week_rate = _positive_float("JARVIS_GAME_DEV_COST_PER_PERSON_WEEK_USD")

    assumptions = [
        {"name": "prototype_person_weeks", "basis": "editable early planning assumption, not a quote"},
        {"name": "monthly active users and sessions", "basis": "scenario inputs only, not a forecast"},
        {"name": "tokens per session", "basis": "illustrative workload assumption; measure with telemetry"},
        {"name": "model token prices", "basis": "configure provider-specific prices in Render environment variables"},
        {"name": "developer person-week rate", "basis": "configure your own fully loaded rate; cash cost otherwise unknown"},
    ]
    definitions = {
        "optimistic": {"prototype_person_weeks": 2, "vertical_slice_person_weeks": 6,
                       "monthly_active_users": 100, "sessions_per_user_month": 20,
                       "input_tokens_per_session": 2500, "output_tokens_per_session": 400},
        "base": {"prototype_person_weeks": 4, "vertical_slice_person_weeks": 12,
                 "monthly_active_users": 1000, "sessions_per_user_month": 40,
                 "input_tokens_per_session": 5000, "output_tokens_per_session": 800},
        "conservative": {"prototype_person_weeks": 8, "vertical_slice_person_weeks": 24,
                         "monthly_active_users": 10000, "sessions_per_user_month": 80,
                         "input_tokens_per_session": 10000, "output_tokens_per_session": 1800},
    }
    scenarios = {}
    for name, values in definitions.items():
        row = dict(values)
        monthly_input_tokens = values["monthly_active_users"] * values["sessions_per_user_month"] * values["input_tokens_per_session"]
        monthly_output_tokens = values["monthly_active_users"] * values["sessions_per_user_month"] * values["output_tokens_per_session"]
        row["monthly_input_tokens_assumed"] = monthly_input_tokens
        row["monthly_output_tokens_assumed"] = monthly_output_tokens
        row["model_cost_per_session_usd"] = (
            values["input_tokens_per_session"] * input_price / 1_000_000
            + values["output_tokens_per_session"] * output_price / 1_000_000
            if input_price is not None and output_price is not None else None
        )
        row["monthly_model_cost_usd"] = (
            monthly_input_tokens * input_price / 1_000_000
            + monthly_output_tokens * output_price / 1_000_000
            if input_price is not None and output_price is not None else None
        )
        row["prototype_labor_cost_usd"] = (
            values["prototype_person_weeks"] * person_week_rate
            if person_week_rate is not None else None
        )
        row["pricing_configured"] = input_price is not None and output_price is not None
        row["labor_rate_configured"] = person_week_rate is not None
        scenarios[name] = row

    return {
        "status": "priced_estimate" if input_price is not None and output_price is not None and person_week_rate is not None else "partial_estimate",
        "currency": "USD",
        "assumptions": assumptions,
        "pricing_inputs": {
            "input_cost_per_million_tokens_usd": input_price,
            "output_cost_per_million_tokens_usd": output_price,
            "developer_cost_per_person_week_usd": person_week_rate,
        },
        "scenarios": scenarios,
        "formula": "monthly model cost = active users × sessions/user/month × (input tokens/session × input price + output tokens/session × output price) / 1,000,000",
        "unpriced_items": [
            label for label, configured in [
                ("provider input/output token prices", input_price is not None and output_price is not None),
                ("developer person-week rate", person_week_rate is not None),
                ("payment/platform fees and net monetization", False),
                ("content, QA, moderation, infra, support and operational overhead", False),
            ] if not configured
        ],
        "warning": "Scenario values are editable planning assumptions, not forecasts or vendor quotes. Null USD costs mean pricing inputs are missing; do not interpret them as zero.",
    }


def _accepted_sources(research: dict | None, prefix: str) -> list[dict]:
    research = research if isinstance(research, dict) else {}
    quality = research.get("quality") or {}
    items = quality.get("items") or research.get("evidence") or []
    rows = []
    seen = set()
    for item in items:
        if not isinstance(item, dict) or item.get("quality_accepted") is not True:
            continue
        source = item.get("source")
        if not isinstance(source, dict):
            continue
        url = str(source.get("url", "")).strip()
        title = str(source.get("title", "")).strip()
        if not url.startswith("https://") or not title or url in seen:
            continue
        seen.add(url)
        rows.append({
            "id": prefix + str(len(rows) + 1),
            "title": title,
            "url": url,
            "snippet": str(source.get("snippet", item.get("finding", ""))).strip(),
            "provider": source.get("provider", "unknown"),
            "published_at": source.get("published_at"),
            "role": "counter_evidence_candidate" if prefix == "C" else "supporting_source_candidate",
            "quality_gate_passed": True,
            "semantic_support_verified": False,
        })
    return rows


def build_automatic_feasibility_report(
    goal: str,
    research: dict | None,
    counter_research: dict | None = None,
    design_brief: dict | None = None,
) -> dict:
    """Create a complete assessment record with explicit unknowns and traceable candidates."""
    primary = _accepted_sources(research, "S")
    counter = _accepted_sources(counter_research, "C")
    primary_urls = {row["url"].split("#", 1)[0].rstrip("/") for row in primary}
    counter = [row for row in counter if row["url"].split("#", 1)[0].rstrip("/") not in primary_urls]
    # Re-number after deduplication so references are stable and easy to read.
    for index, row in enumerate(counter, 1):
        row["id"] = "C" + str(index)

    all_urls = [row["url"] for row in primary + counter]
    domains = {((urlsplit(url).hostname or "").lower().removeprefix("www.")) for url in all_urls}
    dimensions = {
        name: {
            "status": "unknown",
            "score": None,
            "evidence_refs": [],
            "rationale": DIMENSION_UNKNOWN_REASONS[name],
            "confidence": "low",
        }
        for name in REQUIRED_DIMENSIONS
    }
    if primary:
        dimensions["market_evidence"]["evidence_refs"] = [row["id"] for row in primary]
        dimensions["market_evidence"]["rationale"] = (
            f"本轮搜索返回 {len(primary)} 条通过结构质量门禁的来源候选，覆盖 {len(domains)} 个不同主机名；"
            "来源语义支持、独立性与真实用户行为仍未核验，因此暂不评分。"
        )
    if counter:
        dimensions["differentiation"]["evidence_refs"] = [row["id"] for row in counter]
        dimensions["differentiation"]["rationale"] = (
            f"反向检索返回 {len(counter)} 条来源候选；它们尚未经过人工确认是否真正构成反证，"
            "因此仅登记为反证候选，不给出差异化评分。"
        )

    brief = design_brief if isinstance(design_brief, dict) else {}
    prototype_plan = brief.get("prototype_plan") or (brief.get("original_concept") or {}).get("prototype_plan") or {}
    return {
        "goal": str(goal).strip(),
        "assessment_status": "completed_with_gaps",
        "dimensions": dimensions,
        "source_registry": primary + counter,
        "independent_source_count": len(domains),
        "source_independence_method": "unique_hostname_proxy_only; not independently verified",
        "supporting_source_refs": [row["id"] for row in primary],
        "counter_evidence_refs": [row["id"] for row in counter],
        "prototype_evidence_refs": [],
        "prototype_plan": prototype_plan,
        "cost_model": build_cost_model(),
        "critical_blockers": [],
        "unresolved_questions": [
            "目标玩家是否真的有此需求，以及是否会持续游玩或付费？",
            "竞品对比是否证明了可感知的差异化？",
            "模型与服务价格、使用量、变现率和团队成本是多少？",
            "最小原型是否已实际运行，并由目标玩家完成可观测测试？",
        ],
        "limitations": [
            "检索摘要通过机械质量门禁不等于来源事实或语义支持已经独立验证。",
            "反向搜索结果是反证候选，不自动等于有效反证。",
            "所有未完成维度均显式标记为 unknown；当前结果不允许 GO。",
        ],
    }
