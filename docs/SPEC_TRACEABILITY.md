# 规范-实现追溯矩阵（已迁移）

> **⚠️ 已迁移：** 本文件已被 `specs/traceability.md` 取代。
> 新的追溯矩阵位于 [specs/traceability.md](../specs/traceability.md)，
> 由 `scripts/verify_sdd.py` 自动生成，每次运行验证脚本时自动更新。
> 本文件保留作为历史参考。

> 本矩阵建立规范文档 → 代码实现 → 测试的映射关系。
> 每个规范条目都有对应的代码位置和测试覆盖。

## 图例

| 符号 | 含义 |
|------|------|
| ✅ | 规范已实现，测试已覆盖 |
| ⚠️ | 规范已实现，测试不完整 |
| 🔲 | 规范已定义，待实现 |

---

## 1. DIGITAL_WORKFORCE_PROTOCOL.md

### §2 Core responsibilities

| 规范条目 | 代码位置 | 测试位置 | 状态 |
|---------|---------|---------|------|
| 分身拥有目标、分解任务、选择员工、设优先级/期限、监控、处理阻塞、请求审批、综合结果 | `twin.py:DigitalTwin.form_team()`, `twin.py:DigitalTwinCoordinator.start_goal()`, `twin.py:DigitalTwinCoordinator.supervise_once()` | `test_twin.py`, `test_goal_execution_loop.py` | ✅ |
| 员工接受任务、确认、报告进度、返回结构化结果、上报阻塞 | `worker_agent.py:DigitalEmployeeAgent.run_once()`, `workforce.py:report()` | `test_worker_agent.py`, `test_workforce_api_integration.py` | ✅ |
| 人类操作员设目标/约束、审批门控、暂停/取消/改派 | `server.py:authenticate_workforce()`, `workforce.py:approve_task()`, `workforce.py:cancel_task()` | `test_workforce_api_integration.py` | ✅ |

### §3 Task lifecycle

| 规范条目 | 代码位置 | 测试位置 | 状态 |
|---------|---------|---------|------|
| 状态机：queued → assigned → accepted → running → succeeded\|blocked\|failed\|cancelled | `workforce.py:claim()` status="assigned", `workforce.py:report()` status="awaiting_validation"/"blocked"/"failed" | `test_workforce.py` 状态转换测试 | ✅ |
| blocked 任务可返回 queued（需解决阻塞） | `workforce.py:retry_task()` | `test_workforce_api_integration.py` | ✅ |
| 重试策略有界且幂等 | `workforce.py:retry_task()` max_attempts 检查 | `test_workforce.py` | ✅ |
| 结果 payload 未持久前不得标记 succeeded | `workforce.py:report()` → "awaiting_validation"，非 "completed" | `test_workforce_api_integration.py` | ✅ |

### §4 MVP task contract

| 规范条目 | 代码位置 | 测试位置 | 状态 |
|---------|---------|---------|------|
| task_id 稳定唯一 | `workforce.py:create_task()` uuid4.hex[:12] | `test_workforce.py` | ✅ |
| goal 是结果而非动作 | `server.py:validate_autonomous_request()` goal 校验 | `test_planning.py` | ✅ |
| instructions 范围和预期步骤 | `workforce.py:create_task()` description ≤5000 | `test_workforce.py` | ✅ |
| worker_type = capability | `workforce.py:create_task()` capability 字段 | `test_workforce.py` | ✅ |
| priority 1-5 | `workforce.py:create_task()` priority 钳位 1-5 | `test_workforce.py` | ✅ |
| created_at / updated_at | `workforce.py:create_task()` `_stamp()` | `test_workforce.py` | ✅ |
| constraints 预算/时间/策略/数据/工具边界 | `workforce.py:create_task()` success_criteria | `test_workforce.py` | ✅ |
| approval_required | `workforce.py:create_task()` status="approval_required" | `test_workforce.py` | ✅ |
| attempt / max_attempts | `workforce.py:create_task()` attempts=0, max_attempts | `test_workforce.py` | ✅ |

