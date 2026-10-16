"""Experience-mechanism analysis and original-game concept workflow.

Model output is treated as a design hypothesis, never as verified player research.
"""
from __future__ import annotations

import json

SYSTEM_PROMPT = """You are JARVIS, an experienced game-design partner. Analyze design mechanisms, not surface features.
Do not copy protected characters, story, world, maps, art, names, or signature mechanics from the reference game.
Distinguish observable design features from hypotheses about player psychology. Do not invent playtest results or market facts.
Return ONLY valid JSON with keys: source_game, mechanism_analysis, transferable_principles, original_concept, player_perspectives, falsifiable_hypotheses, prototype_plan, evidence_status.
mechanism_analysis: array of objects {feature, possible_experience, causal_mechanism, counter_hypothesis}.
transferable_principles: array of strings.
original_concept: object {title, one_line, core_loop, core_systems, signature_moment, differentiation}.
player_perspectives: array of objects {segment, likely_attraction, possible_rejection, validation_question}.
falsifiable_hypotheses: array of objects {hypothesis, failure_signal, metric}.
prototype_plan: object {scope, steps, sample_note, decision_gates}.
evidence_status: object {observations, hypotheses, unknowns, market_validated:false, playtested:false}.
Keep claims cautious, make the new concept distinct, and make the prototype plan small enough to build."""
 
def _template_brief(source_game: str) -> dict:
    return {
        "source_game": source_game,
        "mechanism_analysis": [
            {
                "feature": "物件与能力可以组合，环境遵循可学习的规则",
                "possible_experience": "玩家可能因发现非预设解法而感到惊喜和能动性",
                "causal_mechanism": "清楚的局部规则与开放的组合空间，让玩家形成假设、尝试并理解因果",
                "counter_hypothesis": "组合成本或规则反馈不清晰时，自由度也可能造成选择过载和挫败"
            },
            {
                "feature": "探索、资源、能力学习和新挑战相互连接",
                "possible_experience": "玩家可能持续投入，因为新知识会改变后续可行策略",
                "causal_mechanism": "学习到的规则能迁移到新问题，带来掌握感和自主目标",
                "counter_hypothesis": "若后续内容只是重复组合，惊喜可能衰减；时长本身不证明满意"
            }
        ],
        "transferable_principles": [
            "规则可理解，但结果空间不必完全预写",
            "玩家可以提出自己的解法，系统反馈应能解释因果",
            "失败应提供可用信息，而不是仅惩罚玩家",
            "在新情境中重用已学规则，形成掌握感",
            "将玩家行动与世界或人物后果连接，而非只增加对话量"
        ],
        "original_concept": {
            "title": "潮痕档案馆（Tidemark Archive）",
            "one_line": "玩家调查一座被周期性大潮重塑的海港城市，通过物件使用痕迹、潮汐规律与居民的局部记忆，重建被遗忘的互助网络。",
            "core_loop": ["观察物件和场所", "提出过去事件的解释", "寻找能区分解释的新证据", "利用潮汐与空间规则检验", "与居民交谈并观察关系变化", "选择公开或保留发现并影响后续线索"],
            "core_systems": [
                "按可预测周期变化的潮汐空间",
                "提供局部而非全知信息的物件使用痕迹",
                "知识边界、记忆和利益各不相同的居民"
            ],
            "signature_moment": "玩家把旧铜铃的磨损、潮汐推动的栏杆和居民关于旧搬运信号的记忆连接起来，令铃声沿水道传递，打开一条未被明确提示的维护通道；谜题解法同时揭示城市曾经的协作方式。",
            "differentiation": "核心不是物理拼装，而是跨空间线索、物件历史和人物记忆的因果推理。"
        },
        "player_perspectives": [
            {"segment": "系统探索者", "likely_attraction": "发现跨系统组合的解法", "possible_rejection": "规则边界模糊导致答案像随机事件", "validation_question": "玩家能否解释替代解法为什么有效？"},
            {"segment": "叙事导向玩家", "likely_attraction": "记忆冲突和人物关系会改变解释", "possible_rejection": "调查像做作业，人物信息与行动脱节", "validation_question": "人物信息是否实际改变了玩家的决定？"},
            {"segment": "目标导向玩家", "likely_attraction": "调查进展与清晰的阶段目标", "possible_rejection": "线索太分散，不知道下一步", "validation_question": "玩家能否复述当前目标并自主选择下一步？"},
            {"segment": "休闲玩家", "likely_attraction": "宁静探索和环境变化", "possible_rejection": "潮汐窗口带来不必要的时间压力", "validation_question": "玩家是否能按舒适节奏完成场景？"}
        ],
        "falsifiable_hypotheses": [
            {"hypothesis": "玩家可以组合至少两类线索，推导出非明确提示的有效方案。", "failure_signal": "玩家只能盲猜，或成功后解释不出因果。", "metric": "独立推导出的非标准解法数与因果解释率"},
            {"hypothesis": "人物记忆与关系后果让解法比单纯开门更有意义。", "failure_signal": "玩家只记住答案，人物信息不影响选择。", "metric": "延迟回忆、玩家自发提及的人物线索和选择理由"},
            {"hypothesis": "玩家拥有自主性，但不会因线索过于分散而迷失。", "failure_signal": "玩家频繁无效试错或无法说出当前目标。", "metric": "目标复述率、自主下一步选择率、无效试错次数"}
        ],
        "prototype_plan": {
            "scope": "一个仓库场景、一个潮汐周期、三个可调查物件、两个信息不完整的居民、一个标准解法与两个替代解法。",
            "steps": [
                "先做纸面流程或简单交互原型，确保每个结果都有可追踪的因果依据",
                "邀请5至8名目标玩家无口头提示试玩；此样本仅用于早期机制发现",
                "记录行动、玩家假设、失败原因、停顿点和原话",
                "试玩后询问玩家为何认为解法有效，以及人物信息如何影响判断",
                "将观察与推断分开编码，优先修复最主要的规则误解后再测"
            ],
            "sample_note": "小样本用于可用性与机制发现，不用于声称统计显著或代表市场。",
            "decision_gates": [
                "至少4/5参与者能说清当前目标",
                "至少3/5能独立推导一种非标准解法",
                "至少4/5成功者能解释解法的因果关系",
                "至少3/5能指出人物信息如何影响判断"
            ]
        },
        "evidence_status": {
            "observations": ["对参考游戏已知设计特征的概括，尚未在本轮逐项外部核验"],
            "hypotheses": ["所有关于惊喜、持续投入、叙事意义与玩家分群的因果解释"],
            "unknowns": ["真实玩家反应", "目标市场需求", "竞品差异与商业可行性", "概念原创性审查"],
            "market_validated": False,
            "playtested": False
        }
    }


