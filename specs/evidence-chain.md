# 证据链规约（Evidence Chain Spec）

> **版本：** 0.7.1
> **最后更新：** 2026-10-26
> **来源：** 从 `docs/DIGITAL_WORKFORCE_PROTOCOL.md` §2.5 和 `docs/schemas/evidence.json` 提取。
> **引用：** [证据链 JSON Schema](../docs/schemas/evidence.json), [分身决策 JSON Schema](../docs/schemas/twin-decision.json)
> **追溯：** [SPEC_TRACEABILITY.md](../docs/SPEC_TRACEABILITY.md)

## 图例

| 符号 | 含义 |
|------|------|
| ✅ | 代码已实现，测试已覆盖 |
| ⚠️ | 代码已实现，测试不完整 |
| 🔲 | 规约已定义，代码未实现 |

---

## 1. 六条证据链原则（强制约束）

### 1.1 可追溯性（Traceability）

每个员工提交的结论必须附带来源 URL、来源标题、原始摘录（excerpt）。没有来源的结论标记为 `untraceable`，不得作为决策依据。

| 要求 | 代码位置 | 状态 |
|------|---------|------|
| 员工提交结果时附带 evidence 数组 | `workforce.py:report()` evidence 参数 | ✅ |
| 每项证据必须含 source_url | `workforce.py:report()` 校验 | ✅ |
| 无来源结论标记为 untraceable | `server.py:_check_evidence_traceability()` | ✅ |

### 1.2 原始数据客观性（Objectivity）

员工不得用自己的语言转述替代原始数据。所有引用必须保留原始摘录，并标注来源类型（一手数据/二手分析/媒体报道/用户评论）。转述仅可作为辅助说明，不能替代原文。

| 要求 | 代码位置 | 状态 |
|------|---------|------|
| evidence 含 excerpt 字段 | `docs/schemas/evidence.json` | ✅ |
| evidence 含 source_type 枚举 | `docs/schemas/evidence.json` | ✅ |
| 代码不自动转述原始数据 | `mvp/research.py` 保留 snippet | ✅ |

### 1.3 来源可靠性论证（Source Reliability）

分身收到员工结果后，必须检查：
- 来源 URL 是否可访问（HTTPS）
- 来源类型是否支持该结论
- 来源发布时间是否在合理范围内
- 是否存在对立来源（counter-source）

| 要求 | 代码位置 | 状态 |
|------|---------|------|
| HTTPS 检查 | `workforce.py:report()` `url.startswith("https://")` | ✅ |
| 来源类型检查 | `docs/schemas/evidence.json` source_type enum | ✅ |
| 模拟输出检查 | `workforce.py:report()` simulated 校验 | ✅ |
| 来源可靠性评级 | `server.py:_assess_source_reliability()` | ✅ |
| 对立来源检测 | 🔲 | 🔲 |

### 1.4 依据可溯源（Evidence Traceability）

分身的每个决策必须记录：
- 决策依据的证据 ID 列表
- 被忽略的证据及其原因
- 不确定性声明（哪些结论缺乏足够证据）

| 要求 | 代码位置 | 状态 |
|------|---------|------|
| TwinDecision 含 evidence_ids | `docs/schemas/twin-decision.json` | ✅ |
| TwinDecision 含 ignored_evidence | `docs/schemas/twin-decision.json` | ✅ |
| TwinDecision 含 uncertainty | `docs/schemas/twin-decision.json` | ✅ |
| record_twin_decision() 写入上述字段 | `workforce.py:record_twin_decision()` | ⚠️ |
| 输出 URL 与证据来源匹配 | `server.py:_check_evidence_traceability()` | ✅ |

### 1.5 不可伪造性（Non-repudiation）

员工提交的结果一旦进入 `awaiting_validation` 状态，不得被员工自行修改。只有管理员或分身策略可以触发修订。

| 要求 | 代码位置 | 状态 |
|------|---------|------|
| awaiting_validation 状态员工不可修改 | `workforce.py:report()` 状态检查 | ✅ |
| 修订需管理员触发 | `workforce.py:retry_task()` | ✅ |
| 租约令牌防覆盖 | `workforce.py:report()` lease_token 检查 | ✅ |

