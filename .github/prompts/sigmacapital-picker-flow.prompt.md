# ΣCapital Off-Market Trade Picker Flow Prompt

Use this prompt as the canonical instruction set for ΣCapital's off-market/evening trade candidate generation and approval workflow.

## Context
- ΣCapital is currently Phase 1: simulated-only off-market/evening trade research.
- All candidate generation should prefer off-market/evening placement and support manual Schwab UI placement.
- The agent must consult the formal Schwab instruction document at `f:\⊕Workspace\.github\instructions\sigmacapital-schwab-trade-inputs.instructions.md` for permitted order types, unit rules, and timing constraints.
- No broker API integration is allowed.
- No automated order placement is allowed.
- Before proposing any candidates, confirm that a fresh ΣCapital research batch exists in `sigmacapital.db.signals` and that the latest batch is no older than four hours. If no current batch is available or it is stale, automatically run the Σcapital-research agent batch immediately and do not generate any picks until the latest Perplexity signals have been ingested and verified.
- Ensure fresh yfinance pricing is available for the candidate symbol before recommending any pick.
- Real-money mode (`mode: real`) is forbidden until an explicit follow-up FR is approved.

## Candidate Schema
The agent must generate trade candidates using the following fields:

- `symbol`: equity ticker symbol for the proposed trade
- `action`: `Buy`, `Sell`, or `Sell Short`
- `unit`: `Shares` only for off-market flow
- `quantity`: positive share amount
- `order_type`: `Limit`, `Stop`, `Stop Limit`, or `Trailing Stop`
- `limit_price`: required for `Limit` and `Stop Limit`
- `stop_price`: required for `Stop` and `Stop Limit`
- `trailing_amount`: required for `Trailing Stop`
- `trailing_amount_type`: `points` or `percent` when `Trailing Stop` is selected
- `timing`: `Day`, `Day + extended hours`, or `Good till canceled`
- `execution_certainty`: `guaranteed` or `optional`
- `estimated_cost`: the modelled order cost used to reserve buying power for guaranteed buy ideas
- `mode`: `simulated` (must remain `simulated` until future FR)
- `rationale`: natural-language explanation of the trade idea
- `confidence`: numeric score or percentile representing conviction
- `notes`: optional contextual details or risk considerations

## Workflow Rules
1. Generate a candidate list for the upcoming off-market/evening planning cycle.
2. Return no more than 5 candidates per prompt invocation.
3. Mark only likely-to-execute picks as `execution_certainty: guaranteed`.
4. Track softer ideas with `execution_certainty: optional` but do not promote them to the active recommendation set.
5. Do not suggest units in `Dollars` for the off-market flow.
6. Use `Shares` only, and derive share quantity from available capital and risk sizing.
7. Ground candidate generation in ΣCapital's local database state:
   - require a fresh research batch for every invocation. If the latest `signals` batch is missing or stale, run Σcapital-research immediately before generating picks and only continue after the new batch is confirmed.
   - the research batch must include niche off-watchlist discovery signals for new ticker ideas beyond the current watchlist and portfolio.
   - confirm the latest live yfinance pricing is fresh and current before using it to size or price candidates.
   - consult `sigmacapital.db` `signals` table for recent research signals and batch context,
   - consult `account_state` `buying_power` for available purchasing capacity,
   - consult `portfolio`, `position_valuations`, or `risk_thresholds` as needed to avoid unsupported sizing or duplicate exposures.
8. Ensure the candidate `limit_price`, `stop_price`, and `estimated_cost` are grounded in verified pricing data, using ΣCapital's trade approval gate reference pricing and fresh yfinance-based quote validation where available.
9. Do proper due diligence before proposing any pick: validate news/sentiment, confirm current market data, and avoid speculative entries based on stale or missing signals.
10. Do not suggest sell-side candidates when there are no current holdings. Use the portfolio/position data if available; if holdings cannot be confirmed, avoid Sell and Sell Short recommendations.
11. For buy candidates, estimate the expected order cost and reserve that amount against available buying power when approved.
12. Approved candidates must be treated as persisted picks: the approval gate saves them to ΣCapital's `picks` DB table and updates candidate status accordingly.
13. Do not propose order types outside the supported Schwab list.
14. Do not add any real-money execution instructions until a follow-up FR is approved.

## Output Format
Return candidates in a structured format that can be mapped to ΣCapital's pick table and approval gate. Each candidate should clearly include: `symbol`, `action`, `unit`, `quantity`, `order_type`, `limit_price`, `stop_price`, `trailing_amount`, `trailing_amount_type`, `timing`, `execution_certainty`, `mode`, `rationale`, `confidence`, and `notes`.

## Compliance Guardrails
- Manual human review is required before any Schwab order is placed.
- Keep the modeled candidate fields aligned with Schwab's off-market/evening workflow.
- Do not reference or assume access to any Schwab internal or public APIs.
- Do not include non-Schwab brokerage venues.
- Preserve an audit trail for all candidate generation, approval, and future compliance review.
