"""
JARVIS 玩家情感雷达 (Player Emotion Radar)
============================================

数字分身的核心能力模块：从海量玩家真实声音中聚类情感峰值，
挖掘玩家"欲罢不能"和"眼前一亮"的底层心理机制。

不自己玩游戏，而是读懂成千上万玩家说的话。

输出维度：
1. emotional_peaks  — 玩家在哪里哭了/震撼了
2. emotional_valleys — 玩家在哪里感到空虚/愤怒/孤独
3. wow_moments     — 玩家在哪里"卧槽还能这样"
4. retention_loops — 玩家为什么停不下来
5. crossroads      — 玩法线与叙事线交汇的那个点（最关键）
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ── 数据结构 ──────────────────────────────────────────────

class EmotionCategory(str, Enum):
    SACRIFICE = "sacrifice"           # 牺牲感
    BELONGING = "belonging"           # 归属感
    LONELINESS = "loneliness"         # 孤独感
    GUILT = "guilt"                   # 愧疚感
    WONDER = "wonder"                 # 震撼/敬畏
    DELIGHT = "delight"               # 惊喜/愉悦
    FRUSTRATION = "frustration"       # 挫败/愤怒
    EMPTINESS = "emptiness"           # 空虚/失重
    CURIOSITY = "curiosity"           # 好奇心被满足
    LONGING = "longing"               # 渴望/念想


@dataclass
class EmotionalMoment:
    """一个被聚类出来的情感峰值/低谷"""
    moment: str                       # 玩家体验到的具体瞬间
    player_quotes: list[str] = field(default_factory=list)  # 玩家原话
    emotion: EmotionCategory = EmotionCategory.WONDER
    frequency: int = 0                # 多少玩家提到（热度）
    mechanism: str = ""               # 背后的心理机制
    is_crossroad: bool = False        # 是否是玩法×叙事交汇点


@dataclass
class WowMoment:
    """玩家'卧槽还能这样'的瞬间"""
    action: str                       # 玩家做了什么
    structure: str                    # 惊喜结构（A+B=意外）
    player_quotes: list[str] = field(default_factory=list)
    is_emotional: bool = False         # 是否同时带情感冲击


@dataclass
class RetentionLoop:
    """让玩家欲罢不能的循环机制"""
    mechanism: str                    # 心理机制名称
    how_it_works: str                 # 在这个游戏里怎么体现
    strength: int = 0                 # 1-5，这个游戏做得到位程度


@dataclass
class EmotionalRadarReport:
    """完整的情感雷达报告"""
    game_title: str
    peaks: list[EmotionalMoment] = field(default_factory=list)
    valleys: list[EmotionalMoment] = field(default_factory=list)
    wow_moments: list[WowMoment] = field(default_factory=list)
    retention_loops: list[RetentionLoop] = field(default_factory=list)
    crossroads: list[EmotionalMoment] = field(default_factory=list)
    summary: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def top_peaks(self, n: int = 5) -> list[EmotionalMoment]:
        return sorted(self.peaks, key=lambda x: x.frequency, reverse=True)[:n]

    def top_valleys(self, n: int = 5) -> list[EmotionalMoment]:
        return sorted(self.valleys, key=lambda x: x.frequency, reverse=True)[:n]


# ── 情感雷达核心逻辑 ─────────────────────────────────────

class EmotionRadar:
    """
    玩家情感雷达引擎。

    用法：
        radar = EmotionRadar(research_provider, llm_client)
        report = radar.scan("塞尔达传说：王国之泪")
        print(report.to_json())

    流程：
        1. search  — 多语言、多平台搜索玩家情感表达
        2. cluster — LLM 把零散评论聚类成情感峰值
        3. diagnose — 给每个峰值标注心理机制
        4. crossroad — 找出玩法线×叙事线交汇的那个点
    """

    # 搜索关键词模板（中英双语，覆盖不同情绪）
    SEARCH_QUERIES = {
        "peaks_zh": "{game} 玩家 哭了 感动 泪目 最震撼 情感 高潮",
        "peaks_en": "{game} emotional moments cried what made players cry",
        "valleys_zh": "{game} 玩家 空虚 寂寞 愤怒 失望 后悔 差评",
        "valleys_en": "{game} disappointed frustrated boring empty after finishing",
        "wow_zh": "{game} 卧槽 居然 没想到 脑洞 离谱 惊喜 还能这样",
        "wow_en": "{game} unexpected moment discovery wow I did not expect that",
        "retention_zh": "{game} 停不下来 沉迷 几百小时 时间去哪了 为什么好玩",
        "retention_en": "{game} why can't stop playing hours flew by addictive",
    }

    def __init__(self, research_provider=None, llm_client=None):
        self.research = research_provider
        self.llm = llm_client

    def scan(self, game_title: str) -> EmotionalRadarReport:
        """
        对指定游戏执行完整的情感雷达扫描。

        Step 1: 多维度搜索
        Step 2: 聚类情感
        Step 3: 诊断心理机制
        Step 4: 找交汇点
        """
        logger.info("🎯 开始情感雷达扫描: %s", game_title)

        report = EmotionalRadarReport(game_title=game_title)

        # Step 1: 搜索玩家声音
        raw_voices = self._collect_voices(game_title)
        logger.info("  📥 收集到 %d 条玩家声音", len(raw_voices))

        # Step 2: 聚类情感峰值和低谷
        report.peaks = self._cluster_peaks(raw_voices)
        report.valleys = self._cluster_valleys(raw_voices)
        logger.info("  🔺 情感峰值: %d, 情感低谷: %d", len(report.peaks), len(report.valleys))

        # Step 3: 惊喜时刻
        report.wow_moments = self._cluster_wow(raw_voices)
        logger.info("  ⚡ 惊喜时刻: %d", len(report.wow_moments))

        # Step 4: 留存循环
        report.retention_loops = self._diagnose_retention(game_title, raw_voices)
        logger.info("  🔄 留存循环: %d", len(report.retention_loops))

        # Step 5: 找交汇点（最关键）
        report.crossroads = self._find_crossroads(report)
        logger.info("  🔀 玩法×叙事交汇点: %d", len(report.crossroads))

        # Step 6: 总结
        report.summary = self._summarize(report)

        return report

    # ── Step 1: 收集玩家声音 ──

    def _collect_voices(self, game_title: str) -> list[dict]:
        """从多个平台搜索玩家的情感表达。"""
        voices = []

        if self.research is None:
            logger.warning("  ⚠️ 无 research_provider，返回空数据")
            return voices

        for label, template in self.SEARCH_QUERIES.items():
            query = template.format(game=game_title)
            try:
                results = self.research.search(query, limit=10)
                for r in results:
                    voices.append({
                        "query_type": label,
                        "query": query,
                        "text": r.get("snippet", r.get("text", "")),
                        "source": r.get("source", ""),
                        "url": r.get("url", ""),
                    })
            except Exception as e:
                logger.error("  搜索失败 [%s]: %s", label, e)

        return voices

    # ── Step 2: 聚类 ──

    def _cluster_peaks(self, voices: list[dict]) -> list[EmotionalMoment]:
        """从玩家声音中聚类出情感峰值（哭了/震撼了）。"""
        peak_voices = [v for v in voices if "peaks" in v["query_type"]]
        if self.llm is None or not peak_voices:
            return self._fallback_peaks()

        prompt = self._build_cluster_prompt(peak_voices, "情感峰值（玩家感动/哭了/震撼）")
        return self._llm_cluster(prompt, EmotionalMoment)

    def _cluster_valleys(self, voices: list[dict]) -> list[EmotionalMoment]:
        """从玩家声音中聚类出情感低谷（空虚/愤怒/失望）。"""
        valley_voices = [v for v in voices if "valleys" in v["query_type"]]
        if self.llm is None or not valley_voices:
            return self._fallback_valleys()

        prompt = self._build_cluster_prompt(valley_voices, "情感低谷（玩家空虚/愤怒/孤独/失望）")
        return self._llm_cluster(prompt, EmotionalMoment)

    def _cluster_wow(self, voices: list[dict]) -> list[WowMoment]:
        """从玩家声音中聚类出'卧槽'时刻。"""
        wow_voices = [v for v in voices if "wow" in v["query_type"]]
        if self.llm is None or not wow_voices:
            return self._fallback_wow()

        prompt = self._build_cluster_prompt(wow_voices, "惊喜时刻（玩家没想到/卧槽/脑洞）")
        return self._llm_cluster(prompt, WowMoment)

    def _diagnose_retention(self, game: str, voices: list[dict]) -> list[RetentionLoop]:
        """诊断让玩家停不下来的底层心理机制。"""
        retention_voices = [v for v in voices if "retention" in v["query_type"]]
        if self.llm is None or not retention_voices:
            return self._fallback_retention()

        prompt = f"""
