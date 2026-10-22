# Commercial Feasibility Gate — AI-native game mechanics

## Purpose

A digital-twin task is complete only when it has answered the decision question at the agreed depth. "Workers finished", "a report exists", and "a model recommends GO" are not completion criteria by themselves.

The gate is inspired by a Grill-Me style discovery loop: expose assumptions, ask high-impact questions, research both supporting and opposing evidence, estimate costs, and run the smallest experiment capable of falsifying the core hypothesis.

## Decision outcomes

- `GO_TO_PROTOTYPE`: evidence is strong enough to fund only the next bounded prototype/vertical-slice experiment. This is not permission for full production.
- `ITERATE`: the idea may be promising, but one or more weak dimensions need another targeted experiment.
- `NO_GO`: a specific, evidence-backed critical blocker makes the concept unacceptable or infeasible. A low score alone should normally trigger `ITERATE`, not an automatic rejection.
- `INSUFFICIENT_EVIDENCE`: required dimensions or evidence are missing. This is a valid research outcome, not a pass.

## Required dimensions

1. Player value and target segment.
2. Differentiation versus existing alternatives.
3. Technical feasibility: quality, latency, reliability, controllability.
4. Market evidence: user behavior, competitor landscape, willingness-to-pay signals.
5. Unit economics: per session / active user / month variable costs and plausible revenue.
6. Production and operating cost: prototype, vertical slice, launch, content, evaluation, moderation, infra, support, ongoing model usage.
7. Retention and replayability beyond novelty.
8. Risk and compliance: privacy, safety, IP, platform constraints and operational risks.

Every dimension needs a 1–5 score, written rationale, evidence references, confidence/unknowns, and at least one way the conclusion could be wrong. Scores are decision aids, not measured probabilities.

## Cost model requirements

Show conservative, base, and optimistic scenarios. Make assumptions visible and editable. At minimum estimate:

- Prototype and vertical-slice effort (person-weeks, elapsed time, cash cost).
- Model/service cost per core loop or session, including retries and moderation.
- Monthly cost at multiple active-user levels.
- Plausible monetization and net revenue after platform/payment fees where relevant.
- Gross margin / contribution per active user.
- Break-even users or revenue, with formula and sensitivity to retention/session length/model calls.
- Ongoing content, QA, evaluation, operations and support costs.

If pricing, retention, conversion, or usage data is not known, use explicit ranges and label them as assumptions; never fabricate precision. A favorable base case is insufficient if a reasonable conservative case creates an unacceptable downside.

### Machine-checkable cost scenarios

The evaluator does not accept an assumptions list plus empty scenario objects as a cost model. Each of `conservative`, `base`, and `optimistic` must include numeric, finite values for:

- `prototype_cost_usd`
- `model_cost_per_session_usd`
- `monthly_cost_usd_at_1000_users`
- `monthly_revenue_usd_at_1000_users`
- `break_even_users`
- `gross_margin_percent` (may be negative, but must be between -100 and 100)

Costs, revenue and break-even user counts must be non-negative. Assumptions must be explicit and non-empty. These checks validate report completeness, not whether an estimate is true.

The automatic draft deliberately leaves prices and usage-dependent figures unknown when they have not been configured or measured. It can show candidate counter-evidence sources, but it does not promote them to reviewed counter-evidence or count retrieved domains as independent sources.

## Grill-Me discovery loop

Ask the smallest number of high-impact questions that change the decision. Continue with research and analysis for questions that can be answered without the user. Ask the user only for decisions or constraints that materially change the answer (for example target platform, budget ceiling, team capacity, target audience, monetization constraints).

For every key hypothesis:
- state the hypothesis and its observable success/failure signal;
- gather support and counter-evidence from traceable sources;
- distinguish primary evidence, secondary reports, expert judgment and assumptions;
- define the smallest falsification experiment, its sample/measurement limits, timebox and cost;
- record what would change the recommendation.

Do not ask endless questions for completeness' sake. Stop when remaining unknowns no longer change the next decision, or when the agreed time/budget limit is reached. If they do change the decision, return `INSUFFICIENT_EVIDENCE` or `ITERATE`.

## Completion contract

A commercial-feasibility task can be marked complete only when:
- the decision question and scope are explicit;
- all eight dimensions are assessed or explicitly marked unknown;
- support and counter-evidence are recorded;
- cost scenarios and major sensitivities are shown;
- the prototype/experiment plan has measurable gates;
- limitations, unresolved risks and confidence are disclosed;
- the decision follows the recorded evidence rather than a desired outcome.

A completed *assessment* may conclude NO_GO or INSUFFICIENT_EVIDENCE. Completion means the investigation met its agreed standard, not that the business idea was judged viable.

## Current implementation boundary

The server exposes authenticated `POST /api/feasibility/contract` and `POST /api/feasibility/evaluate` routes, plus `GET /api/feasibility` for the current in-memory assessment state. The evaluator creates the discovery contract and applies conservative structural gates. Its evaluator checks that a report contains dimension scores, evidence references, source-count metadata, counter-evidence, prototype evidence and a cost model. It cannot independently prove that cited sources are genuinely independent, that estimates are accurate, or that a prototype actually ran. Those need server-side evidence resolution, real experiment records and independent verification before this gate can be treated as production-grade.
