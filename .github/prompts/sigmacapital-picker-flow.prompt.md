---
mode: Σcapital-orchestrator
---
# ΣCapital Off-Market Trade Picker Flow Prompt

Use this prompt as the canonical instruction set for ΣCapital's off-market/evening trade candidate generation and approval workflow.

## Context
- Generate off-market/evening trade recommendations from fresh research and, when available, live read-only Schwab account context.
- A candidate is a recommendation grounded in the live account context, pending Tyler's manual review and approval; it is not an order and has not been placed.
- Candidate generation and database insertion must never call an order-placement API or place an order. Only the human-confirmed Trade Gate live-approval route may place a real Schwab order.
- The agent must consult the formal Schwab instruction document at `f:\⊕Workspace\.github\instructions\sigmacapital-schwab-trade-inputs.instructions.md` for permitted order types, unit rules, and timing constraints.
- The agent must consult the order-type tradeoff and risk guidance at `f:\⊕Workspace\.github\instructions\sigmacapital-order-type-tradeoffs.instructions.md` when selecting an order type for each candidate. This document governs when to use each order type, execution vs price risk tradeoffs, market-context rules, and the required `execution_certainty` classification.
- The agent must consult the deferred-symbol watchlist workflow at `f:\⊕Workspace\.github\instructions\sigmacapital-watchlist-workflow.instructions.md` before classifying, persisting, enriching, reviewing, or promoting watchlist observations. That document is the runtime handoff for `research.py`, `watchlist.py`, `init_db.py`, and the separate Trade Gate review API.
- Read-only Schwab account API access (including live buying power) may ground recommendations. Order placement is not part of generation or insertion; `place_order` is reachable only through the Trade Gate's human-confirmed live approval path. Cancel/replace behavior is unchanged and must not be expanded.
- No automated order placement is allowed.
- Open-order replacement requests use an agentic open-order replacement proposal flow. The flow is proposal-only and has no live write behavior.
- The replacement proposal must preserve immutable order identity: `account reference`, `symbol`, `side`, `logical execution ID`, and `current broker order ID`.
- The proposal must state the `replacement intent`, every complete proposed replacement field, the `rationale/evidence`, `validation status`, and `operator-review status`.
- This Workspace proposal workflow is separate from the private Capital service execution dependency. Workspace only proposes and validates; Capital Trade Gate executes only after human confirmation.
- Only Capital Trade Gate performs human-confirmed execution. The Workspace agent must not place, cancel, or replace live orders.
- Before proposing any candidates, confirm that a fresh ΣCapital research batch exists in `sigmacapital.db.signals` and that the latest batch is no older than four hours. If no current batch is available or it is stale, automatically run the Σcapital-research agent batch immediately and do not generate any picks until the latest Perplexity signals have been ingested and verified.
- Ensure fresh yfinance pricing is available for the candidate symbol before recommending any pick.
- Do not add or infer a `mode` field on `trade_candidates`. Candidate rows remain pending recommendations until the Trade Gate creates the execution decision. The execution row records its own gated mode after manual approval.
- Watchlist observations are research records, not candidates or orders. A promising symbol that is below the immediate candidate threshold must be classified as watchlist-only and persisted through the documented watchlist workflow, with evidence, provenance, freshness, and a deferred reason. Watchlist capture must not lower candidate thresholds or bypass risk checks.

## Candidate Schema
The agent must generate trade candidates using the following fields:

- `symbol`: equity ticker symbol for the proposed trade
- `side`: `buy` or `sell` for the current `trade_candidates` schema
- `unit`: `Shares` only for off-market flow
- `quantity`: positive share amount
- `order_type`: `Limit`, `Stop`, `Stop Limit`, or `Trailing Stop`
- `limit_price`: required for `Limit` and `Stop Limit`
- `stop_price`: required for `Stop` and `Stop Limit`
- `trailing_amount`: required for `Trailing Stop`
- `trailing_amount_type`: `points` or `percent` when `Trailing Stop` is selected
- `timing`: `Day`, `Day + extended hours`, or `Good till canceled`. GTC orders use regular hours and become active the next trading day when placed after regular hours, on weekends, or on holidays.
- `execution_certainty`: `optional` for `Limit` and `Stop Limit`; `guaranteed` for `Stop` and `Trailing Stop` (or the exact equivalent used by the runtime schema). Preserve this mapping without silently converting order type or timing.
- `estimated_cost`: the modelled order cost used to reserve buying power for elevated buy ideas
- `model`: the exact runtime model that generated the pick. When runtime provenance is unavailable, use the explicit marker `unavailable`; never invent a model name.
- `rationale`: natural-language explanation of the trade idea
- `confidence`: numeric score or percentile representing conviction
- `notes`: optional contextual details or risk considerations

