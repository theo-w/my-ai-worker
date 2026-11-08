# 追溯矩阵（Traceability Matrix）

> **自动生成：** 此文件由 `scripts/verify_sdd.py` 生成。
> **最后更新：** 2026-11-08
> **规约目录：** [specs/](./)

## API 规约追溯

| 规约条目 | 规约文档 | 代码位置 | 状态 |
|---------|---------|---------|------|
| GET /api/workforce | api-contract.md#/api/workforce_get | — | ✅ |
| POST /api/workforce/tasks | api-contract.md#/api/workforce/tasks_post | — | ✅ |
| POST /api/workforce/claim | api-contract.md#/api/workforce/claim_post | — | ✅ |
| POST /api/workforce/report | api-contract.md#/api/workforce/report_post | — | ✅ |
| POST /api/workforce/verify | api-contract.md#/api/workforce/verify_post | — | ✅ |
| POST /api/workforce/retry | api-contract.md#/api/workforce/retry_post | — | ✅ |
| POST /api/workforce/cancel | api-contract.md#/api/workforce/cancel_post | — | ✅ |
| POST /api/workforce/merge | api-contract.md#/api/workforce/merge_post | — | ✅ |
| POST /api/workforce/feedback | api-contract.md#/api/workforce/feedback_post | — | ✅ |
| POST /api/workforce/approve | api-contract.md#/api/workforce/approve_post | — | ✅ |
| POST /api/workforce/maintain | api-contract.md#/api/workforce/maintain_post | — | ✅ |
| POST /api/twin/goal | api-contract.md#/api/twin/goal_post | — | ✅ |
| POST /api/twin/review | api-contract.md#/api/twin/review_post | — | ✅ |
| POST /api/twin/advance | api-contract.md#/api/twin/advance_post | — | ✅ |
| POST /api/workers/heartbeat | api-contract.md#/api/workers/heartbeat_post | — | ✅ |
| GET /api/llm/status | api-contract.md#/api/llm/status_get | — | ✅ |
| POST /api/llm/smoke-test | api-contract.md#/api/llm/smoke-test_post | — | ✅ |
| GET /api/research/status | api-contract.md#/api/research/status_get | — | ✅ |
| POST /api/research | api-contract.md#/api/research_post | — | ✅ |
| GET /api/state | api-contract.md#/api/state_get | — | ✅ |
| GET /api/history | api-contract.md#/api/history_get | — | ✅ |
| GET /api/knowledge | api-contract.md#/api/knowledge_get | — | ✅ |
| POST /api/knowledge/search | api-contract.md#/api/knowledge/search_post | — | ✅ |
| GET /api/feasibility | api-contract.md#/api/feasibility_get | — | ✅ |
| GET /api/improvement/report | api-contract.md#/api/improvement/report_get | — | ✅ |
| GET / | api-contract.md#/_get | — | ✅ |
| GET /trace | api-contract.md#/trace_get | — | ✅ |
| GET /playtest | api-contract.md#/playtest_get | — | ✅ |

## 数据模型追溯

| 规约条目 | 规约文档 | 代码位置 | 状态 |
|---------|---------|---------|------|
| EvidenceItem.source_url 存在 | data-models.md#4-evidenceitem | — | ✅ |
| EvidenceItem.source_url HTTPS 校验 | data-models.md#4-evidenceitem | — | ✅ |
| TwinDecision.evidence_ids 存在 | data-models.md#9-twindecision | — | ✅ |
| TwinDecision.ignored_evidence 存在 | data-models.md#9-twindecision | — | ✅ |
| TwinDecision.uncertainty 存在 | data-models.md#9-twindecision | — | ✅ |

## 协议规约追溯

| 规约条目 | 规约文档 | 代码位置 | 状态 |
|---------|---------|---------|------|
| 状态 queued 在代码中存在 | protocol.md#2-任务生命周期状态机 | — | ✅ |
| 状态 approval_required 在代码中存在 | protocol.md#2-任务生命周期状态机 | — | ✅ |
| 状态 assigned 在代码中存在 | protocol.md#2-任务生命周期状态机 | — | ✅ |
| 状态 awaiting_validation 在代码中存在 | protocol.md#2-任务生命周期状态机 | — | ✅ |
| 状态 completed 在代码中存在 | protocol.md#2-任务生命周期状态机 | — | ✅ |
| 状态 blocked 在代码中存在 | protocol.md#2-任务生命周期状态机 | — | ✅ |
| 状态 failed 在代码中存在 | protocol.md#2-任务生命周期状态机 | — | ✅ |
| 状态 cancelled 在代码中存在 | protocol.md#2-任务生命周期状态机 | — | ✅ |
| 状态 superseded 在代码中存在 | protocol.md#2-任务生命周期状态机 | — | ✅ |
| 租约令牌分配 | protocol.md#42-租约令牌fencing-token | — | ✅ |
| 租约令牌校验 | protocol.md#42-租约令牌fencing-token | — | ✅ |
| max_attempts 字段 | protocol.md#43-重试策略 | — | ✅ |
| attempts < max_attempts 检查 | protocol.md#43-重试策略 | — | ✅ |

## 证据链规约追溯

| 规约条目 | 规约文档 | 代码位置 | 状态 |
|---------|---------|---------|------|
| _assess_source_reliability() 存在 | evidence-chain.md#3-来源可靠性评级规则 | — | ✅ |
| _check_evidence_traceability() 存在 | evidence-chain.md#4-可追溯性检查规则 | — | ✅ |
| _audit_worker_result() 存在 | evidence-chain.md#5-分身审计流程 | — | ✅ |
| verdict: SIMULATION_ONLY | evidence-chain.md#5-分身审计流程 | — | ✅ |
| verdict: TRACEABLE_BUT_UNVERIFIED | evidence-chain.md#5-分身审计流程 | — | ✅ |
| verdict: NEEDS_INDEPENDENT_EVIDENCE | evidence-chain.md#5-分身审计流程 | — | ✅ |
| report() 含 evidence 参数 | evidence-chain.md#11-证据项字段规约 | — | ✅ |
| confidence 校验 | evidence-chain.md#11-证据项字段规约 | — | ✅ |
| simulated 校验 | evidence-chain.md#11-证据项字段规约 | — | ✅ |

## 统计摘要

| 类别 | 总条目 | ✅ | ❌ |
|------|--------|----|----|
| API 规约 | 28 | 28 | 0 |
| 数据模型 | 5 | 5 | 0 |
| 协议规约 | 13 | 13 | 0 |
| 证据链规约 | 9 | 9 | 0 |

| **合计** | **55** | **55** | **0** |

