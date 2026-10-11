# My AI Worker

JARVIS Digital Employee Runtime — the runtime foundation for a domain-agnostic AI Workforce OS.

## Project direction

Build a digital-twin orchestrator that can decompose goals, assign tasks to capable digital employees, track execution, receive structured feedback, validate results, resolve blockers, and resume work reliably.

The first domain pack is AI-native game feasibility and game-operations analysis. The core task/worker protocol should remain reusable for other domains.

## Current repository status

- JARVIS game-operation copilot demo: `demo/JARVIS_AI_Game_Operation_Copilot_V4.html`.
- Task lifecycle and worker feedback contract: [Digital Workforce Protocol](docs/DIGITAL_WORKFORCE_PROTOCOL.md).
- A first Node.js HTTP runtime now exists in `src/server.js`, with task creation/inspection, worker acceptance, progress/result/blocker/failure events, bounded manual retries, human approval gates, and a health endpoint.
- Runtime state and event history are stored in a JSON file at the configured `JARVIS_STORE_PATH` (default: `data/runtime.json`). Use persistent disk storage in deployments where local filesystems are ephemeral.
- Automated tests and a health smoke-test workflow are configured in `.github/workflows/runtime-tests.yml`. Check the Actions result before treating the code as verified.
- **Not yet complete:** an autonomous scheduler that launches workers, acknowledgement-timeout reassignment, multi-worker dependency orchestration, production-grade database/concurrency handling, and verified deployment. The API currently accepts worker feedback; it does not itself provide an LLM-powered worker.

## Run locally

Requires Node.js 20 or later.

```bash
npm test
npm start
```

The server listens on `0.0.0.0:10000` by default. Override `PORT` and `JARVIS_STORE_PATH` as needed.

## Initial API

- `GET /health` — runtime health
- `POST /tasks` — create a task (JSON body requires `goal`)
- `GET /tasks` — list tasks
- `GET /tasks/:id` — task details and event history
- `POST /tasks/:id/accept` — accept a task (JSON: `worker_id`)
- `POST /tasks/:id/events` — send `progress`, `result`, `blocked`, or `failed` event
- `POST /tasks/:id/approve` — approve/reject a result when approval is required
- `POST /tasks/:id/retry` — requeue an eligible blocked/failed task within its attempt limit

## Recommended next steps

1. Run CI and fix any test failures.
2. Deploy the runtime and confirm `/health` works in the real environment.
3. Add an actual worker executor and an orchestrator loop.
4. Add task lease/heartbeat, acknowledgement timeout, safe reassignment, and idempotency.
5. Move durable state to a production database before concurrent or multi-instance use.
6. Extend to multi-worker dependency graphs and reusable domain packs.

## MVP success criteria

A task can be created, accepted by a worker, updated with progress, completed with evidence, or marked blocked/failed; events survive restart on persistent storage; retries are bounded; approval-gated results cannot succeed before approval; and CI plus deployed health checks pass.
