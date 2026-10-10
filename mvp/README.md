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


### Dashboard research workflow

The local Dashboard now includes a research panel wired to `POST /api/research`. It displays provider status, returned source links, evidence quality counts, deterministic baseline synthesis, and the optional LLM synthesis result. It does not fabricate results when the search provider is absent or fails.

Configure a search service that implements the documented JSON HTTP contract:

```bash
export JARVIS_SEARCH_ENDPOINT="https://your-search-provider.example/search"
export JARVIS_SEARCH_API_KEY="your-search-api-key" # if required by your provider
```

The endpoint is called with `?q=<query>&limit=<n>` and should return either a JSON list or an object containing `results`. Each result should include `title`, an HTTPS `url`, and a `snippet` (or `description`). Provider-specific authentication and schema translation belong in the adapter. The Dashboard status indicators are configuration checks, not proof that credentials or the remote service are valid; run a research request to verify the integration.

When both search and LLM are configured, JARVIS deduplicates returned URLs and sends only quality-accepted source excerpts to LLM synthesis. The synthesis must cite supplied source IDs and may not invent links. This pipeline validates the supplied excerpts and URL shape, not the truth of the full pages; human review and stronger source verification remain necessary before high-impact decisions.


## Accuracy and trust policy

JARVIS separates language-model reasoning from deterministic controls and external-tool execution:

- **LLM**: proposes plans, summarizes supplied material, drafts options, and explains uncertainty. Its text is marked `model_generated_unverified` and is never automatically treated as factual evidence.
- **Rules/code**: validate schemas, allowed capabilities, task limits, approval boundaries, and decision state transitions. These controls are deterministic when correctly implemented, but still require tests and code review.
- **External tools**: provide traceable outputs such as search results or test logs. Traceability does not guarantee freshness, completeness, or truth.
- **Evidence gate**: checks source structure, excerpts, confidence thresholds, and simulated status. Passing the gate means the configured mechanical checks passed; it is not proof that a claim is true.
- **Human review**: remains required for high-impact decisions and actions covered by approval policy.

`mvp/accuracy.py` provides explicit trust labels, conservative HTTPS source-record checks, and a fail-closed evidence decision helper. The helper is not a replacement for domain-specific review and must be integrated into each consequential decision path before production use.

Recommended validation layers for any new capability: (1) unit tests for rules, (2) contract tests for provider responses, (3) adversarial/invalid-output tests for LLM results, (4) integration tests with mocked external services, (5) controlled real-provider smoke tests, and (6) human review of sampled outputs. Track factual error rate, unsupported-claim rate, source citation precision, task success rate, and escalation rate separately; do not use model self-confidence as a correctness metric.

## Hybrid Worker Executor and trust boundaries

When a search endpoint and/or LLM credentials are configured, the server uses
a capability-aware executor router. It does not treat an LLM response as proof
that a research task actually searched the web.

- Research capabilities require `JARVIS_SEARCH_ENDPOINT`. If it is missing,
  research tasks are blocked rather than silently answered by the LLM.
- Analysis/design tasks require the configured OpenAI-compatible LLM. If it is
  missing in hybrid mode, those tasks are blocked rather than reported complete.
- A research task is only considered completed when at least one result passes
  the mechanical evidence-quality gate. That gate checks provenance structure,
  excerpts and confidence thresholds; it does **not** prove that a source is
  truthful or semantically supports every claim.
- LLM-generated content is labeled as unverified. Search snippets are also not
  automatically treated as verified truth.
- Code implementation and test execution are not yet wired to a real sandbox
  or test-runner adapter. The executor status endpoint reports these gaps.

Check the current capability configuration at:

```
GET /api/executor/status
```

The response reports the executor mode, whether search/LLM are configured,
which capabilities are available, and explicit trust-policy flags. Never place
API keys in source control; configure them in the runtime environment.


## Game experience-design MVP API

