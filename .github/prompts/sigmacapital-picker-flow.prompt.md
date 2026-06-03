# ΣCapital Weekend Trade Picker Flow Prompt

Use this prompt as the canonical instruction set for ΣCapital's weekend trade candidate generation and approval workflow.

## Context
- ΣCapital is currently Phase 1: simulated-only weekend trade research.
- All candidate generation must be weekend-only and support manual Schwab UI placement.
- The agent must consult the formal Schwab order semantics file at `f:\ΣCapital\schwabTradeInputs.txt` for permitted order types, unit rules, and timing constraints.
- No broker API integration is allowed.
- No automated order placement is allowed.
- Real-money mode (`mode: real`) is forbidden until an explicit follow-up FR is approved.

## Candidate Schema
The agent must generate trade candidates using the following fields:

- `action`: `Buy`, `Sell`, or `Sell Short`
- `unit`: `Shares` only for weekend flow
- `quantity`: positive share amount
- `order_type`: `Limit`, `Stop`, `Stop Limit`, or `Trailing Stop`
- `limit_price`: required for `Limit` and `Stop Limit`
- `stop_price`: required for `Stop` and `Stop Limit`
- `trailing_amount`: required for `Trailing Stop`
- `trailing_amount_type`: `points` or `percent` when `Trailing Stop` is selected
- `timing`: `Day`, `Day + extended hours`, or `Good till canceled`
- `execution_certainty`: `guaranteed` or `optional`
- `mode`: `simulated` (must remain `simulated` until future FR)
- `rationale`: natural-language explanation of the trade idea
- `confidence`: numeric score or percentile representing conviction
- `notes`: optional contextual details or risk considerations

## Workflow Rules
1. Generate a candidate list for the upcoming weekend only.
2. Mark only likely-to-execute picks as `execution_certainty: guaranteed`.
3. Track softer ideas with `execution_certainty: optional` but do not promote them to the active recommendation set.
4. Do not suggest units in `Dollars` for the weekend flow.
5. Use `Shares` only, and derive share quantity from available capital and risk sizing.
6. Do not propose order types outside the supported Schwab list.
7. Do not add any real-money execution instructions until a follow-up FR is approved.

## Output Format
Return candidates in a structured format that can be mapped to ΣCapital's pick table and approval gate. Each candidate should clearly include: `action`, `unit`, `quantity`, `order_type`, `limit_price`, `stop_price`, `trailing_amount`, `trailing_amount_type`, `timing`, `execution_certainty`, `mode`, `rationale`, and `confidence`.

## Compliance Guardrails
- Manual human review is required before any Schwab order is placed.
- Keep the modeled candidate fields aligned with Schwab's weekend interface.
- Do not reference or assume access to any Schwab internal or public APIs.
- Do not include non-Schwab brokerage venues.
- Preserve an audit trail for all candidate generation, approval, and future compliance review.
