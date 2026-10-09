# JARVIS Game Validation MVP

This MVP validates the core Digital Workforce loop:

User goal -> Strategy Team -> parallel Workers -> Evidence -> Decision -> Prototype Sprint.

## Run

```bash
python3 mvp/run.py "做一款玩家可以和有长期记忆 NPC 建立关系的 AI 原生 RPG"
```

The current workers are deliberately simulated. They validate orchestration and decision flow, not real market research.

## Example output

- 4 workers active
- 8 evidence items collected
- recommendation: GO_TO_PROTOTYPE
- confidence: 78%
- next step: AI Game Prototype Sprint

## Next

Replace simulated workers with real web research + LLM synthesis while keeping the same Worker interface.


## Operations Dashboard

For an HR/company-ready product walkthrough:

```bash
python3 mvp/server.py
```

Open `http://127.0.0.1:8765`.

The dashboard demonstrates:

1. Natural-language business/game goal
2. Digital Twin intent + policy layer
3. Dynamic Digital Workforce team formation
4. Worker execution and live status
5. Evidence stream (explicitly simulated in this MVP)
6. Evidence-first GO / NO-GO decision
7. One-click handoff to an AI Game Prototype Sprint

The product story is intentionally end-to-end rather than feature-heavy:

```
Digital Twin
    ↓
AI CEO / Intent
    ↓
Dynamic Digital Workforce
    ↓
Research / Analysis Workers
    ↓
Evidence
    ↓
Decision
    ↓
Prototype Sprint
```

This is a showcase MVP: the orchestration is real, while research outputs are simulated. The next implementation replaces individual simulated Workers with real Web Research + LLM Synthesis without changing the product-level workflow.


## Configurable live research provider

JARVIS now includes a vendor-neutral HTTPS JSON search adapter. It is not
automatically connected to a search service; configure one that supports the
response contract below.

Set environment variables before starting the server:

```bash
export JARVIS_SEARCH_ENDPOINT="https://your-search-provider.example/api/search"
export JARVIS_SEARCH_API_KEY="your-api-key"
```

The endpoint receives `q` and `limit` query parameters and must return JSON
as either a list or `{"results": [...]}`. Each usable result needs `title`,
an HTTPS `url`, and `snippet` (or `description`). The optional key is sent
as a Bearer token. Never commit API keys to the repository.

This is the provider adapter and its test contract, not a claim that live
research is already enabled in the dashboard. Without a configured provider,
the adapter reports that live research is unavailable and returns no sources.


## Live research API

The local server exposes `GET /api/research/status` to check whether
`JARVIS_SEARCH_ENDPOINT` is configured, and `POST /api/research` with JSON
`{"query":"AI native games","limit":5}` to run the configured search provider.
The response includes source records, evidence-quality decisions, and a
deterministic synthesis. Provider failures and unconfigured state are returned
explicitly; they are not treated as successful research.

These endpoints are an API integration, not yet a dedicated Dashboard research
panel. The default autonomous task executor remains simulated until a real
worker adapter is deliberately configured.


## Demo handoff versus evidence-backed decisions

The Dashboard invokes the evaluation function with `demo_mode=True` so a user can exercise the prototype handoff in a clearly labeled demo. When all findings are simulated, the decision is `DEMO_GO_TO_PROTOTYPE`, and the prototype endpoint labels the handoff as demo-only. This is not a real business approval. Calls to `evaluate()` default to strict evidence mode and keep simulated-only findings at `HOLD_FOR_EVIDENCE`; only source-backed non-simulated evidence can yield `GO_TO_PROTOTYPE`.

The canonical autonomous project loop is `mvp/twin.py`. The duplicate `mvp/autonomous.py` has been removed, and its tests now exercise the canonical implementation. `.gitignore` excludes local environment files, Python caches, and local data; `pyproject.toml` declares Python 3.12+ and the optional pytest development dependency.


## Configurable LLM Worker runtime (v0.8 foundation)

The autonomous project loop can use an OpenAI-compatible chat-completions endpoint for task execution. Configure these environment variables before starting the server:

```bash
export JARVIS_LLM_BASE_URL="https://your-llm-provider.example/v1"
export JARVIS_LLM_API_KEY="your-api-key"
export JARVIS_LLM_MODEL="your-model-name"
python -m mvp.server
```

The adapter expects `POST {JARVIS_LLM_BASE_URL}/chat/completions` (or a base URL already ending in `/chat/completions`) and a response with `choices[0].message.content`. The endpoint must use HTTPS. Keep keys in environment variables or a secret manager; never commit them.

Check `GET /api/llm/status` to see whether the server started in `llm` or `simulated` mode. If the required variables are absent or configuration is invalid, the server stays in explicitly reported simulated mode. The LLM executor returns auditable task outputs, but it does not browse the web, verify claims, or create source-backed evidence. Do not treat a model response as a verified research finding or a business approval.

The default Dashboard research pipeline remains separate: configure `JARVIS_SEARCH_ENDPOINT` to use the JSON search adapter. LLM execution and live search are distinct integrations and must both be configured to provide a real research-and-synthesis workflow.
