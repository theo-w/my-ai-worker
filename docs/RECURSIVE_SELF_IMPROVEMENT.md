# Recursive Self-Improvement Protocol (Design)

## Purpose

JARVIS should improve not only task outcomes, but also the process it uses to achieve them. Self-improvement is a bounded, evidence-driven control loop—not unrestricted self-modification and not a requirement to create more agents.

This document defines a staged design target. It does not claim the current runtime already performs autonomous learning or code modification.

## Improvement loop

1. **Observe:** collect task outcomes, worker feedback, event history, blockers, retries, elapsed time, cost where available, and independent verification results.
2. **Diagnose:** identify a concrete gap against an explicit success criterion. Separate observed facts from model-generated hypotheses.
3. **Propose:** create a versioned improvement proposal with the problem, supporting examples, expected benefit, risks, cost, and a falsifiable prediction.
4. **Evaluate:** test the proposal on a fixed regression suite or replayable tasks. Compare it with the current baseline using the same criteria.
5. **Gate:** reject proposals that fail safety, quality, or cost limits. Require human approval for production code changes, permission changes, external publication, destructive actions, or changes that expand the system's own authority.
6. **Adopt:** roll out a passing change in a reversible, limited scope; record the version and evaluation results.
7. **Monitor and revert:** compare real outcomes with the baseline. Automatically roll back reversible changes when predefined regression thresholds are crossed; escalate when rollback is unsafe or uncertain.
8. **Reflect on the evaluator:** only after the basic loop is reliable, evaluate whether the diagnosis and evaluation process itself is producing useful, repeatable decisions. This is the recursive layer.

## What may improve

- Goal decomposition and task ordering
- Choosing between a single worker and temporary collaboration
- Worker capability matching and task instructions
- Retry, timeout, and escalation policies
- Evidence requirements and independent verification rules
- Tool selection and bounded prompts/workflows

## What must not self-authorize

- Raising its own permissions or removing approval gates
- Disabling logging, monitoring, tests, or independent verification
- Treating its own generated explanation or confidence score as evidence
- Deploying untested code directly to production
- Repeating improvement cycles indefinitely or spending unbounded time/tokens/money
- Using a change's own self-reported success as the sole acceptance signal

## Measurement

Every proposal must name a baseline and a measurable target. Relevant measures include:

- Task success rate against external acceptance criteria
- Evidence coverage and independent verification pass rate
- Rework, retry, and duplicate-work rate
- Time to completion and time spent blocked
- Tool/model cost per accepted result
- Safety incidents and false-positive/false-negative validation outcomes

Do not optimize a single metric in isolation. For example, faster completion is not an improvement if correctness or evidence quality drops.

## Stopping and escalation

Each run has explicit limits for improvement iterations, wall-clock time, tool/model budget, and failed experiments. Stop when the target is met, marginal improvement falls below a defined threshold, a safety invariant fails, or the budget is exhausted. Surface unresolved blockers and evidence to the human operator rather than silently looping.

## Rollout stages

1. **Observe-only:** summarize recurring failures and recommend changes; no self-modification.
2. **Offline evaluation:** run proposed workflow/prompt/policy changes against regression cases.
3. **Reversible bounded adoption:** enable passing changes for a limited task class, with audit trail and rollback.
4. **Recursive evaluation:** assess and improve the quality of the improvement proposals and test suite, still subject to the same external acceptance criteria and limits.

## MVP integration order

The first priority remains the task execution loop: digital twin plans and manages tasks; workers accept, heartbeat, execute, and report structured results; monitoring exposes status and blockers; independent validation checks outcomes. Once this loop is testable, add observe-only improvement reports. Do not build autonomous code rewriting before the task lifecycle and verification path are reliable.
