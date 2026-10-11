# Goal-Driven Autonomous System: Architecture Decision

**Status:** Adopted as the target architecture for the MVP  
**Scope:** Digital Twin / Digital Employee runtime in `mvp/`

## Product goal

Build a system that autonomously completes complex goals with controlled permissions,
observable execution, evidence-backed verification, and bounded recovery. Do not optimize
for reproducing a human company's departments or hierarchy.

## Design decisions

1. **Keep the Digital Twin; change its responsibility.** It owns intent interpretation,
   success criteria, constraints, execution-mode selection, plan revisions, worker feedback,
   cancellation/supersession decisions, and final acceptance. It is a closed-loop controller,
   not just a dispatcher.
2. **Keep workers; make roles temporary.** A worker is a configurable capability/tool bundle
   with explicit permissions, resource limits, and runtime status. A task may assemble a
   temporary team from capability-compatible workers; persistent job titles are optional metadata.
3. **Single-agent first.** Start with one agent unless there is an explicit expected benefit
   from parallelism, specialization, or independent review. Team formation must account for
   complexity, parallelizability, expected quality/time gain, coordination cost, and risk.
4. **Separate execution from verification.** A non-empty worker response is an output, not
   proof of correctness. Claims requiring evidence must carry traceable source data and pass
   evidence-quality checks. High-risk/high-quality work should receive independent review when
   available. Failed verification returns the work to revision or leaves the goal blocked.
5. **Closed-loop planning.** Reassess after meaningful outputs and failures. Replan only when
   new information changes the plan; merge duplicate work, supersede stale tasks, cancel work
   with negative expected value, and bound retries/iterations. Preserve an audit trail for each
   decision.
6. **Observability is infrastructure, not a cognitive constraint.** Heartbeats, worker/task
   states, input/output provenance, attempts, leases, cost, latency, blockers, verification
   decisions, and recovery events should be inspectable. A stale heartbeat means suspected
   unavailability, not proof that a process is dead.
7. **Policy and permissions are explicit.** Tool permissions are least-privilege. Human
   approval gates remain for configured high-impact actions. Autonomy never implies unrestricted
   access.
8. **Measure before standardizing.** Record per-task quality, verified success, latency, cost,
   retry rate, and human intervention. Compare single-agent, team, and independent-review modes
   on representative task suites before changing selection thresholds.

## Runtime flow

Goal + success criteria + constraints -> execution-mode decision -> plan and bounded execution
-> observations/worker feedback -> revise/merge/cancel/retry -> independent verification/evidence
gate -> accepted result or explicit blocked/escalated state.

Monitoring observes this flow and must not mark a goal complete merely because a worker reported
completion.

## MVP implementation sequence

- [x] Add a deterministic, inspectable execution-mode policy as an initial decision seam.
- [x] Connect the policy to the Digital Twin goal loop, capability-based worker selection, and bounded concurrent polling for justified parallel-team mode.
- [ ] Add a verifier interface that consumes output, task criteria, provenance, and evidence.
- [x] Require evidence-gate verification before goal-level completion for research/evidence-required tasks; semantic truth still needs domain checks or human review.
- [x] Add authenticated worker heartbeat/registration and expose offline suspicion in the monitor.
- [x] Add audited merge/cancel operations for pending tasks, with optional per-cycle revision policy hooks and bounded action counts. Automatic semantic replanning still depends on a trustworthy planner/revision policy.
- [ ] Benchmark single-agent versus team mode on representative tasks; tune thresholds from
  observed outcomes.

## Honest MVP boundary

The mode selector is a deterministic policy baseline, not an autonomous learned policy. Its estimates
must be supplied or produced by a planner and later calibrated against observed outcomes. Existing
simulated executor results remain simulated and cannot count as independent evidence. Live monitoring
requires a running server and valid credentials.