## Workflow Rules
1. Generate a candidate list for the upcoming off-market/evening planning cycle.
2. Return no more than 5 candidates per prompt invocation.
3. Use `execution_certainty: optional` for `Limit` and `Stop Limit` candidates.
4. Use `execution_certainty: guaranteed` for `Stop` and `Trailing Stop` candidates, or the exact equivalent used by the runtime schema.
5. Do not suggest units in `Dollars` for the off-market flow.
6. Use `Shares` only, and derive share quantity from available capital and risk sizing.
7. Ground candidate generation in ΣCapital's local database state:
   - require a fresh research batch for every invocation. If the latest `signals` batch is missing or stale, run Σcapital-research immediately before generating picks and only continue after the new batch is confirmed.
   - the research batch must include niche off-watchlist discovery signals for new ticker ideas beyond the current watchlist and portfolio.
   - confirm the latest live yfinance pricing is fresh and current before using it to size or price candidates.
   - consult `sigmacapital.db` `signals` table for recent research signals and batch context,
   - confirm each research symbol has financial signal enrichment in `sigmacapital.db.signals` before candidate scoring. If the financial signal is missing, enrich the symbol with earnings and fundamentals data before using it in a pick.
   - for a promising but non-eligible symbol, use the watchlist workflow's `record_observation()` path rather than inserting a `trade_candidates` row; on later cycles, append fresh evidence with `reenrich_observation()` and use `shadow_replay()` for non-writing qualification previews.
   - consult `account_state` `buying_power` for available purchasing capacity,
   - consult `portfolio`, `position_valuations`, or `risk_thresholds` as needed to avoid unsupported sizing or duplicate exposures.
8. Ensure the candidate `limit_price`, `stop_price`, and `estimated_cost` are grounded in verified pricing data, using ΣCapital's trade approval gate reference pricing and fresh yfinance-based quote validation where available.
9. Do proper due diligence before proposing any pick: validate news/sentiment, confirm current market data, and avoid speculative entries based on stale or missing signals.
10. Do not suggest sell-side candidates when there are no current holdings. Use the portfolio/position data if available; if holdings cannot be confirmed, avoid Sell and Sell Short recommendations.
11. For buy candidates, estimate the expected order cost and reserve that amount against available buying power when approved.
12. Candidates remain `approval_status: pending` until Tyler approves or rejects them through the Trade Gate. Generation and insertion do not create an execution or place an order.
13. Do not propose order types outside the supported Schwab list.
14. Preserve the separation between recommendations and orders: only the human-confirmed Trade Gate live-approval route may create a real execution row or place an order. Never silently convert the approved order type, timing, unit, or quantity.
15. Stamp every generated candidate with exact runtime model provenance or `unavailable`. This provenance flows through the Trade Gate into execution history and later holdings views.
16. Keep watchlist review and promotion separate from candidate generation. Only an explicit human-supervised promotion may create a new pending candidate, and promotion must never approve or execute an order.

## Output Format
Return candidates in a structured format that can be mapped to ΣCapital's `trade_candidates` table and approval gate. Each candidate should clearly include: `symbol`, `side`, `unit`, `quantity`, `order_type`, `limit_price`, `stop_price`, `trailing_amount`, `trailing_amount_type`, `timing`, `execution_certainty`, `model`, `rationale`, and `confidence`. Do not include a candidate `mode` column.

## Open-Order Replacement Proposal Format
For an open-order replacement request, return a structured proposal with these inputs and outputs:

- Immutable order identity inputs: `account reference`, `symbol`, `side`, `logical execution ID`, and `current broker order ID`.
- Replacement intent: the requested change and the reason the existing open order should be replaced.
- Complete proposed replacement fields: `unit`, `quantity`, `order_type`, `limit_price`, `stop_price`, `trailing_amount`, `trailing_amount_type`, `timing`, and any other fields required by the current Trade Gate contract. Use `null` only when a field is not applicable to the proposed order type, and preserve the existing order identity separately.
- Rationale/evidence: the fresh research, pricing, account context, risk checks, and other evidence supporting the proposal.
- Validation status: explicit results for identity, field completeness, supported order type, timing, quantity, pricing, buying power, and risk validation, including any failures or unknowns.
- Operator-review status: `pending` until Tyler reviews the proposal through Capital Trade Gate; proposal generation must not approve, submit, cancel, or replace an order.

The output must include an explicit `no live write` marker and must state that the proposal is not an execution instruction. The Workspace workflow only prepares and validates the proposal. Only Capital Trade Gate performs human-confirmed execution.

## Compliance Guardrails
- Manual human review through the Trade Gate is required before any Schwab order is placed.
- Keep the modeled candidate fields aligned with Schwab's off-market/evening workflow.
- Read-only Schwab account API access may ground live-account recommendations; generation and insertion must never place orders. Live placement remains Trade Gate-only after the required human approval and safeguards.
- Do not include non-Schwab brokerage venues.
- Preserve an audit trail for all candidate generation, approval, and future compliance review.
