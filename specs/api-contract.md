# API 规约（API Contract Spec）

> **版本：** 0.7.1
> **最后更新：** 2026-10-26
> **来源：** 从 `docs/api/openapi.yaml` 提取，保留关键约束，完整定义引用 OpenAPI 文件。
> **引用：** [OpenAPI 3.0 完整规范](../docs/api/openapi.yaml)
> **追溯：** [SPEC_TRACEABILITY.md](../docs/SPEC_TRACEABILITY.md)

## 图例

| 符号 | 含义 |
|------|------|
| ✅ | 代码已实现，测试已覆盖 |
| ⚠️ | 代码已实现，测试不完整 |
| 🔲 | 规约已定义，代码未实现 |

## 认证说明

| 角色 | Token 配置 | 说明 |
|------|-----------|------|
| admin | `JARVIS_ADMIN_TOKEN` | 管理员，可创建/审批/取消/合并任务 |
| worker | `JARVIS_WORKER_TOKENS` | 员工，可领取/报告/心跳 |
| dashboard | `JARVIS_ADMIN_TOKEN` | Dashboard 页面，可读状态 |
| none | 无 | 公开端点 |

---

## 1. Workforce API

### 1.1 GET /api/workforce

- **认证：** admin
- **描述：** 获取全量队列快照（任务、员工、事件）
- **协议：** DIGITAL_WORKFORCE_PROTOCOL.md §3
- **代码：** `server.py:1069`
- **状态：** ✅

**响应 200：**
| 字段 | 类型 | 说明 |
|------|------|------|
| ok | boolean | 始终 true |
| counts | object | 任务计数分组 |
| tasks | array | 任务列表（schema 见 [task.json](../docs/schemas/task.json)） |
| events | array | 事件列表（schema 见 [event-record.json](../docs/schemas/event-record.json)） |
| workers | array | 员工列表（schema 见 [worker-info.json](../docs/schemas/worker-info.json)） |
| lease_seconds | integer | 租约时长（秒） |

---

### 1.2 POST /api/workforce/tasks

- **认证：** admin
- **描述：** 创建新任务
- **协议：** DIGITAL_WORKFORCE_PROTOCOL.md §4
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**请求体：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| title | string | 是 | ≤200 字符 |
| description | string | 否 | ≤5000 字符，默认 "" |
| capability | string | 否 | ≤100 字符，默认 "general" |
| priority | integer | 否 | 1-5，默认 3 |
| assigned_to | string | 否 | null 允许 |
| approval_required | boolean | 否 | 默认 false |
| success_criteria | object | 否 | ≤4000 字符 |
| evidence_required | boolean | 否 | 默认 false |

**响应 201：** Task（完整 schema 见 [task.json](../docs/schemas/task.json)）

---

### 1.3 POST /api/workforce/claim

- **认证：** worker
- **描述：** 员工领取任务（能力匹配）
- **协议：** DIGITAL_WORKFORCE_PROTOCOL.md §3
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**请求体：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| capabilities | array | 是 | 员工能力列表 |
| task_id | string | 否 | null 允许，指定领取特定任务 |

**响应 200：** TaskClaim（Task + lease_token）

---

### 1.4 POST /api/workforce/report

- **认证：** worker
- **描述：** 员工提交结果或阻塞
- **协议：** DIGITAL_WORKFORCE_PROTOCOL.md §4, §2.5（阶段二）
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**请求体：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| task_id | string | 是 | 任务 ID |
| status | string | 是 | enum: completed, blocked, failed, in_progress |
| lease_token | string | 是 | 租约令牌 |
| output | string | 否 | ≤20000 字符，默认 "" |
| blocker | string | 否 | ≤3000 字符，status=blocked 时必填 |
| evidence | array | 否 | 每项含 `source_url`（必须 HTTPS） |
| provenance | object | 否 | 含 `executor_type`（enum: simulated, llm, live_search） |

**证据项字段：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| source_url | string | 是 | 必须 `https://` 开头 |
| source_title | string | 否 | ≤500 字符 |
| excerpt | string | 否 | ≤5000 字符 |
| source_type | string | 否 | enum: primary, secondary, media, user_review |
| confidence | number | 否 | 0.0-1.0 |
| simulated | boolean | 否 | 默认 false |

**响应 200：** Task（完整 schema 见 [task.json](../docs/schemas/task.json)）

---

### 1.5 POST /api/workforce/verify

- **认证：** admin
- **描述：** 记录验证结果
- **协议：** DIGITAL_WORKFORCE_PROTOCOL.md §5.1, §2.5（阶段二）
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**请求体：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| task_id | string | 是 | 任务 ID |
| verification | object | 是 | Verification schema（[verification.json](../docs/schemas/verification.json)） |

**注意：** `verification.verified_truth` 始终为 false。结构检查通过不等于事实证明。

---

### 1.6 POST /api/workforce/retry

