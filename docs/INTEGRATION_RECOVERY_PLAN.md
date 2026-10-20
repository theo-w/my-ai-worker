# Python MVP Runtime Integration and Acceptance Plan

> Status: execution plan, not a claim of completed runtime acceptance. Keep the current Render deployment stable until the Python source of truth, persistence, and authenticated APIs are verified together.

## Why this plan exists

The live Render service starts `python -m mvp.server` from `feat/autonomous-twin-project-loop`. The repository `main` branch contains the Render Blueprint configured for `main`, but the live service setting still points at the feature branch. The histories diverged materially, so switching the service branch or merging the old feature branch wholesale is unsafe.

The open heartbeat PRs (#4 and #5) primarily change `src/server.js` (Node.js); those changes do not automatically fix the Python runtime deployed by Render. PR #6 adds Python MVP observability and bounded Twin-advance features but targets the old feature branch and must be ported/rebased selectively.

## Safe order of work

1. **Freeze scope and compare runtime paths**
   - Treat `mvp.server` + `mvp.workforce` as the deployed runtime.
   - Inventory routes and state transitions on `main` and the deployed branch.
   - Port only missing behavior; do not merge unrelated Node.js runtime changes into the Python service.

2. **Automated regression suite**
   - Run Python compile checks and all pytest tests on the proposed branch.
   - Verify admin/worker role boundaries, invalid credentials, worker claim/lease ownership, heartbeat authorization, duplicate/late result rejection, and independent verification.
   - Verify query-string paths for `/playtest`, `/trace`, and the logic-flow page.
   - Verify unknown blockers remain blocked and retries are bounded to known transient infrastructure failures.
   - Verify improvement reporting is observe-only and never auto-accepts results, edits code, changes permissions, or deploys.

3. **Durability**
   - Confirm `JARVIS_WORKFORCE_STORE` is honored by the deployed runtime.
   - Configure persistent storage or migrate state to a durable managed store before claiming restart-safe task history.
   - Test create task → restart/redeploy → inspect task and event history.

4. **Authenticated live acceptance**
   - Use non-production test credentials; never print or commit tokens.
   - Create a task as admin; claim and heartbeat as the assigned employee; submit progress/result; verify result as a distinct authorized actor; inspect the event trace.
   - Test unauthorized worker actions and ensure they are rejected.
   - Do not use simulated results as evidence of real web research or real LLM execution.

5. **AI-native game feasibility workflow**
   - Create a bounded task for one gameplay hypothesis.
   - Separate Chinese and English market/customer signals; retain source URLs and provenance.
   - Record a falsifiable hypothesis, counter-evidence, prototype experiment, success/failure thresholds, and a decision with uncertainty.
   - Keep the report blocked or inconclusive when evidence is insufficient; do not manufacture citations or claim live research when no provider is configured.

6. **Deployment alignment**
   - Compare the final tested commit to the Render service branch and live deployment SHA.
   - Only align Render to `main` after the complete Python MVP and required configuration are present and the acceptance suite passes.
   - Check health endpoint, protected APIs, trace UI, and persistence after deployment.

## Acceptance gates

| Gate | Pass condition |
|---|---|
| Build | Python compile check and pytest suite pass on the exact candidate SHA |
| Auth | Admin/worker separation and lease ownership verified by tests |
| Lifecycle | Claim, heartbeat, progress, result, independent verification, and trace events work end-to-end |
| Safety | Unknown blockers do not auto-retry; no self-approval or autonomous code/deploy changes |
| Durability | Task and event state survive a service restart |
| Research provenance | Every factual market claim has traceable source evidence, or is explicitly marked simulated/unverified |
| Live deployment | Tested SHA matches the deployed branch/commit; live API and UI checks pass |

## Current limitations to report honestly

- A page returning HTTP 200 proves route availability only; it does not prove authentication, worker lifecycle, real LLM calls, external research, or restart persistence.
- A successful build/deploy is not full end-to-end acceptance.
- Recursive self-improvement remains observe-only unless a proposal passes independent evaluation and explicit human approval.
