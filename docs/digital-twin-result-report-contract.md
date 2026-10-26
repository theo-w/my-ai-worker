# Digital Twin Result Report Contract v1

This contract applies to every digital-twin / digital-employee task, not only game feasibility.

## Purpose
A result report must let a person quickly decide whether to adopt, conditionally adopt, test further, or reject the result. It must explain how the result was reached and make uncertainty visible. Report completeness is not proof of correctness.

## Required report sections
1. **Decision at a glance**
   - conclusion and recommended action
   - adoption status: `ADOPT`, `CONDITIONAL`, `NEEDS_VALIDATION`, `REJECT`, or `BLOCKED`
   - confidence label with rationale, not an unexplained percentage
   - most important reason and highest-impact unresolved risk
2. **How the conclusion was reached**
   - question/task and scope
   - method, tools actually used, time range, and sources actually consulted
   - numbered reasoning steps, each linked to supporting evidence or clearly labelled as inference
   - assumptions and calculations, including formulas, units, inputs, and source for each input
3. **Evidence ledger**
   - claim ID and exact claim
   - evidence IDs, source URL/title/date, excerpt or observed data
   - evidence role: primary user signal, secondary analysis, official/industry data, experiment/measurement, internal record, or unclassified
   - source quality, freshness, independence/duplication, sample size and representativeness where known
   - whether evidence directly supports the claim, only indirectly relates, conflicts with it, or is missing
4. **Objectivity and counter-check**
   - strongest evidence against the conclusion
   - alternative explanations and possible confirmation/selection bias
   - data gaps, unknowns, conflicts, stale sources, duplicated sources, and unverified assumptions
   - what evidence would change the conclusion
5. **Adoption guidance**
   - what can be used now and under what conditions
   - what must not yet be treated as fact
   - cheapest/highest-value next validation step, expected cost/time if supportable
6. **Task acceptance**
   - checklist of required deliverables and dimensions
   - each item marked passed, failed, blocked, or not tested, with evidence
   - no task may be called complete solely because prose/report generation succeeded

## Evidence and decision rules
- Separate observation, quoted user expression, externally reported claim, inference, and recommendation.
- A valid URL or a high model confidence is not proof of truth.
- Do not count copies/reposts as independent evidence.
- Secondary articles can generate hypotheses and competitor context, but cannot by themselves prove direct user demand.
- Do not invent sample sizes, conversion rates, market size, costs, test results, tool calls, or sources.
- If a claim lacks direct support, label it unsupported or inferred.
- If material evidence is missing or counter-evidence remains unresolved, downgrade the adoption status.
- Cost/market calculations must show formula, assumptions, units, ranges, and sensitivity to major assumptions.
- The report must not hide failed searches, inaccessible sources, or unavailable tools.
- When evidence is insufficient, the system must make a reasoned provisional decision (including "do not adopt yet") and propose validation; it must not fill gaps with plausible-sounding prose.
- Automated quality checks assess completeness and traceability only. They must never label a claim "true" without an actual verification procedure and recorded result.

## Universal acceptance gate
A report is acceptable only if a reviewer can answer:
- What exactly is being claimed?
- Which evidence supports each material claim?
- What is fact versus inference?
- What contradicts the conclusion?
- What is unknown or biased?
- Why is the adoption recommendation proportionate to the evidence?
- What would change the recommendation?
- What is the next validation step, and what will it cost?

If any critical question cannot be answered, the result must say `NEEDS_VALIDATION` or `BLOCKED`, not silently pass.
