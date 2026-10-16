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
