# 数据模型规约（Data Models Spec）

> **版本：** 0.7.1
> **最后更新：** 2026-10-26
> **来源：** 从 `docs/schemas/*.json` 提取，保留关键约束，完整定义引用 JSON Schema 文件。
> **引用：** [JSON Schema 目录](../docs/schemas/)
> **追溯：** [SPEC_TRACEABILITY.md](../docs/SPEC_TRACEABILITY.md)

## 图例

| 符号 | 含义 |
|------|------|
| ✅ | 代码已实现，测试已覆盖 |
| ⚠️ | 代码已实现，测试不完整 |
| 🔲 | 规约已定义，代码未实现 |

---

## 1. Task

- **完整定义：** [task.json](../docs/schemas/task.json)
- **对应代码：** `workforce.py:create_task()`, `workforce.py:report()`, `workforce.py:claim()`
- **状态：** ✅

### 必填字段

| 字段 | 类型 | 约束 |
|------|------|------|
| id | string | hex[:12]，格式 `^[a-f0-9]{12}$` |
| title | string | 1-200 字符 |
| description | string | ≤5000 字符 |
| capability | string | 1-100 字符 |
| priority | integer | 1-5 |
| status | string | enum（见下） |
| created_at | string | ISO 8601 |
| updated_at | string | ISO 8601 |

### 关键字段约束

**status 枚举值：**
`queued`, `approval_required`, `assigned`, `awaiting_validation`, `completed`, `blocked`, `failed`, `cancelled`, `superseded`

### 可选字段

| 字段 | 类型 | 约束 |
|------|------|------|
| assigned_to | string | null 允许，≤120 字符 |
| attempts | integer | ≥0 |
| max_attempts | integer | ≥1 |
| lease_until | string | null 允许，ISO 8601 |
| output | string | ≤20000 字符 |
| blocker | string | ≤3000 字符 |
| feedback | array | FeedbackItem 数组 |
| history | array | TaskHistoryEvent 数组 |
| success_criteria | object | 成功标准 |
| evidence_required | boolean | 默认 false |
| evidence | array | EvidenceItem 数组（阶段二新增） |
| provenance | object | Provenance 对象（阶段二新增） |
| verification | object | Verification 对象 |
| verified_truth | boolean | 始终为 false |
| _lease_token | string | 内部字段，不出现在 API 响应中 |

---

## 2. TaskClaim

- **完整定义：** [task.json](../docs/schemas/task.json)（Task 的扩展）
- **对应代码：** `workforce.py:claim()`
- **状态：** ✅

### 说明

TaskClaim = Task + `lease_token`（字符串，租约令牌）。`lease_token` 用于防过期结果覆盖（fencing token）。

---

## 3. Verification

- **完整定义：** [verification.json](../docs/schemas/verification.json)
- **对应代码：** `workforce.py:record_verification()`
- **状态：** ✅

### 必填字段

| 字段 | 类型 | 约束 |
|------|------|------|
| accepted | boolean | 验证是否通过 |
| status | string | 验证后的任务状态 |

### 关键字段约束

**重要：** `verified_truth` 始终为 false。结构检查通过不等于事实证明。

### 可选字段

| 字段 | 类型 | 约束 |
|------|------|------|
| checks | array | 验证检查项 |
| verified_truth | boolean | 始终 false |
| evidence_count | integer | 证据数量 |
| notes | string | 验证备注 |

---

## 4. EvidenceItem

- **完整定义：** [evidence.json](../docs/schemas/evidence.json)
- **对应代码：** `workforce.py:report()` evidence 参数
- **状态：** ✅

### 必填字段

| 字段 | 类型 | 约束 |
|------|------|------|
| source_url | string | 必须 `https://` 开头 |

### 可选字段

| 字段 | 类型 | 约束 |
|------|------|------|
| source_title | string | ≤500 字符 |
| excerpt | string | ≤5000 字符 |
| source_type | string | enum: primary, secondary, media, user_review |
| confidence | number | 0.0-1.0 |
| simulated | boolean | 默认 false |
| provider | string | 来源提供商 |
| source_role | string | 来源角色 |
| evidence_use | string | 证据用途 |
| evidence_use_label | string | 证据用途标签 |
| evidence_use_reason | string | 证据用途说明 |

---

## 5. SourceRecord

- **完整定义：** [evidence.json](../docs/schemas/evidence.json)
- **对应代码：** `mvp/research.py` 搜索结果
- **状态：** ✅

### 字段

| 字段 | 类型 | 约束 |
|------|------|------|
| title | string | 来源标题 |
| url | string | 来源 URL |
| snippet | string | 摘要片段 |
| provider | string | 提供商（如 tavily） |
| source_role | string | 来源角色 |
| evidence_use | string | 证据用途 |

---

## 6. WorkerInfo

- **完整定义：** [worker-info.json](../docs/schemas/worker-info.json)
- **对应代码：** `workforce.py:heartbeat_worker()`, `workforce.py:snapshot()`
- **状态：** ✅

### 字段

| 字段 | 类型 | 约束 |
|------|------|------|
| worker_id | string | 员工 ID |
| status | string | idle, working, waiting_tool, blocked |
| current_task_id | string | null 允许 |
| progress | string | ≤500 字符 |
| last_heartbeat_at | string | ISO 8601 |
| last_error | string | ≤1000 字符 |
| capabilities | array | 能力列表 |

---

## 7. WorkforceSnapshot

- **完整定义：** [snapshot.json](../docs/schemas/snapshot.json)
- **对应代码：** `workforce.py:snapshot()`
- **状态：** ✅

### 字段

