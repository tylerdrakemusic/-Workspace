---
mode: SigmaCapital-orchestrator
---
# OCO Protective Pair Recalibration

Start this flow through a manual-only action when a previewed protective OCO pair needs a fresh review. This prompt is independent of picker generation and does not recalibrate `trade_candidates`.

This prompt is temporarily maintained in the shared Workspace prompt directory beside the SigmaCapital picker flow. The `sigmacapital*.md` prompts are planned for migration to the private SigmaCapital repository as their proper home.

## Review target

- Select one `oco_protective_pairs` row with status `previewed`.
- Review the existing Stop, Target, quantity, direction, stored broker preview, legs, and events.
- Do not review submitted, partially filled, filled, canceled, rejected, or reconciliation-required pairs in this flow.

## Evidence required

Gather and identify the source for each item before proposing values:

- Current live quote.
- Fresh 14-period ATR and volatility evidence.
- Approved production candidate thesis and rationale, when linked.
- Current market context and fundamentals as contextual evidence.
- Fresh ticker/news or sentiment evidence from the existing research service.
- Broker fill/reconciliation facts and replacement history, when available.

The current quote and ATR must be available. Ticker/news evidence must satisfy the existing four-hour research freshness gate. Fundamentals are provenance only and cannot replace missing price, volatility, or protection evidence.

## Proposal contract

Call the proposal-only recalibration service with the pair ID, current quote, ATR, proposed Stop, proposed Target, thesis, evidence records, and a deterministic idempotency key. Each evidence record must include a source ID and evidence kind.

Successful proposals are immutable, versioned records containing current and proposed Stop/Target values, source provenance, thesis and volatility assessments, protection-risk results, confidence, approval state, supersession linkage, and idempotency data. Reusing an idempotency key for another pair is an error.

If evidence is missing, stale, contradictory, malformed, or fails protection-risk validation, return the failure without persisting a proposal and without refreshing the broker preview.

## Human review sequence

1. Tyler reviews the evidence-backed proposal in the existing Trade Gate Protective OCO pairs section.
2. Tyler explicitly approves the proposal.
3. The service builds the approved Stop/Target payload and requests a fresh Schwab OCO preview.
4. Only a successful fresh preview may update the local `previewed` pair values and payload.
5. The existing Trade Gate two-step confirmation remains required for any live OCO submission.

Never automatically submit, cancel, replace, mutate, or create a broker order. Never bypass quote revalidation, risk validation, dedicated-account binding, immutable audit confirmation, or the existing human confirmation route. Submitted or partially filled pairs remain untouched and require a separate future workflow.

## Completion

Report the proposal ID, pair ID, version, evidence source IDs, current and proposed Stop/Target values, freshness/protection results, preview result, and approval state. If no proposal was persisted, report the exact transient failure and confirm that no OCO preview or broker action occurred.