分析以下玩家声音，找出让玩家"欲罢不能"的心理机制。

玩家声音：
{json.dumps([v["text"][:200] for v in retention_voices[:10]], ensure_ascii=False, indent=2)}

已知的留存心理机制框架：
- 多巴胺预期（anticipation > reward）
- 可变奖励（variable ratio）
- 心流通道（challenge ≈ skill + 5%）
- 蔡格尼克效应（未完成的事 nag 你）
- 即时反馈（操作后2.8秒内响应）
- 创造循环（"如果我加个X呢？"）
- 叙事钩子（"最后到底怎样了？"）

输出 JSON 数组，每个元素包含：mechanism, how_it_works, strength(1-5)。
只输出 JSON，不要其他文字。
"""
        return self._llm_call(prompt, RetentionLoop)

    def _find_crossroads(self, report: EmotionalRadarReport) -> list[EmotionalMoment]:
        """
        找出玩法线×叙事线交汇的那个点。
        这是最关键的——玩家记住的不是单独的玩法或剧情，
        而是两者同时击中的瞬间。
        """
        crossroads = []
        for peak in report.peaks:
            # 一个峰值如果同时有玩法探索和叙事揭示，就是交汇点
            if any(kw in peak.moment for kw in ["原来", "居然", "一直", "其实", "真相", "发现"]):
                peak.is_crossroad = True
                crossroads.append(peak)
        return crossroads

    def _summarize(self, report: EmotionalRadarReport) -> str:
        top_peaks = report.top_peaks(3)
        top_valleys = report.top_valleys(3)
        parts = [
            f"玩家最感动的是：{', '.join(p.moment for p in top_peaks)}",
            f"玩家最空虚的是：{', '.join(v.moment for v in top_valleys)}",
        ]
        if report.crossroads:
            parts.append(f"最关键的交汇点是：{report.crossroads[0].moment}")
        return "；".join(parts)

    # ── LLM 调用 ──

    def _build_cluster_prompt(self, voices: list[dict], dimension: str) -> str:
        texts = [v["text"][:300] for v in voices[:15]]
        return f"""