### 1.6 模拟与真实标注（Simulation Labeling）

所有输出必须标注 `simulated: true/false`。模拟输出不得进入证据链，不得作为任何决策的依据。

| 要求 | 代码位置 | 状态 |
|------|---------|------|
| evidence 含 simulated 字段 | `docs/schemas/evidence.json` | ✅ |
| 模拟输出标记为 unreliable | `server.py:_assess_source_reliability()` | ✅ |
| 模拟输出 verdict = SIMULATION_ONLY | `server.py:_audit_worker_result()` | ✅ |

---

## 2. 证据项字段规约

### 2.1 必填字段

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| source_url | string | 必须 `https://` 开头 | 来源 URL |

### 2.2 可选字段

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| source_title | string | ≤500 字符 | 来源标题 |
| excerpt | string | ≤5000 字符 | 原始摘录 |
| source_type | string | enum: primary, secondary, media, user_review | 来源类型 |
| confidence | number | 0.0-1.0 | 证据置信度 |
| simulated | boolean | 默认 false | 是否模拟输出 |
| provider | string | - | 来源提供商 |
| source_role | string | - | 来源角色 |
| evidence_use | string | - | 证据用途 |
| evidence_use_label | string | - | 证据用途标签 |
| evidence_use_reason | string | - | 证据用途说明 |

---

## 3. 来源可靠性评级规则

| 条件 | 评级 | 说明 | 代码位置 | 状态 |
|------|------|------|---------|------|
| HTTPS URL + 非模拟 + 有来源类型 | reliable | 可信来源 | `server.py:_assess_source_reliability()` | ✅ |
| HTTPS URL + 非模拟 + 无来源类型 | questionable | 需人工复核 | `server.py:_assess_source_reliability()` | ✅ |
| HTTP URL | unreliable | 非加密连接 | `server.py:_assess_source_reliability()` | ✅ |
| simulated=true | unreliable | 模拟输出 | `server.py:_assess_source_reliability()` | ✅ |
| 无 source_url | unreliable | 无来源 | `server.py:_assess_source_reliability()` | ✅ |

---

## 4. 可追溯性检查规则

### 4.1 输出 URL 与证据来源匹配

| 规则 | 说明 | 代码位置 | 状态 |
|------|------|---------|------|
| 输出中的每个 URL 必须在证据来源中找到 | structural_traceability=true | `server.py:_check_evidence_traceability()` | ✅ |
| 输出中的 URL 在证据中找不到 | structural_traceability=false | `server.py:_check_evidence_traceability()` | ✅ |
| 输出无 URL，证据有 URL | 记录 counts，不标记失败 | `server.py:_check_evidence_traceability()` | ✅ |

---

## 5. 分身审计流程

### 5.1 审计步骤

```
员工提交结果
    │
    ▼
1. 确定性初筛（已有）
   - 检查 simulated 字段
   - 检查 evidence 结构
   │
   ▼
2. 来源可靠性论证（新增）
   - _assess_source_reliability(evidence)
   - 返回 reliable / questionable / unreliable 列表
   │
   ▼
3. 依据可溯源检查（新增）
   - _check_evidence_traceability(output, evidence)
   - 返回 structural_traceability / matched_urls / unmatched_urls
   │
   ▼
4. 综合审计结果
   - _audit_worker_result(output, result_data, evidence)
   - 返回 verdict + source_reliability + traceability
```

### 5.2 审计 verdict

| 条件 | verdict | 说明 | 代码位置 | 状态 |
|------|---------|------|---------|------|
| simulated=true | SIMULATION_ONLY | 模拟输出，不进入证据链 | `server.py:_audit_worker_result()` | ✅ |
| 有证据 + URL 匹配 | TRACEABLE_BUT_UNVERIFIED | 可追溯但未验证 | `server.py:_audit_worker_result()` | ✅ |
| 无证据 | NEEDS_INDEPENDENT_EVIDENCE | 需要独立证据 | `server.py:_audit_worker_result()` | ✅ |

---

## 规约版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.7.1 | 2026-10-26 | 初始规约，六条原则 + 评级规则 + 审计流程 |
