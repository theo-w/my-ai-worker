# Digital Workforce Collaboration Protocol (MVP)

## Goal

Turn JARVIS from a single-task demo into a digital-twin orchestrator that can assign work to digital employees, track progress, receive structured feedback, and decide what happens next. The first use case is AI-native game feasibility and game-operation analysis, but the protocol must remain domain-agnostic.

## Core responsibilities

- **Digital Twin / JARVIS (orchestrator):** owns the user goal, decomposes it into tasks, selects workers, sets priorities and deadlines, monitors execution, handles blockers, requests approval for consequential actions, and synthesizes results.
- **Digital Employee (worker):** accepts an assigned task, acknowledges it, reports progress, returns a structured result with evidence and limitations, and raises a blocker instead of silently failing.
- **Human operator:** sets goals and constraints, approves gated actions, and can pause, cancel, or reassign work.

## 2.5 证据链原则（强制约束）

分身与员工交互的所有结果必须满足以下证据链要求：

1. **可追溯性（Traceability）：** 每个员工提交的结论必须附带来源 URL、来源标题、原始摘录（excerpt）。没有来源的结论标记为 `untraceable`，不得作为决策依据。

2. **原始数据客观性（Objectivity）：** 员工不得用自己的语言转述替代原始数据。所有引用必须保留原始摘录，并标注来源类型（一手数据/二手分析/媒体报道/用户评论）。转述仅可作为辅助说明，不能替代原文。

3. **来源可靠性论证（Source Reliability）：** 分身收到员工结果后，必须检查：
   - 来源 URL 是否可访问（HTTPS）
   - 来源类型是否支持该结论（如：媒体报道 ≠ 一手用户数据）
   - 来源发布时间是否在合理范围内
   - 是否存在对立来源（counter-source）

4. **依据可溯源（Evidence Traceability）：** 分身的每个决策必须记录：
   - 决策依据的证据 ID 列表
   - 被忽略的证据及其原因
   - 不确定性声明（哪些结论缺乏足够证据）

5. **不可伪造性（Non-repudiation）：** 员工提交的结果一旦进入 `awaiting_validation` 状态，不得被员工自行修改。只有管理员或分身策略可以触发修订。

6. **模拟与真实的明确标注：** 所有输出必须标注 `simulated: true/false`。模拟输出不得进入证据链，不得作为任何决策的依据。

## Task lifecycle

`queued -> assigned -> accepted -> running -> succeeded | blocked | failed | cancelled`

A blocked task may return to `queued` after the orchestrator resolves the blocker. Retry policy must be bounded and idempotent. A task must not be marked `succeeded` until a result payload has been persisted.

## MVP task contract

Each task should carry:

- `task_id`: stable unique identifier
- `goal`: outcome to achieve, not just an action
- `instructions`: scope and expected steps
- `worker_type`: capability required (research, analysis, coding, QA, etc.)
- `priority`: low / normal / high / urgent
- `status`: lifecycle state above
- `created_at`, `updated_at`, `deadline_at`
- `input_refs`: URLs, files, datasets, or upstream task outputs
- `constraints`: budget, time, policy, data and tool boundaries
- `approval_required`: whether a human approval gate applies
- `attempt`, `max_attempts`: bounded retry metadata

## Worker feedback contract

Every worker update should contain:

- `task_id`, `worker_id`, `event_type` (`accepted`, `progress`, `result`, `blocked`, `failed`)
- `summary`: concise human-readable update
- `progress`: optional 0–100 estimate; never treat it as proof of completion
- `artifacts`: output references or structured result
- `evidence`: sources, test results, or observations supporting claims
- `blocker`: required when blocked
- `next_action`: proposed next step
- `needs_human_approval`: explicit approval request when applicable
- `timestamp`

## Orchestrator loop

1. Capture the user's goal and success criteria.
2. Decompose the goal into a dependency-aware task graph.
3. Assign each ready task to a compatible worker.
4. Require an acceptance event; reassign after a configurable acknowledgement timeout.
5. Consume progress, result, blocked, and failed events.
6. Validate outputs against acceptance criteria and required evidence.
7. Retry transient failures within the attempt limit; otherwise escalate.
8. Ask for human approval before external, destructive, financial, or publication actions.
9. Synthesize completed work, explain unresolved uncertainty, and propose the next task.
10. Persist the task, event history, artifacts, and final decision so work can resume after restart.

## Initial API shape (implementation target)

- `POST /tasks` — create a task
- `GET /tasks` and `GET /tasks/:id` — inspect queue and task state
- `POST /tasks/:id/accept` — worker acknowledges assignment
- `POST /tasks/:id/events` — worker posts progress/result/blocker/failure events
- `POST /tasks/:id/approve` — record human approval or rejection
- `POST /tasks/:id/retry` — explicitly requeue an eligible task
- `GET /health` — runtime health check

These endpoints are a target contract, not a claim that they are already implemented.

## Reliability and safety requirements

- Persist tasks and events; do not rely on browser memory or process memory as the source of truth.
- Use idempotency keys for task creation and worker event submission.
- Record an append-only event history for auditability.
- Enforce worker capability boundaries and least-privilege tool access.
- Never let an AI-generated confidence score replace evidence or acceptance tests.
- Require approval before irreversible or externally visible actions.
- Expose queue age, retry count, blocked tasks, last worker heartbeat, and health status.
- Keep credentials and secrets out of task payloads, logs, and repository files.

## Acceptance tests for the first vertical slice

1. Orchestrator creates a task and it appears in the persistent queue.
2. A worker claims the task and the state becomes `accepted`.
3. Worker posts progress; the event is visible in task history.
4. Worker submits a result with artifacts/evidence; the task becomes `succeeded` only after validation.
5. Worker reports a blocker; the orchestrator exposes it and proposes/requires a next action.
6. A worker that does not acknowledge before timeout can be reassigned without duplicate completion.
7. A retryable failure is retried only up to `max_attempts`.
8. An approval-gated action cannot proceed until an approval decision is recorded.
9. Restarting the service does not lose tasks or events.
10. `GET /health` and an end-to-end smoke test verify the deployed runtime.

## Delivery sequence

1. **Contract first:** agree on task states, task schema, worker events, and acceptance tests.
2. **Runnable vertical slice:** implement persistent storage, task APIs, one worker, and a minimal orchestrator loop.
3. **Observability:** add queue/worker status, timeouts, retries, and blocker escalation.
4. **Multi-worker coordination:** dependency graph, capability matching, result validation, and synthesis.
5. **Domain packs:** add AI-native game feasibility assessment, prototype planning, playtest analysis, and game-operations workflows without changing the core protocol.

## Current status

This document specifies the MVP protocol and acceptance criteria. It is design documentation only; runtime endpoints, durable storage, worker execution, and deployed end-to-end behavior must be implemented and verified separately.
