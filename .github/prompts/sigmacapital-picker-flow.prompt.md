---
mode: Σcapital-orchestrator
---
# ΣCapital Off-Market Trade Picker Flow Prompt

Use this prompt as the canonical instruction set for ΣCapital's off-market/evening trade candidate generation and approval workflow.

## Context
- ΣCapital is currently Phase 1: simulated-only off-market/evening trade research.
- All candidate generation should prefer off-market/evening placement and support manual Schwab UI placement.
- The agent must consult the formal Schwab instruction document at `f:\⊕Workspace\.github\instructions\sigmacapital-schwab-trade-inputs.instructions.md` for permitted order types, unit rules, and timing constraints.
- The agent must consult the order-type tradeoff and risk guidance at `f:\⊕Workspace\.github\instructions\sigmacapital-order-type-tradeoffs.instructions.md` when selecting an order type for each candidate. This document governs when to use each order type, execution vs price risk tradeoffs, market-context rules, and the required `execution_certainty` classification.
- Read-only Schwab account API access (live buying power) is permitted to ground high-confidence `mode: real` candidate proposals (FR-20260711). Order-placement/write APIs (`place_order`, `replace_order`, `cancel_order`) remain fully out of scope.
- No automated order placement is allowed.
- Before proposing any candidates, confirm that a fresh ΣCapital research batch exists in `sigmacapital.db.signals` and that the latest batch is no older than four hours. If no current batch is available or it is stale, automatically run the Σcapital-research agent batch immediately and do not generate any picks until the latest Perplexity signals have been ingested and verified.
- Ensure fresh yfinance pricing is available for the candidate symbol before recommending any pick.
- Real-money mode (`mode: real`) may be proposed by the research agent for high-confidence picks grounded in live (read-only) Schwab account buying power (FR-20260711). Approval/execution of a `mode: real` candidate still requires Tyler's explicit real-money authorization (`AUTHORIZED_REAL_MONEY_FR_ID`) to be set by a future FR — until then the approval gate blocks real-money confirmation even though a proposal may appear.

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
- `execution_certainty`: `elevated` or `optional`
- `estimated_cost`: the modelled order cost used to reserve buying power for elevated buy ideas
- `mode`: `simulated` by default; the research agent may propose `real` for high-confidence picks grounded in live Schwab buying power (FR-20260711). Approval/execution of a `real` candidate still requires Tyler's explicit real-money authorization FR before it can complete.
- `model`: the LLM model that generated the pick (e.g. `Claude Opus 4.8`, `gpt-5`). The agent must stamp every candidate with the exact model it is running on so each pick's provenance is captured and later surfaced on the portfolio holdings view.
- `rationale`: natural-language explanation of the trade idea
- `confidence`: numeric score or percentile representing conviction
- `notes`: optional contextual details or risk considerations

## Workflow Rules
1. Generate a candidate list for the upcoming off-market/evening planning cycle.
2. Return no more than 5 candidates per prompt invocation.
3. Mark only likely-to-execute picks as `execution_certainty: elevated`.
4. Track softer ideas with `execution_certainty: optional` but do not promote them to the active recommendation set.
5. Do not suggest units in `Dollars` for the off-market flow.
6. Use `Shares` only, and derive share quantity from available capital and risk sizing.
7. Ground candidate generation in ΣCapital's local database state:
   - require a fresh research batch for every invocation. If the latest `signals` batch is missing or stale, run Σcapital-research immediately before generating picks and only continue after the new batch is confirmed.
   - the research batch must include niche off-watchlist discovery signals for new ticker ideas beyond the current watchlist and portfolio.
   - confirm the latest live yfinance pricing is fresh and current before using it to size or price candidates.
   - consult `sigmacapital.db` `signals` table for recent research signals and batch context,
   - confirm each research symbol has financial signal enrichment in `sigmacapital.db.signals` before candidate scoring. If the financial signal is missing, enrich the symbol with earnings and fundamentals data before using it in a pick.
   - consult `account_state` `buying_power` for available purchasing capacity,
   - consult `portfolio`, `position_valuations`, or `risk_thresholds` as needed to avoid unsupported sizing or duplicate exposures.
8. Ensure the candidate `limit_price`, `stop_price`, and `estimated_cost` are grounded in verified pricing data, using ΣCapital's trade approval gate reference pricing and fresh yfinance-based quote validation where available.
9. Do proper due diligence before proposing any pick: validate news/sentiment, confirm current market data, and avoid speculative entries based on stale or missing signals.
10. Do not suggest sell-side candidates when there are no current holdings. Use the portfolio/position data if available; if holdings cannot be confirmed, avoid Sell and Sell Short recommendations.
11. For buy candidates, estimate the expected order cost and reserve that amount against available buying power when approved.
12. Approved candidates must be treated as persisted picks: the approval gate saves them to ΣCapital's `picks` DB table and updates candidate status accordingly.
13. Do not propose order types outside the supported Schwab list.
14. The research agent may propose `mode: real` candidates for high-confidence picks informed by live Schwab account data (FR-20260711), but do not add any real-money order-placement/execution instructions — approval of a `mode: real` candidate still requires Tyler's explicit real-money authorization FR before it can complete.
15. Stamp every generated candidate with the `model` field set to the exact LLM model the agent is running on. This provenance flows through approval into `execution_history` and the `portfolio` row, where it is surfaced on the portfolio holdings view. When the same holding is bought under more than one model, the portfolio `model` value accumulates a deduped, comma-separated list (e.g. `raptor, Claude Opus 4.8`).

## Output Format
Return candidates in a structured format that can be mapped to ΣCapital's pick table and approval gate. Each candidate should clearly include: `symbol`, `action`, `unit`, `quantity`, `order_type`, `limit_price`, `stop_price`, `trailing_amount`, `trailing_amount_type`, `timing`, `execution_certainty`, `mode`, `model`, `rationale`, `confidence`, and `notes`.

## Compliance Guardrails
- Manual human review is required before any Schwab order is placed.
- Keep the modeled candidate fields aligned with Schwab's off-market/evening workflow.
- Read-only Schwab account API access (live buying power) is permitted solely to ground high-confidence `mode: real` proposals (FR-20260711); do not reference or assume access to any Schwab order-placement/write APIs.
- Do not include non-Schwab brokerage venues.
- Preserve an audit trail for all candidate generation, approval, and future compliance review.
