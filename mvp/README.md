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
