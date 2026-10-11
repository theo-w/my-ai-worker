# My AI Worker

JARVIS Digital Employee Runtime — the runtime foundation for a domain-agnostic AI Workforce OS.

## Project direction

Build a digital-twin orchestrator that can decompose goals, assign tasks to capable digital employees, track execution, receive structured feedback, validate results, resolve blockers, and resume work reliably.

The first domain pack is AI-native game feasibility and game-operations analysis. The core task/worker protocol should remain reusable for other domains.

## Current repository status

- GitHub repository initialized and connected.
- JARVIS game-operation copilot demo is available in `demo/JARVIS_AI_Game_Operation_Copilot_V4.html`.
- The digital-workforce task lifecycle, worker feedback contract, API target, reliability requirements, and acceptance tests are documented in [Digital Workforce Protocol](docs/DIGITAL_WORKFORCE_PROTOCOL.md).
- Runtime APIs, persistent queue/storage, real worker execution, and deployed end-to-end tests remain implementation work; documentation is not evidence that these runtime capabilities are already working.

## Recommended implementation order

1. Implement persistent task and event storage.
2. Implement task creation/inspection and worker accept/event endpoints.
3. Build one real worker and the orchestrator loop.
4. Add acknowledgement timeout, bounded retry, blocker escalation, and human approval gates.
5. Add automated acceptance/smoke tests and deployment health checks.
6. Extend to multi-worker dependency graphs and domain packs.

## MVP success criteria

A task can be created, accepted by a worker, updated with progress, completed with evidence, or marked blocked/failed; all events persist across restart; retries are bounded; approval-gated actions cannot run before approval; and health plus end-to-end smoke tests pass.