| 字段 | 类型 | 约束 |
|------|------|------|
| counts | object | 任务计数分组 |
| tasks | array | Task 数组 |
| events | array | EventRecord 数组 |
| workers | array | WorkerInfo 数组 |
| lease_seconds | integer | 租约时长 |

---

## 8. EventRecord

- **完整定义：** [event-record.json](../docs/schemas/event-record.json)
- **对应代码：** `workforce.py:_event()`
- **状态：** ✅

### 字段

| 字段 | 类型 | 约束 |
|------|------|------|
| type | string | 事件类型 |
| at | string | ISO 8601 |
| details | object | 事件详情 |

---

## 9. TwinDecision

- **完整定义：** [twin-decision.json](../docs/schemas/twin-decision.json)
- **对应代码：** `workforce.py:record_twin_decision()`
- **状态：** ✅

### 必填字段

| 字段 | 类型 | 约束 |
|------|------|------|
| goal | string | 1-2000 字符 |
| decision | string | 1-100 字符 |
| reason | string | ≤1000 字符 |

### 阶段二新增字段（证据链）

| 字段 | 类型 | 约束 |
|------|------|------|
| evidence_ids | array | 决策依据的证据 ID 列表 |
| ignored_evidence | array | 被忽略的证据及原因 |
| uncertainty | string | 不确定性声明 |

### 可选字段

| 字段 | 类型 | 约束 |
|------|------|------|
| llm_used | boolean | 是否使用 LLM |
| task_id | string | null 允许 |

---

## 10. FeedbackItem

- **完整定义：** [feedback-item.json](../docs/schemas/feedback-item.json)
- **对应代码：** `workforce.py:feedback()`
- **状态：** ✅

### 字段

| 字段 | 类型 | 约束 |
|------|------|------|
| actor | string | ≤120 字符 |
| message | string | ≤5000 字符 |
| kind | string | note, question, correction, approval_request |
| at | string | ISO 8601 |

---

## 11. TaskHistoryEvent

- **完整定义：** [task-history-event.json](../docs/schemas/task-history-event.json)
- **对应代码：** `workforce.py:report()` history 追加
- **状态：** ✅

### 字段

| 字段 | 类型 | 约束 |
|------|------|------|
| event | string | 事件类型 |
| worker_id | string | 员工 ID |
| status | string | 状态 |
| at | string | ISO 8601 |
| blocker | string | 阻塞原因 |

---

## 12. DesignBrief

- **完整定义：** 无独立 schema 文件
- **对应代码：** `mvp/experience_design.py`
- **状态：** ✅

### 字段

| 字段 | 类型 | 约束 |
|------|------|------|
| concept_name | string | 概念名称 |
| source_game | string | 源游戏 |
| trust | boolean | 信任度 |
| market_validated | boolean | 市场已验证 |
| playtested | boolean | 已试玩 |

---

## 13. FeasibilityDraft

- **完整定义：** 无独立 schema 文件
- **对应代码：** `mvp/commercial_feasibility.py`
- **状态：** ✅

### 字段

| 字段 | 类型 | 约束 |
|------|------|------|
| goal | string | 目标 |
| contract | string | 合同 |
| report | string | 报告 |
| evaluation | object | 评估结果 |

---

## 14. KnowledgeSummary

- **完整定义：** 无独立 schema 文件
- **对应代码：** `mvp/game_knowledge.py`
- **状态：** ✅

### 字段

| 字段 | 类型 | 约束 |
|------|------|------|
| total_records | integer | 总记录数 |
| summary | string | 摘要 |

---

## 15. LLMStatus

- **完整定义：** 无独立 schema 文件
- **对应代码：** `server.py:1174`
- **状态：** ✅

### 字段

| 字段 | 类型 | 约束 |
|------|------|------|
| configured | boolean | LLM 是否已配置 |
| mode | string | simulated / hybrid / llm / search_only |
| model | string | 模型 ID |
| missing_llm_variables | array | 缺失环境变量 |
| truth_policy | object | 真理策略 |

---

## 16. ResearchStatus

- **完整定义：** 无独立 schema 文件
- **对应代码：** `mvp/research.py`
- **状态：** ✅

### 字段

| 字段 | 类型 | 约束 |
|------|------|------|
| configured | boolean | 搜索是否已配置 |
| provider | string | 提供商 |
| endpoint | string | 端点 URL |

---

## 17. ImprovementReport

- **完整定义：** 无独立 schema 文件
- **对应代码：** `mvp/improvement.py`
- **状态：** ✅

### 字段

| 字段 | 类型 | 约束 |
|------|------|------|
| total_runs | integer | 总运行数 |
| success_rate | number | 成功率 |
| recommendations | array | 改进建议 |

---

## 18. ApiResponse（通用包装）

- **完整定义：** [openapi.yaml](../docs/api/openapi.yaml)
- **对应代码：** `server.py:_json()`
- **状态：** ✅

### 字段

| 字段 | 类型 | 约束 |
|------|------|------|
| ok | boolean | 是否成功 |
| [data] | object | 业务数据（因端点而异） |

---

## 19. ErrorResponse（通用错误）

- **完整定义：** [openapi.yaml](../docs/api/openapi.yaml)
- **对应代码：** `server.py:do_POST/GET` 错误处理
- **状态：** ✅

### 字段

| 字段 | 类型 | 约束 |
|------|------|------|
| ok | boolean | 始终 false |
| error | string | 错误信息 |

---

## 规约版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.7.1 | 2026-10-26 | 新增 EvidenceItem、TwinDecision 阶段二字段规约 |
| 0.7.0 | 2026-10-26 | 初始规约，14 个数据模型 |