def create_design_brief(source_game: str = "塞尔达传说：王国之泪",
                        concept_name: str = "潮痕档案馆",
                        llm_client=None) -> dict:
    """Create a structured brief; use the configured LLM when available.

    If no LLM is configured, return a clearly labeled deterministic template.
    """
    source_game = source_game.strip() if isinstance(source_game, str) else ""
    concept_name = concept_name.strip() if isinstance(concept_name, str) else ""
    if not source_game or len(source_game) > 160:
        raise ValueError("source_game must be between 1 and 160 characters.")
    if not concept_name or len(concept_name) > 160:
        raise ValueError("concept_name must be between 1 and 160 characters.")

    if llm_client is None:
        brief = _template_brief(source_game)
        brief["original_concept"]["title"] = concept_name + "（Tidemark Archive）" if concept_name != "潮痕档案馆" else "潮痕档案馆（Tidemark Archive）"
        brief["generation"] = {"mode": "template_fallback", "model_generated": False}
        return brief

    prompt = (
        "参考游戏：" + source_game + "\n"
        "候选新游戏名：" + concept_name + "\n"
        "请按系统约定的 JSON schema 生成完整的机制分析和原创游戏 MVP brief。"
        "请避免复制参考游戏的具体表达。所有玩家心理与市场判断都标注为假设。"
    )
    raw = llm_client.complete(SYSTEM_PROMPT, prompt)
    try:
        brief = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM response was not valid JSON.") from exc
    required = {"source_game", "mechanism_analysis", "transferable_principles",
                "original_concept", "player_perspectives", "falsifiable_hypotheses",
                "prototype_plan", "evidence_status"}
    if not isinstance(brief, dict) or not required.issubset(brief):
        raise ValueError("LLM response is missing required design-brief fields.")
    brief["generation"] = {"mode": "llm", "model_generated": True}
    # Prevent a model response from asserting validation that this workflow did not perform.
    status = brief.get("evidence_status")
    if isinstance(status, dict):
        status["market_validated"] = False
        status["playtested"] = False
    return brief