### §5 Worker feedback contract

| 规范条目 | 代码位置 | 测试位置 | 状态 |
|---------|---------|---------|------|
| task_id / worker_id / event_type | `workforce.py:report()` task_id, worker_id, status | `test_workforce_api_integration.py` | ✅ |
| summary 人类可读 | `workforce.py:report()` output ≤20000 | `test_workforce.py` | ✅ |
| progress 0-100 估计值，不视为完成证明 | `workforce.py:heartbeat_worker()` progress ≤500 | `test_workforce.py` | ✅ |
| artifacts 输出引用 | `workforce.py:report()` output 字段 | `test_workforce.py` | ✅ |
| evidence 来源/测试结果/观察 | `workforce.py:report()` evidence 字段（阶段二新增） | `test_evidence_chain.py`（待新增） | ⚠️ |
| blocker 阻塞时必填 | `workforce.py:report()` blocker ≤3000 | `test_workforce.py` | ✅ |
| timestamp | `workforce.py:report()` `_stamp()` | `test_workforce.py` | ✅ |

### §5.1 可靠性要求（协议文档）

| 规范条目 | 代码位置 | 测试位置 | 状态 |
|---------|---------|---------|------|
| 持久化任务和事件 | `workforce.py:save()` JSON 文件 | `test_workforce.py` | ✅ |
| 幂等键（待实现） | — | — | 🔲 |
| 追加式事件历史 | `workforce.py:_event()` events[-2000:] | `test_workforce.py` | ✅ |
| 员工能力边界和最小权限 | `server.py:_worker_capabilities()`, `workforce.py:claim()` | `test_workforce_api_integration.py` | ✅ |
| 模型自述置信度不替代证据 | `server.py:_audit_worker_result()` simulated 检查 | `test_quality_accuracy.py` | ✅ |
| 不可逆动作前要求审批 | `workforce.py:approve_task()` | `test_workforce.py` | ✅ |
| 暴露队列年龄/重试计数/阻塞任务/心跳/健康 | `monitor.py:build_monitor_report()`, `server.py:/api/state` | `test_monitor.py` | ✅ |
| 凭证不出任务载荷/日志/仓库 | `.gitignore`, `server.py` 不记录 token | `test_server_auth.py` | ✅ |

### §6 验收测试（协议文档 §10 条）

| 验收测试 | 测试位置 | 状态 |
|---------|---------|------|
| 1. 分身创建任务，出现在持久队列 | `test_workforce_api_integration.py:create_task` | ✅ |
| 2. 员工领取，状态变为 accepted | `test_workforce_api_integration.py:claim` | ✅ |
| 3. 员工报告进度，事件可见 | `test_workforce_api_integration.py:heartbeat` | ✅ |
| 4. 员工提交结果+证据，验证后变 succeeded | `test_workforce_api_integration.py:full_lifecycle` | ✅ |
| 5. 员工报告阻塞，分身暴露并提出下一步 | `test_workforce_api_integration.py:blocker_retry` | ✅ |
| 6. 超时未确认可改派，无重复完成 | `workforce.py:maintain()` lease expiry | ✅ |
| 7. 可重试故障仅重试 max_attempts 次 | `workforce.py:maintain()` + `retry_task()` | ✅ |
| 8. 门控动作需审批 | `workforce.py:approve_task()` | ✅ |
| 9. 重启不丢失任务/事件 | `workforce.py:load()` + `save()` | ✅ |
| 10. /health 和端到端 smoke test | `server.py:/api/llm/status` + `test_llm_smoke_api.py` | ✅ |

### §7 交付序列

| 交付步骤 | 状态 |
|---------|------|
| 1. 合同先行（本矩阵） | ✅ |
| 2. 可运行垂直切片 | ✅ |
| 3. 可观测性 | ✅ |
| 4. 多员工协调 | ⚠️ 部分实现 |
| 5. 领域包（AI 游戏可行性等） | ✅ |