- **认证：** admin
- **描述：** 重试阻塞/失败任务
- **协议：** DIGITAL_WORKFORCE_PROTOCOL.md §3
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**请求体：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| task_id | string | 是 | 任务 ID |
| reason | string | 是 | ≤1000 字符 |

**前置条件：** 任务状态为 blocked 或 failed，且 `attempts < max_attempts`。

---

### 1.7 POST /api/workforce/cancel

- **认证：** admin
- **描述：** 取消任务
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**请求体：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| task_id | string | 是 | 任务 ID |
| reason | string | 是 | ≤1000 字符 |

---

### 1.8 POST /api/workforce/merge

- **认证：** admin
- **描述：** 合并重复任务
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**请求体：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| target_task_id | string | 是 | 目标任务 ID |
| source_task_ids | array | 是 | ≤20 个任务 ID |
| reason | string | 是 | ≤1000 字符 |

---

### 1.9 POST /api/workforce/feedback

- **认证：** admin
- **描述：** 提交反馈
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**请求体：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| task_id | string | 是 | 任务 ID |
| actor | string | 是 | ≤120 字符 |
| message | string | 是 | ≤5000 字符 |
| kind | string | 否 | enum: note, question, correction, approval_request，默认 "note" |

---

### 1.10 POST /api/workforce/approve

- **认证：** admin
- **描述：** 审批待审任务
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**请求体：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| task_id | string | 是 | 任务 ID |

---

### 1.11 POST /api/workforce/maintain

- **认证：** admin
- **描述：** 租约维护（回收过期租约）
- **协议：** DIGITAL_WORKFORCE_PROTOCOL.md §5
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**响应 200：**
| 字段 | 类型 | 说明 |
|------|------|------|
| requeued | array | 重新入队的任务 ID 列表 |
| failed | array | 标记失败的任务 ID 列表 |

---

## 2. Digital Twin API

### 2.1 POST /api/twin/goal

- **认证：** admin
- **描述：** 向分身提交目标
- **协议：** DIGITAL_WORKFORCE_PROTOCOL.md §2
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**请求体：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| goal | string | 是 | ≤4000 字符 |
| strategy | string | 否 | enum: single_agent, decompose，默认 "single_agent" |
| template | string | 否 | enum: general, ai_game_feasibility，默认 "general" |
| capability | string | 否 | ≤100 字符 |

**响应 201：** 包含 project_id, goal, strategy, template, tasks（Task 数组）, next_step

---

### 2.2 POST /api/twin/review

- **认证：** admin
- **描述：** 分身复核项目状态
- **协议：** DIGITAL_WORKFORCE_PROTOCOL.md §2
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**请求体：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| project_id | string | 是 | ≤80 字符 |

**响应 200：** 包含 decision（enum: replan_required, awaiting_independent_validation, continue_monitoring, goal_completed, needs_twin_review）, reason, task_count, status_counts, next_actions, llm_used, safety_note

---

### 2.3 POST /api/twin/advance

- **认证：** admin
- **描述：** 分身推进（有界确定性重试）
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**请求体：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| project_id | string | 是 | ≤80 字符 |

**响应 200：** 包含 decision, reason, task_count, next_actions, action_task_id, llm_used, safety_note

---

## 3. Worker API

### 3.1 POST /api/workers/heartbeat

- **认证：** worker
- **描述：** 员工心跳
- **协议：** DIGITAL_WORKFORCE_PROTOCOL.md §5
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**请求体：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| status | string | 是 | enum: idle, working, waiting_tool, blocked |
| current_task_id | string | 否 | null 允许 |
| lease_token | string | 否 | null 允许 |
| progress | string | 否 | ≤500 字符 |
| last_error | string | 否 | ≤1000 字符 |

---

## 4. LLM API

### 4.1 GET /api/llm/status

- **认证：** none（公开）
- **描述：** LLM 配置状态
- **代码：** `server.py:1174`
- **状态：** ✅

**响应 200：**
| 字段 | 类型 | 说明 |
|------|------|------|
| configured | boolean | LLM 是否已配置 |
| mode | string | simulated / hybrid / llm / search_only |
| model | string | 模型 ID |
| missing_llm_variables | array | 缺失的环境变量 |
| truth_policy | object | 真理策略（llm_output_is_verified=false） |

---

### 4.2 POST /api/llm/smoke-test

- **认证：** admin
- **描述：** LLM 连通测试（64-token 限制）
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**响应 200：**
| 字段 | 类型 | 说明 |
|------|------|------|
| ok | boolean | 是否连通 |
| status | string | connected / unexpected_response |
| model | string | 模型 ID |
| elapsed_ms | integer | 耗时（毫秒） |
| max_tokens | integer | 64 |
| marker_matched | boolean | 标记是否匹配 |

---

## 5. Research API

### 5.1 GET /api/research/status

