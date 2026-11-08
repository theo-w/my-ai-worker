# 协议规约（Protocol Spec）

> **版本：** 0.7.1
> **最后更新：** 2026-10-26
> **来源：** 从 `docs/DIGITAL_WORKFORCE_PROTOCOL.md` 提取，保留关键约束。
> **引用：** [完整协议文档](../docs/DIGITAL_WORKFORCE_PROTOCOL.md)
> **追溯：** [SPEC_TRACEABILITY.md](../docs/SPEC_TRACEABILITY.md)

## 图例

| 符号 | 含义 |
|------|------|
| ✅ | 代码已实现，测试已覆盖 |
| ⚠️ | 代码已实现，测试不完整 |
| 🔲 | 规约已定义，代码未实现 |

---

## 1. 核心职责

### 1.1 数字分身（Digital Twin）

数字分身是闭环控制器，不是简单分发器。

| 职责 | 代码位置 | 状态 |
|------|---------|------|
| 拥有用户目标 | `twin.py:DigitalTwinCoordinator` | ✅ |
| 分解目标为任务图 | `twin.py:DigitalTwin.form_team()` | ✅ |
| 选择员工（能力匹配） | `workforce.py:claim()` | ✅ |
| 设置优先级和期限 | `workforce.py:create_task()` priority, `lease_seconds` | ✅ |
| 监控执行 | `server.py:supervise_workforce()` | ✅ |
| 处理阻塞 | `workforce.py:report(status=blocked)` | ✅ |
| 请求审批（不可逆动作前） | `workforce.py:approve_task()` | ✅ |
| 综合结果 | `twin.py:DigitalTwinCoordinator.supervise_once()` | ✅ |

### 1.2 数字员工（Digital Employee）

| 职责 | 代码位置 | 状态 |
|------|---------|------|
| 接受任务 | `workforce.py:claim()` → status="assigned" | ✅ |
| 确认任务 | `workforce.py:report(status=in_progress)` | ✅ |
| 报告进度 | `workforce.py:heartbeat_worker()` | ✅ |
| 返回结构化结果 | `workforce.py:report(status=completed)` | ✅ |
| 上报阻塞 | `workforce.py:report(status=blocked)` | ✅ |

### 1.3 人类操作员

| 职责 | 代码位置 | 状态 |
|------|---------|------|
| 设目标和约束 | `server.py:POST /api/twin/goal` | ✅ |
| 审批门控 | `workforce.py:approve_task()` | ✅ |
| 暂停/取消/改派 | `workforce.py:cancel_task()`, `workforce.py:retry_task()` | ✅ |

---

## 2. 任务生命周期状态机

### 2.1 状态图

```
queued ──claim──> assigned ──report(in_progress)──> assigned(heartbeat)
  │                    │                                    │
  │                    ▼                                    ▼
  │                  blocked                         awaiting_validation
  │                    │                                    │
  │                    ▼                                    ▼
  │                  queued                         completed / failed
  │                    │
  └────retry──────────┘
```

### 2.2 状态转换规则

| 转换 | 触发条件 | 代码位置 | 约束 | 状态 |
|------|---------|---------|------|------|
| queued → assigned | `claim()` 能力匹配 | `workforce.py:claim()` | capability 必须匹配 | ✅ |
| assigned → awaiting_validation | `report(status=completed)` | `workforce.py:report()` | lease_token 必须有效 | ✅ |
| assigned → blocked | `report(status=blocked)` | `workforce.py:report()` | lease_token 必须有效 | ✅ |
| assigned → failed | `report(status=failed)` | `workforce.py:report()` | lease_token 必须有效 | ✅ |
| assigned → assigned | `report(status=in_progress)` | `workforce.py:report()` | 续租，更新 lease_until | ✅ |
| blocked → queued | `retry_task()` | `workforce.py:retry_task()` | attempts < max_attempts | ✅ |
| failed → queued | `retry_task()` | `workforce.py:retry_task()` | attempts < max_attempts | ✅ |
| awaiting_validation → completed | `record_verification(accepted=true)` | `workforce.py:record_verification()` | 管理员操作 | ✅ |
| approval_required → queued | `approve_task()` | `workforce.py:approve_task()` | 管理员操作 | ✅ |
| 任意 → cancelled | `cancel_task()` | `workforce.py:cancel_task()` | 管理员操作 | ✅ |

### 2.3 状态枚举

```
queued, approval_required, assigned, awaiting_validation,
completed, blocked, failed, cancelled, superseded
```

---

## 3. 员工反馈合同

### 3.1 事件类型