---

## 2. DIGITAL_TWIN_EMPLOYEE_FLOW.md

| 规范条目 | 代码位置 | 测试位置 | 状态 |
|---------|---------|---------|------|
| 目标流：用户目标→分身→单代理优先判断 | `server.py:_execute_run()` goal 解析 + `twin.py:DigitalTwin.form_team()` | `test_twin.py` | ✅ |
| 任务流：任务含目标/描述/能力/优先级/成功标准/证据要求/权限约束 | `server.py:/api/twin/goal` → `workforce.py:create_task()` | `test_workforce.py` | ✅ |
| 执行反馈流：输出/状态/阻塞/证据引用 | `worker_agent.py:run_once()` → `workforce.py:report()` | `test_worker_agent.py` | ✅ |
| 验证流：按成功标准检查，缺证据不得通过 | `workforce.py:record_verification()` evidence_required 检查 | `test_verification.py` | ✅ |
| 重规划流：重试/补证/改派/合并/取消/结束 | `server.py:/api/twin/advance` + `workforce.py:retry/cancel/merge` | `test_workforce_api_integration.py` | ✅ |
| 监控流：心跳/状态/输入输出/验证/事件 | `monitor.py`, `server.py:/api/state` | `test_monitor.py` | ✅ |
| 递归自我改进：仅用严格验证结果 | `self_improvement.py:summarize_outcomes()` verified 检查 | `test_self_improvement.py` | ✅ |

---

## 3. GOAL_DRIVEN_ARCHITECTURE.md

| 规范条目 | 代码位置 | 测试位置 | 状态 |
|---------|---------|---------|------|
| 分身是闭环控制器，不是分发器 | `twin.py:DigitalTwinCoordinator.execute_goal()` | `test_goal_execution_loop.py` | ✅ |
| 员工角色临时，基于能力 | `workforce.py:claim()` capability 匹配 | `test_workforce.py` | ✅ |
| 单代理优先 | `execution_strategy.py:choose_execution_mode()` | `test_execution_strategy.py` | ✅ |
| 执行与验证分离 | `twin.py:AutonomousProjectLoop.run()` verifier 注入 | `test_verification.py` | ✅ |
| 闭环规划：重评估/合并/取消/重试 | `twin.py:AutonomousProjectLoop.run()` replanner | `test_goal_execution_loop.py` | ✅ |
| 可观测性是基础设施 | `monitor.py`, `server.py:/api/state` | `test_monitor.py` | ✅ |
| 策略和权限显式 | `server.py:authenticate_workforce()` | `test_server_auth.py` | ✅ |
| 先测量后标准化 | `self_improvement.py` | `test_self_improvement.py` | ✅ |

---

## 4. OBSERVABILITY.md

| 规范条目 | 代码位置 | 测试位置 | 状态 |
|---------|---------|---------|------|
| twin: workflow status + 状态计数 | `monitor.py:build_monitor_report()` | `test_monitor.py` | ✅ |
| employees/workers: 心跳注册/状态/进度/最后心跳 | `workforce.py:heartbeat_worker()` | `test_workforce.py` | ✅ |
| tasks: input/output/provenance/history | `workforce.py:snapshot()` | `test_workforce.py` | ✅ |
| alerts: 过期租约/停滞任务/阻塞/心跳缺失 | `monitor.py:build_monitor_report()` alerts | `test_monitor.py` | ✅ |
| 租约续期 fencing token | `workforce.py:renew_lease()` | `test_workforce_api_integration.py` | ✅ |
| Trace 页面 5 秒刷新 | `trace.html` setInterval | 手动验证 | ⚠️ |
| 手动验收场景 | `test_workforce_api_integration.py:test_acceptance_scenario_*` | ✅ |

---

## 5. SECURITY_AND_AUTH.md