- **认证：** none（公开）
- **描述：** 搜索配置状态
- **代码：** `server.py:1146`
- **状态：** ✅

**响应 200：**
| 字段 | 类型 | 说明 |
|------|------|------|
| configured | boolean | 搜索是否已配置 |
| provider | string | 提供商名称 |
| endpoint | string | 端点 URL（脱敏） |

---

### 5.2 POST /api/research

- **认证：** admin
- **描述：** 执行搜索
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**请求体：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| query | string | 是 | ≤2000 字符 |
| limit | integer | 否 | 1-20，默认 5 |

**响应 200：**
| 字段 | 类型 | 说明 |
|------|------|------|
| ok | boolean | 是否成功 |
| sources | array | SourceRecord 数组 |
| evidence | array | EvidenceItem 数组 |
| quality | object | 质量评估 |
| synthesis | string | 综合结果 |
| error | string | 错误信息（如有） |

---

## 6. State & History API

### 6.1 GET /api/state

- **认证：** admin
- **描述：** 运行状态快照
- **代码：** `server.py:1097`
- **状态：** ✅

**响应 200：**
| 字段 | 类型 | 说明 |
|------|------|------|
| goal | string | 当前目标 |
| phase | string | 当前阶段 |
| agents | array | 代理列表 |
| evidence | array | 证据列表 |
| decision | object | 当前决策 |
| feasibility | object | 可行性评估 |
| knowledge | object | 知识库摘要 |
| research | object | 调研状态 |
| supervision | object | 监督信息 |
| run_id | string | 运行 ID |
| supervision | object | 监督状态（attention_required/monitoring/blocked/terminal_or_idle） |

---

### 6.2 GET /api/history

- **认证：** admin
- **描述：** 运行历史（最多 50 条）
- **代码：** `server.py:1077`
- **状态：** ✅

**响应 200：**
| 字段 | 类型 | 说明 |
|------|------|------|
| count | integer | 总记录数 |
| runs | array | 运行记录数组（最多 50 条） |

---

## 7. Knowledge API

### 7.1 GET /api/knowledge

- **认证：** admin
- **描述：** 知识库摘要
- **代码：** `server.py:1128`
- **状态：** ✅

**响应 200：**
| 字段 | 类型 | 说明 |
|------|------|------|
| ok | boolean | 始终 true |
| knowledge | object | KnowledgeSummary（记录数 + 摘要） |

---

### 7.2 POST /api/knowledge/search

- **认证：** admin
- **描述：** 搜索知识库
- **代码：** `server.py:1217` (POST 路由)
- **状态：** ✅

**请求体：**
| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| query | string | 是 | ≤2000 字符 |

**响应 200：**
| 字段 | 类型 | 说明 |
|------|------|------|
| ok | boolean | 是否成功 |
| matches | array | 匹配结果 |

---

## 8. Feasibility API

### 8.1 GET /api/feasibility

- **认证：** admin
- **描述：** 可行性评估状态
- **代码：** `server.py:1136`
- **状态：** ✅

**响应 200：**
| 字段 | 类型 | 说明 |
|------|------|------|
| ok | boolean | 始终 true |
| feasibility | object | FeasibilityDraft（goal, contract, report, evaluation） |

---

## 9. Improvement API

### 9.1 GET /api/improvement/report

- **认证：** admin
- **描述：** 递归自我改进报告
- **代码：** `server.py:1060`
- **状态：** ✅

**响应 200：**
| 字段 | 类型 | 说明 |
|------|------|------|
| ok | boolean | 始终 true |
| report | object | ImprovementReport |

---

## 10. Pages

### 10.1 GET /

- **认证：** none（公开）
- **描述：** Dashboard 工作台
- **代码：** `server.py:1206`
- **状态：** ✅

### 10.2 GET /trace

- **认证：** none（公开）
- **描述：** 流程追踪页面
- **代码：** `server.py:1206`
- **状态：** ✅

### 10.3 GET /playtest

- **认证：** none（公开）
- **描述：** 游戏体验原型
- **代码：** `server.py:1206`
- **状态：** ✅

---

## 错误响应

所有 API 端点统一返回以下错误码：

| 状态码 | 含义 | 说明 |
|--------|------|------|
| 400 | BadRequest | 请求体格式错误、字段校验失败 |
| 401 | Unauthorized | 认证失败或 Token 缺失 |
| 403 | Forbidden | Token 有效但权限不足 |
| 404 | NotFound | 资源不存在 |
| 413 | PayloadTooLarge | 请求体超过 1MB |
| 500 | InternalError | 服务器内部错误 |
| 502 | BadGateway | 上游服务错误 |
| 503 | ServiceUnavailable | 服务不可用（无 Token 配置时 fail-closed） |

---

## 规约版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.7.1 | 2026-10-26 | 新增 evidence/provenance 字段规约（阶段二） |
| 0.7.0 | 2026-10-26 | 初始规约，28 个端点 |
