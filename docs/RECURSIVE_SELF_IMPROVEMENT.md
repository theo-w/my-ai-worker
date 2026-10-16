
## Recursive self-improvement (MVP guardrail)

The first implementation seam lives in \`mvp/self_improvement.py\`:

1. Summarize task outcomes and recurring failure categories.
2. Count a success as verified only when a separate verification record explicitly says so.
3. Evaluate a proposed policy change against a baseline on a minimum number of comparable benchmark cases.
4. Reject candidates with regressions, insufficient samples, invalid scores, negligible gains, or an exhausted iteration budget.
5. Mark a passing candidate as eligible for review; never silently apply code, expand permissions, or deploy it.

This is intentionally a **bounded improvement loop**, not unrestricted self-modifying AI. The module currently provides deterministic summary and evaluation primitives. It does not yet generate semantic proposals from arbitrary logs, run a benchmark suite automatically, persist experiment history, or promote a candidate. Those are later integration steps.

A proposed improvement should be evaluated on a fixed regression suite plus representative AI-native-game feasibility tasks. Record provenance for every run; simulated output must not be counted as verified evidence. Promotion should require operator approval and a rollback path.