| 规范条目 | 代码位置 | 测试位置 | 状态 |
|---------|---------|---------|------|
| Bearer Token 认证 | `server.py:authenticate_workforce()` | `test_server_auth.py` | ✅ |
| admin/worker 角色边界 | `server.py:authenticate_workforce()` role 检查 | `test_server_auth.py` | ✅ |
| 员工不能自赋能力 | `server.py:_worker_capabilities()` 服务端分配 | `test_workforce_api_integration.py` | ✅ |
| 每次领取独立租约令牌 | `workforce.py:claim()` _lease_token | `test_workforce_api_integration.py` | ✅ |
| 报告/续租携带当前令牌 | `workforce.py:report()` + `renew_lease()` token 校验 | `test_workforce_api_integration.py` | ✅ |
| 未配置时 fail-closed | `server.py:authenticate_workforce()` 503 | `test_server_auth.py` | ✅ |
| 公共演示模式隔离 | `server.py:authenticate_dashboard()` | `test_server_auth.py` | ✅ |
| Token ≥24 字符 | `server.py:authenticate_workforce()` 长度检查 | `test_server_auth.py` | ✅ |
| 凭证不出仓库 | `.gitignore` | 手动验证 | ✅ |

---

## 6. 阶段二新增：证据链原则 (§2.5)

| 规范条目 | 代码位置 | 测试位置 | 状态 |
|---------|---------|---------|------|
| 可追溯性：结论必须附带 URL/标题/摘录 | `workforce.py:report()` evidence 字段（待实现） | `test_evidence_chain.py`（待新增） | 🔲 |
| 原始数据客观性：保留原始摘录，标注来源类型 | `evidence.json` schema excerpt/source_type | `test_evidence_chain.py` | 🔲 |
| 来源可靠性论证：HTTPS/来源类型/时间/对立来源 | `server.py:_assess_source_reliability()`（待实现） | `test_evidence_chain.py` | 🔲 |
| 依据可溯源：决策记录证据 ID/忽略原因/不确定性 | `twin-decision.json` evidence_ids/ignored_evidence/uncertainty | `test_evidence_chain.py` | 🔲 |
| 不可伪造性：awaiting_validation 后员工不可修改 | `workforce.py:report()` 状态检查 | `test_workforce_api_integration.py` | ✅ |
| 模拟与真实明确标注 | `workforce.py:report()` evidence.simulated | `test_quality_accuracy.py` | ✅ |

---

## 7. OpenAPI 规范 (§1)

| 规范条目 | 代码位置 | 测试位置 | 状态 |
|---------|---------|---------|------|
| 25+ 端点完整定义 | `docs/api/openapi.yaml` | `server.py` 路由 | ✅ |
| 请求/响应 JSON Schema | `docs/api/openapi.yaml` components/schemas | — | ✅ |
| 错误码定义 | `docs/api/openapi.yaml` responses | `test_server_auth.py` | ✅ |
| 认证要求 | `docs/api/openapi.yaml` security | `test_server_auth.py` | ✅ |
| 语义说明（与协议文档对应） | `docs/api/openapi.yaml` description 字段 | — | ✅ |

---

## 8. 术语表 (§4)

| 术语 | 代码对应 | 规范位置 | 状态 |
|------|---------|---------|------|
| Digital Twin | `twin.py:DigitalTwin`, `DigitalTwinCoordinator` | `DIGITAL_WORKFORCE_PROTOCOL.md` §2 | ✅ |
| Digital Employee | `worker_agent.py:DigitalEmployeeAgent` | `DIGITAL_WORKFORCE_PROTOCOL.md` §2 | ⚠️ 术语不一致 |
| Workforce | `workforce.py:WorkforceRegistry` | `DIGITAL_WORKFORCE_PROTOCOL.md` §1 | ✅ |
| MVP | `DIGITAL_WORKFORCE_PROTOCOL.md` §100 | `docs/GLOSSARY.md` | ✅ |