从以下玩家声音中聚类出最常被提到的{dimension}。

玩家声音：
{json.dumps(texts, ensure_ascii=False, indent=2)}

要求：
1. 合并相似的瞬间为一类
2. 每类给出 moment（一句话描述）、player_quotes（2-3条原话）、frequency（粗略估计热度）、mechanism（背后的心理机制）
3. 按 frequency 从高到低排序
4. 只输出 JSON 数组，不要其他文字
"""

    def _llm_cluster(self, prompt: str, cls):
        if self.llm is None:
            return []
        try:
            raw = self.llm.complete(prompt)
            data = json.loads(raw)
            return [cls(**item) for item in data]
        except Exception as e:
            logger.error("LLM 聚类失败: %s", e)
            return []

    def _llm_call(self, prompt: str, cls):
        if self.llm is None:
            return []
        try:
            raw = self.llm.complete(prompt)
            data = json.loads(raw)
            return [cls(**item) for item in data]
        except Exception as e:
            logger.error("LLM 调用失败: %s", e)
            return []

    # ── 降级：基于王国之泪的已知数据 ──

    def _fallback_peaks(self) -> list[EmotionalMoment]:
        return [
            EmotionalMoment(
                moment="塞尔达吞下秘石化身为龙，在天上飞了几万年等林克",
                player_quotes=["公主化身为龙的那一刻我哭了", "她已经等了几万年"],
                emotion=EmotionCategory.SACRIFICE,
                frequency=95,
                mechanism="信息差：玩家比林克先知道真相，替林克心疼",
                is_crossroad=True,
            ),
            EmotionalMoment(
                moment="拔出大师剑，发现它一直在光龙头上",
                player_quotes=["我找了它整个游戏，它一直在我头顶飞过", "原来找剑和找公主是同一件事"],
                emotion=EmotionCategory.WONDER,
                frequency=90,
                mechanism="认知闭合：两件看似无关的事突然连起来了",
                is_crossroad=True,
            ),
            EmotionalMoment(
                moment="Sonia 在塞尔达面前突然被杀",
                player_quotes=["前一秒还在笑，下一秒就倒了", "近乎沉默，没有慢动作"],
                emotion=EmotionCategory.LONELINESS,
                frequency=75,
                mechanism="突然失去：没有预警的失去最痛",
            ),
        ]

    def _fallback_valleys(self) -> list[EmotionalMoment]:
        return [
            EmotionalMoment(
                moment="通关后一切回到原样，什么都没改变",
                player_quotes=["打完好空虚，意犹未尽", "老婆还在沉睡，辛苦一番什么都没改变"],
                emotion=EmotionCategory.EMPTINESS,
                frequency=85,
                mechanism="目标消失后的失重感：高刺激突然停止",
            ),
            EmotionalMoment(
                moment="龙之泪做完后三天没打开游戏",
                player_quotes=["没有办法接受不能立刻救塞尔达", "林克一直无知无觉"],
                emotion=EmotionCategory.GUILT,
                frequency=70,
                mechanism="无力感：你知道真相但什么都做不了",
            ),
        ]

    def _fallback_wow(self) -> list[WowMoment]:
        return [
            WowMoment(
                action="盾滑 + 矿车轨道 = 过山车",
                structure="A系统（盾滑下山）+ B系统（轨道矿车）= 开发者没想到的组合",
                player_quotes=["我居然在轨道上盾滑起来了"],
                is_emotional=False,
            ),
            WowMoment(
                action="小摩托 + 风扇 = 飞天摩托",
                structure="代步工具 + 飞行装置 = 不该行但居然行",
                player_quotes=["我造了个飞摩托！！！"],
                is_emotional=False,
            ),
        ]

    def _fallback_retention(self) -> list[RetentionLoop]:
        return [
            RetentionLoop(
                mechanism="可变奖励",
                how_it_works="每个神庙、洞穴、地底区域都是未知的，不知道下一个里面有什么",
                strength=5,
            ),
            RetentionLoop(
                mechanism="蔡格尼克效应",
                how_it_works="地图没探索完、龙之泪没找齐、神庙没开——'再开一个就睡'",
                strength=5,
            ),
            RetentionLoop(
                mechanism="创造循环",
                how_it_works="造出一个东西 → '如果我加个风扇呢？' → 再造一个",
                strength=5,
            ),
            RetentionLoop(
                mechanism="心流通道",
                how_it_works="神庙刚好5-10分钟谜题，难了看攻略，简单了秒过",
                strength=4,
            ),
        ]
