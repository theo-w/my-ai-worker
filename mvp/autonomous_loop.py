"""
JARVIS 自主循环 (Autonomous Twin Loop)
=======================================

数字分身真正自己跑的闭环：

  分析玩家情感 → 翻译为游戏设计要求 → 生成游戏场景
  → 模拟玩家试玩 → 收集反馈 → 更新记忆 → 再来一轮

不依赖手动复制粘贴。每一轮结束后，分身会自己决定下一轮分析什么。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from emotion_radar import EmotionRadar, EmotionalRadarReport, EmotionCategory

# game_action 可能还没在本地，优雅降级
try:
    from game_action import interpret_and_validate_action, PATTERNS, _has
    GAME_ACTION_AVAILABLE = True
except ImportError:
    GAME_ACTION_AVAILABLE = False
    PATTERNS = {"key": "钥匙", "bell": "铃", "rail": "滑轨", "tide": "潮", "signal": "信号", "door": "门"}
    def _has(p, t): return p in t
    def interpret_and_validate_action(action, state, llm_client=None):
        return {"validation": {"ok": False, "title": "game_action未安装", "type": "unknown"}}

logger = logging.getLogger(__name__)


# ── 数字分身记忆 ──────────────────────────────────────────

@dataclass
class TwinMemory:
    """数字分身的长期记忆：记住分析过什么、学到了什么。"""
    analyses_done: list[dict] = field(default_factory=list)
    design_decisions: list[dict] = field(default_factory=list)
    learned_principles: list[str] = field(default_factory=list)
    failed_hypotheses: list[dict] = field(default_factory=list)
    next_target: str = ""

    def record_analysis(self, game: str, report: EmotionalRadarReport):
        self.analyses_done.append({
            "game": game,
            "top_peak": report.top_peaks(1)[0].moment if report.peaks else "",
            "top_valley": report.top_valleys(1)[0].moment if report.valleys else "",
            "crossroads": [c.moment for c in report.crossroads],
            "timestamp": time.time(),
        })

    def record_design(self, scenario_name: str, design_goal: str, source_game: str):
        self.design_decisions.append({
            "scenario": scenario_name,
            "goal": design_goal,
            "inspired_by": source_game,
            "timestamp": time.time(),
        })

    def record_learning(self, principle: str):
        if principle not in self.learned_principles:
            self.learned_principles.append(principle)
            logger.info("  🧠 新原则: %s", principle)

    def record_failure(self, hypothesis: str, evidence: str):
        self.failed_hypotheses.append({
            "hypothesis": hypothesis,
            "evidence": evidence,
            "timestamp": time.time(),
        })

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


# ── 从情感报告到游戏设计 ──────────────────────────────────

@dataclass
class DesignSpec:
    """从情感雷达翻译出来的游戏设计要求"""
    scenario_name: str
    goal: str
    must_have: list[str]
    must_avoid: list[str]
    success_criteria: list[str]


def translate_emotion_to_design(report: EmotionalRadarReport) -> DesignSpec:
    """把情感雷达报告翻译成游戏设计要求。"""
    principles = []
    must_have = []
    must_avoid = []

    for peak in report.top_peaks(3):
        if peak.emotion == EmotionCategory.SACRIFICE:
            must_have.append("玩家行动和NPC的命运有因果关联")
            principles.append("牺牲感来自信息差——玩家比主角先知道真相")
        elif peak.emotion == EmotionCategory.WONDER:
            must_have.append("两个看似无关的线索最终汇合")
            principles.append("震撼来自认知闭合——玩家自己发现关联")
        elif peak.emotion == EmotionCategory.BELONGING:
            must_have.append("回到熟悉的地方时有变化反馈")
            principles.append("归属感来自时间积累后的对比")

    for valley in report.top_valleys(3):
        if valley.emotion == EmotionCategory.EMPTINESS:
            must_avoid.append("通关后世界毫无变化")
            principles.append("空虚感来自目标消失——需要持续的未完成感")
        elif valley.emotion == EmotionCategory.GUILT:
            must_avoid.append("玩家知道真相但无能为力太久")
            principles.append("无力感不能持续太久——需要行动窗口")

    for wow in report.wow_moments[:2]:
        must_have.append(f"允许玩家组合：{wow.action}")
        principles.append(f"惊喜来自跨系统组合——{wow.structure}")

    for loop in report.retention_loops:
        if loop.strength >= 4:
            must_have.append(f"留存机制：{loop.mechanism}")

    return DesignSpec(
        scenario_name=f"验证: {report.top_peaks(1)[0].moment[:20] if report.peaks else '未知'}",
        goal=f"验证'{principles[0] if principles else '未知设计原则'}'是否能产生情感冲击",
        must_have=list(set(must_have)),
        must_avoid=list(set(must_avoid)),
        success_criteria=[
            "玩家能在3步内找到至少一种非标准解法",
            "玩家能解释为什么这个解法有效",
            "NPC的反应让玩家觉得他记得我做过什么",
        ],
    )


# ── 模拟玩家试玩 ──────────────────────────────────────────

@dataclass
class PlaytestResult:
    turns: int
    actions: list[dict] = field(default_factory=list)
    found_solution: bool = False
    solution_type: str = ""
    stuck_at: str = ""
    unrecognized_ideas: list[str] = field(default_factory=list)


def simulate_player(spec: DesignSpec, llm_client=None) -> PlaytestResult:
    """模拟一个玩家试玩。"""
    test_actions = [
        "我直接冲向仓库门",
        "我调查铜钥匙",
        "我用钥匙开门",
        "我调查铜铃",
        "我问修复师关于潮汐的事",
        "我把铜铃绑在滑轨上，等涨潮推它响",
        "我问搬运工关于旧信号的事",
        "我把铜铃绑在浮动滑轨上，涨潮时让它发出三声搬运信号",
    ]

    state = {"inspected": [], "talked": [], "selected": []}
    result = PlaytestResult(turns=0)

    for action in test_actions:
        result.turns += 1
        if not GAME_ACTION_AVAILABLE:
            if "钥匙" in action and "开门" in action:
                result.found_solution = True
                result.solution_type = "标准解法(模拟)"
                result.actions.append({"action": action, "ok": True, "result": "门开了(模拟)"})
                break
            result.actions.append({"action": action, "ok": False, "result": "待实现"})
            continue
        try:
            output = interpret_and_validate_action(action, state, llm_client)
            validation = output["validation"]
            result.actions.append({
                "action": action,
                "kind": output["interpretation"]["action_kind"],
                "ok": validation["ok"],
                "result": validation["title"],
            })
            for kw in ["key", "bell", "rope"]:
                if _has(PATTERNS[kw], action) and kw not in state["inspected"]:
                    state["inspected"].append(kw)
            if "修复师" in action:
                state["talked"].append("repairer")
            if "搬运工" in action:
                state["talked"].append("porter")
            if validation["ok"]:
                result.found_solution = True
                result.solution_type = validation.get("type", "unknown")
                break
        except Exception as e:
            result.unrecognized_ideas.append(action)
            logger.error("  行动解析失败: %s → %s", action, e)

    if not result.found_solution:
        result.stuck_at = "无法找到任何解法"
    return result


# ── 自主循环主引擎 ──────────────────────────────────────────

class AutonomousTwin:
    """数字分身自主循环引擎。"""

    def __init__(self, research_provider=None, llm_client=None):
        self.radar = EmotionRadar(research_provider, llm_client)
        self.llm = llm_client
        self.memory = TwinMemory()

    def run(self, game_title: str) -> dict:
        logger.info("=" * 60)
        logger.info("🤖 数字分身自主循环启动")
        logger.info("=" * 60)

        # Step 1: 情感雷达
        logger.info("\n📡 Step 1: 分析《%s》的玩家情感", game_title)
        report = self.radar.scan(game_title)
        self.memory.record_analysis(game_title, report)
        logger.info("  峰值: %s", report.top_peaks(1)[0].moment if report.peaks else "无")
        logger.info("  交汇点: %d 个", len(report.crossroads))

        # Step 2: 翻译为设计要求
        logger.info("\n🎯 Step 2: 翻译为游戏设计要求")
        spec = translate_emotion_to_design(report)
        self.memory.record_design(spec.scenario_name, spec.goal, game_title)
        logger.info("  目标: %s", spec.goal)
        logger.info("  必须有: %d 项", len(spec.must_have))

        # Step 3: 模拟试玩
        logger.info("\n🎮 Step 3: 模拟玩家试玩")
        playtest = simulate_player(spec, self.llm)
        logger.info("  用了 %d 回合", playtest.turns)
        logger.info("  找到解法: %s", playtest.found_solution)

        # Step 4: 从结果中学习
        logger.info("\n🧠 Step 4: 从结果中学习")
        for principle in self._extract_learnings(report, spec, playtest):
            self.memory.record_learning(principle)

        # Step 5: 决定下一轮
        self.memory.next_target = self._decide_next_target(game_title, report)
        logger.info("\n➡️  Step 5: 下一轮目标: %s", self.memory.next_target)

        return {
            "game": game_title,
            "emotion_report": report.to_json(),
            "design_spec": asdict(spec),
            "playtest": asdict(playtest),
            "memory": self.memory.to_json(),
        }

    def _extract_learnings(self, report, spec, playtest) -> list[str]:
        learnings = []
        if playtest.found_solution and "跨系统" in playtest.solution_type:
            learnings.append("跨系统组合解法确实能产生卧槽时刻")
        if playtest.found_solution and playtest.turns <= 5:
            learnings.append("标准解法路径太短，玩家可能跳过探索直接用钥匙")
        if len(playtest.unrecognized_ideas) > 0:
            learnings.append(f"规则覆盖不足：{len(playtest.unrecognized_ideas)}个玩家想法未被识别")
        if report.crossroads:
            learnings.append("玩法×叙事交汇点是最值得在新游戏中复现的设计")
        return learnings

    def _decide_next_target(self, current_game: str, report) -> str:
        if report.peaks and not report.valleys:
            return f"{current_game} 差评分析：玩家为什么失望"
        if report.crossroads:
            return "下一个要拆解的游戏（用户指定）"
        return "等待用户指定下一个分析目标"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    twin = AutonomousTwin()
    result = twin.run("塞尔达传说：王国之泪")
    print("\n" + "=" * 60)
    print("📊 数字分身自主循环完成")
    print("=" * 60)
    print(f"\n记忆中积累了 {len(twin.memory.learned_principles)} 条设计原则:")
    for p in twin.memory.learned_principles:
        print(f"  • {p}")