| 事件类型 | 触发时机 | 必填字段 | 代码位置 | 状态 |
|---------|---------|---------|---------|------|
| accepted | 员工领取任务 | task_id, worker_id | `workforce.py:claim()` | ✅ |
| progress | 员工报告进度 | task_id, worker_id, progress | `workforce.py:heartbeat_worker()` | ✅ |
| result | 员工提交结果 | task_id, worker_id, output, evidence | `workforce.py:report()` | ✅ |
| blocked | 员工上报阻塞 | task_id, worker_id, blocker | `workforce.py:report()` | ✅ |
| failed | 员工执行失败 | task_id, worker_id | `workforce.py:report()` | ✅ |

### 3.2 反馈字段约束

| 字段 | 类型 | 约束 | 代码位置 | 状态 |
|------|------|------|---------|------|
| task_id | string | 必填 | `workforce.py:report()` | ✅ |
| worker_id | string | 必填 | `workforce.py:report()` | ✅ |
| status | string | enum | `workforce.py:report()` | ✅ |
| output | string | ≤20000 | `workforce.py:report()` | ✅ |
| blocker | string | ≤3000 | `workforce.py:report()` | ✅ |
| evidence | array | 可选（阶段二） | `workforce.py:report()` | ✅ |
| provenance | object | 可选（阶段二） | `workforce.py:report()` | ✅ |
| timestamp | string | ISO 8601 | `workforce.py:_stamp()` | ✅ |

---

## 4. 可靠性要求

### 4.1 持久化

| 要求 | 代码位置 | 状态 |
|------|---------|------|
| 任务持久化到 JSON 文件 | `workforce.py:save()` | ✅ |
| 事件追加到 history 数组 | `workforce.py:_event()` | ✅ |
| 重启不丢失 | `workforce.py:load()` | ✅ |

### 4.2 租约令牌（Fencing Token）

| 要求 | 代码位置 | 状态 |
|------|------|------|
| 每个任务分配唯一 lease_token | `workforce.py:claim()` | ✅ |
| 报告时必须携带有效 lease_token | `workforce.py:report()` | ✅ |
| 过期租约自动回收 | `workforce.py:maintain()` | ✅ |
| 过期结果被拒绝 | `workforce.py:report()` lease_token 检查 | ✅ |

### 4.3 重试策略

| 要求 | 代码位置 | 状态 |
|------|------|------|
| 重试有界（max_attempts） | `workforce.py:retry_task()` | ✅ |
| 幂等重试 | `workforce.py:retry_task()` | ✅ |
| 重试前必须解决阻塞 | `workforce.py:retry_task()` | ✅ |

### 4.4 安全要求

| 要求 | 代码位置 | 状态 |
|------|------|------|
| 凭证不出任务载荷 | `workforce.py:report()` 不记录 token | ✅ |
| 能力边界检查 | `workforce.py:claim()` capability 匹配 | ✅ |
| 不可逆动作前审批 | `workforce.py:approve_task()` | ✅ |
| 模型置信度不替代证据 | `server.py:_audit_worker_result()` | ✅ |

### 4.5 可观测性

| 要求 | 代码位置 | 状态 |
|------|------|------|
| 暴露队列年龄 | `server.py:/api/state` supervision.age_seconds | ✅ |
| 暴露重试计数 | `workforce.py:snapshot()` counts | ✅ |
| 暴露阻塞任务 | `server.py:/api/state` supervision.status | ✅ |
| 暴露最后心跳 | `workforce.py:snapshot()` workers | ✅ |
| 暴露健康状态 | `server.py:/api/llm/status`, `/api/research/status` | ✅ |

---

## 5. 验收测试清单

| # | 测试项 | 测试位置 | 状态 |
|---|--------|---------|------|
| 1 | 分身创建任务，出现在持久队列 | `test_workforce_api_integration.py` | ✅ |
| 2 | 员工领取，状态变为 assigned | `test_workforce_api_integration.py` | ✅ |
| 3 | 员工报告进度，事件可见 | `test_workforce_api_integration.py` | ✅ |
| 4 | 员工提交结果，状态变为 awaiting_validation | `test_workforce.py` | ✅ |
| 5 | 员工上报阻塞，orchestrator 暴露阻塞 | `test_workforce.py` | ✅ |
| 6 | 未确认领取的员工可被重新分配 | `test_workforce.py` | ✅ |
| 7 | 重试失败任务不超过 max_attempts | `test_workforce.py` | ✅ |
| 8 | 审批门控：未审批前任务不执行 | `test_workforce.py` | ✅ |
| 9 | 重启服务不丢失任务 | `test_workforce.py` | ✅ |
| 10 | `/api/llm/status` 和健康检查可用 | `test_llm_worker.py` | ✅ |

---

## 规约版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.7.1 | 2026-10-26 | 新增证据链相关职责（§1.1 分身综合结果含证据论证） |
| 0.7.0 | 2026-10-26 | 初始规约 |
