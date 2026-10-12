# My AI Worker

JARVIS Digital Employee Runtime — the runtime foundation for a domain-agnostic AI Workforce OS.

## Project direction

Build a digital-twin orchestrator that decomposes goals, assigns tasks to capable digital employees, tracks execution, receives structured feedback, validates results, resolves blockers, and resumes work reliably.

The first domain pack is AI-native game feasibility and game-operations analysis. The core protocol remains reusable across domains.

## Current repository status

- JARVIS game-operation copilot demo: `demo/JARVIS_AI_Game_Operation_Copilot_V4.html`.
- Task lifecycle and worker feedback contract: [Digital Workforce Protocol](docs/DIGITAL_WORKFORCE_PROTOCOL.md).
- Node.js HTTP runtime: `src/server.js`, with task APIs, worker feedback, approval gates, retries, and health endpoint.
- Bearer-token authentication and role-based access control are now implemented. Configure separate `JARVIS_ADMIN_TOKEN` and `JARVIS_WORKER_TOKEN` secrets. The worker identity is configured with `JARVIS_WORKER_ID`.
- `GET /health` is public for deployment probes. All task routes require `Authorization: Bearer <token>`.
- Admin can create tasks, inspect tasks, retry tasks, and approve/reject approval-gated results. Worker credentials can inspect available/assigned tasks, accept work only as their configured identity, and post events only for tasks assigned to that identity.
- CI tests cover missing/invalid credentials, role boundaries, approval gating, and task lifecycle. Verify the latest GitHub Actions run before considering this revision fully tested.
- **Security limitations:** this MVP uses long-lived bearer secrets, not individual user accounts, SSO, or short-lived sessions. Store secrets in the hosting provider's secret manager; never commit tokens. Use HTTPS in production. Worker tokens are shared within the configured worker identity and should later become per-worker credentials. Rate limiting, rotation workflow, and a production database remain future work.
- **Not yet complete:** autonomous scheduling, LLM-powered worker execution, acknowledgement-timeout reassignment, multi-worker dependency orchestration, and verified deployment. Authentication does not by itself make public deployment production-ready.

## Configure and run locally

Requires Node.js 20 or later. Set secrets in your shell or deployment secret manager; do not put real tokens in source control.

```bash
export JARVIS_ADMIN_TOKEN='replace-with-a-long-random-admin-secret'
export JARVIS_WORKER_TOKEN='replace-with-a-different-long-random-worker-secret'
export JARVIS_WORKER_ID='worker-1'
npm test
npm start
```

The server listens on `0.0.0.0:10000` by default. Override `PORT` and `JARVIS_STORE_PATH` as needed. Requests to task APIs must include the relevant bearer token. If tokens are not configured, task APIs fail closed rather than accepting unauthenticated requests.

## Initial API

- `GET /health` — public health probe
- `POST /tasks` — admin creates a task (JSON requires `goal`)
- `GET /tasks` — admin lists all tasks; worker sees queued or assigned tasks
- `GET /tasks/:id` — task detail and events, subject to role checks
- `POST /tasks/:id/accept` — worker accepts as its configured identity
- `POST /tasks/:id/heartbeat` — assigned worker refreshes its heartbeat; heartbeat events are persisted in task history
- `GET /monitoring/workers` — admin-only worker/task heartbeat view, including stale-heartbeat flags (default timeout 60 seconds; set `JARVIS_HEARTBEAT_TIMEOUT_MS` to override, minimum 5 seconds)
- `POST /tasks/:id/events` — assigned worker reports `progress`, `result`, `blocked`, or `failed`
- `POST /tasks/:id/approve` — admin approves/rejects a gated result
- `POST /tasks/:id/retry` — admin requeues eligible tasks within the attempt limit

## Next steps

1. Verify CI after the authentication changes.
2. Add request rate limits, secret rotation guidance, and stronger per-worker identity.
3. Add a real worker executor and orchestrator loop.
4. Add task leases, heartbeats, acknowledgement timeouts, idempotency, and safe reassignment.
5. Move durable state to a production database before concurrent/multi-instance use.
6. Verify deployment with configured secrets and an end-to-end smoke test.
7. Add multi-worker dependency graphs and reusable domain packs.

## MVP success criteria

A task can be created, accepted by an authenticated worker, updated with progress, completed with evidence, or marked blocked/failed; approval-gated results cannot be approved by a worker token; events persist on persistent storage; retries are bounded; and CI plus deployed health checks pass.