JARVIS exposes a structured first-pass workflow that analyzes a reference game's
transferable design mechanisms, proposes a distinct concept, maps hypotheses
across player perspectives, and creates a small prototype-validation plan.

Start the local server:

```bash
python -m mvp.server
```

Call the endpoint:

```bash
curl -X POST http://127.0.0.1:8765/api/experience-design \
  -H 'Content-Type: application/json' \
  -d '{"source_game":"塞尔达传说：王国之泪","concept_name":"潮痕档案馆"}'
```

The response contains `brief` plus a `trust` section. When a configured
OpenAI-compatible LLM is available, it generates a structured design brief;
otherwise a deterministic, explicitly labeled template is returned. LLM
outputs must pass JSON schema-shape checks and are never treated as verified
player research. The endpoint forcibly reports `market_validated=false` and
`playtested=false`. The current fallback concept is a starting hypothesis,
not a claim of proven originality, player appeal, or commercial viability.

Automated tests in `mvp/test_experience_design.py` cover required fields,
input validation, invalid model output, and the rule that model output cannot
declare market validation or playtesting complete.


## Playable prototype: Tidemark Archive warehouse

With the local server running, open `http://127.0.0.1:8765/playtest` or use the
link in Game Experience Lab. The scene lets a player inspect three objects,
talk to two residents, try a standard key solution or describe an alternate
action, and export the local event log as JSON.

**Important limitation:** this is a deterministic rule-based interaction
prototype, not an LLM-driven world and not a completed game. It recognizes a
small set of authored action patterns. Unrecognized actions are retained as
test signals rather than treated as impossible in principle. The goal is to
check whether the experience loop is understandable before investing in a
larger dynamic-NPC implementation. Do not interpret a successful scripted path
as evidence of emergent AI behavior or market demand.

For a real-model test, configure `JARVIS_LLM_BASE_URL`,
`JARVIS_LLM_API_KEY`, and `JARVIS_LLM_MODEL` in the runtime environment.
Never commit credentials. The current CI run checks the Python suite; it does
not execute browser interaction tests or prove that a real provider is reachable.


## Manual ChatGPT response handoff (Loophole first, reusable JARVIS capability)

The playtest includes a **manual** temporary-model workflow at `/playtest`. It does
not read ChatGPT conversations automatically and does not require an API key:

1. Enter a player's action and inspect/talk to clues as usual.
2. Generate and copy the context-scoped prompt into a ChatGPT conversation.
3. Ask ChatGPT for the single JSON object requested by the prompt.
4. Paste the response back into the playtest and submit it for validation.

The response contract includes `intent`, `action_kind`, `entities`, `reasoning`,
`uncertainties`, and `counterexample`. `mvp/model_handoff.py` validates the
shape and allowed vocabulary, then passes the proposal to the independent game
rules validator. A model saying "success" cannot itself authorize a state change.
Invalid output fails closed. The raw pasted response and the validation result are
included in the **browser-local** event log export when a handoff is submitted;
the endpoint does not persist conversation text on the server. Review exported
logs before sharing them, since they can contain pasted text.

This is an experimental handoff protocol, not a real ChatGPT connector. The
game-specific transition validator remains separate from the reusable handoff
contract so later JARVIS capabilities can define their own validators. A successful
build/deploy only confirms the service is running; it does not establish player
appeal, market validation, or the correctness of model reasoning.


### Current handoff verification checklist

- [ ] A normal key action is accepted only when the action text mentions a key and the door/unlocking action.
- [ ] The alternate route is accepted only when the action connects bell, rail/rope, tide and signal, and the required inspection/talk state is present.
- [ ] A model claiming "success" without rule conditions cannot open the warehouse.
- [ ] Invalid JSON, unsupported action kinds/entities, invalid state types, and oversized responses fail closed.
- [ ] Browser UI manual handoff works on the deployed service and the exported event log can be inspected.
- [ ] Deployment status is confirmed for the latest commit, not inferred from a previous live build.

The first five items require code/tests or hands-on runtime checks; a successful Render deploy alone does not mark them all complete.
