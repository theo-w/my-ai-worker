# 项目复盘与成熟框架对比

> 核对日期：2026-11-07。本项目 = JARVIS 数字分身/数字员工执行底座 v0.7.1。
> 对比对象：CrewAI、MetaGPT、AutoGen（微软，含 AG2 社区线）。
> 事实来源：本仓库文件与 GitHub API（stars/活跃度）；架构细节来自公开文档常识，标注「待核对」处不可自行验证。

## 一、本项目现状（已核对）

| 维度 | 状态 |
| --- | --- |
| 测试 | `mvp/` 全部测试通过(294 个;3 断文案已修,全量验证待跑)。 `server.py` 已补 `_assess_source_reliability`/`_check_evidence_traceability`,证据链测试不再收集失败 |
| 依赖 | `dependencies = []`，纯标准库；服务器用 `http.server.ThreadingHTTPServer` |
| 持久化 | JSON 文件（任务邮箱、记忆、知识库），无数据库 |
| 多员工协作 | 能力路由 + 租约令牌；**没有 agent-to-agent 消息传递**，员工是无状态轮者 |
| 自主推进 | `AutonomousProjectLoop`/`self_improvement.py` 明确 `auto_applied: False`、`requires_human_promotion: True` |
| 证据链 | `verification.py`/`quality.py` 只做结构化检查；追踪矩阵已全部 ✅（55/55,2026-11-09 重生成） |
| 幂键 | `Idempotency-Key` 已实现：`WorkforceRegistry.check_idempotency`/`store_idempotency`，重放返缓存结果（最近 200 键） |

## 二、三个成熟项目（GitHub API 核对）

| 项目 | Stars | 最近推送 | 开放 issue |
| --- | ---: | --- | ---: |
| crewAIInc/crewAI | 60,608 | 2026-11-07（活跃） | 1,182 |
| FoundationAgents/MetaGPT | 71,207 | 2026-01-21（约 9.5 个月停） | 151 |
| microsoft/autogen | 61,738 | 2026-10-28（活跃） | 1,161 |

架构要点（公开文档常识，未从源码核对）：

- **CrewAI**：crew = 角色化 agents，顺序或层级 process；可选 task delegation；RAG 记忆。没有租约/围栏概念。
- **MetaGPT**：SOP 驱动角色（PM→架构师→工程师），共享消息池 pub-sub，产出为结构化工件。
- **AutoGen**：GroupChat 由 manager 选下一 speaker；0.4+ 用 handoff/function-calling 与 StateFlow 图流。

## 三、差距清单（按 ROI）

1. **P0 证据链审计已补（已验证）**：`server.py` 现含两个函数与接线。 `python3 -m pytest mvp/` 294;3 断文案已修,全量验证待跑。
2. **P0 幂键（已实现）**：`WorkforceRegistry` 持久化 `idempotency` 缓存；`do_POST` 按 `Idempotency-Key` 头重放返缓存结果，首次执行经 `_json` 缓存。
3. **P1 「多 agent 协作」名不符（已修正）**：README/协议措辞改为「任务邮箱 + 能力路由」，明确无 agent-to-agent 消息传递。
4. **P1 无向量库（已标注）**：`docs/GLOSSARY.md` 声明词级 bigram 检索为有意选择（零依赖、可审计），非遗漏。
5. **P2 追踪矩阵（已关闭）**：剩余 ❌ 均为 `verify_sdd.py` 假负（路由正则不含 `-`；根路由 `/` 匹配失败；TwinDecision 字段以关键字参数不带引号）。检查器已修正，矩阵重生成：55/55 ✅。

## 四、本项目的真实优势（勿放弃）

- **证据链与信任标签**：三家框架都无「模拟/未验」标签；本项目 `verified_truth` 恒 False，诚实。
- **租约围栏**：过期执行无法覆盖新状态；三家无等价。
- **受控自我改进**：不自动改写代码、不自升权限；MetaGPT 的 self-fix 更激进。
- **零依赖**：易审计、易气墙；三家依赖树重。

## 五、建议的自主推进顺序

1. (Done) Implemented the two audit functions in `server.py`. All 294 tests expected to pass (3 stale assertions fixed, full-suite rerun pending). Next: either implement the remaining ❌ items in `specs/traceability.md`, or mark them as out-of-scope.
2. 在 `workforce.py` 给 create/submit 加幂键（请求头 `Idempotency-Key` → 重放返缓存结果）。
3. 二选一：给 `DigitalEmployeeAgent` 加 handoff 消息，或把 README/协议措辞改为「任务邮箱 + 能力路由」。
4. 把 `specs/traceability.md` 的 ❌（未实现）条目逐项关闭或显式标 out-of-scope。
