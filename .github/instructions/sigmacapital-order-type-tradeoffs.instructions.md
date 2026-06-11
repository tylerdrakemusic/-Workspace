<!-- applyTo: .github/prompts/*.prompt.md -->

# ΣCapital Schwab Order Type Tradeoffs and Risk Factors

Use this document as the canonical ΣCapital guidance for choosing between supported Schwab order types in the off-market/evening picker flow.

## Purpose
- Provide agent-level reasoning for `Limit`, `Stop`, `Stop Limit`, and `Trailing Stop` orders.
- Surface advantages, disadvantages, and risk factors for each order type.
- Keep the guidance static and prompt-driven, not a new candidate data field.
- Preserve the Phase 1 rule: only simulated candidate generation, no automated Schwab order placement.

## Supported Order Types

### Limit Order
- Advantage: keeps price control and prevents execution above (buy) or below (sell) a specified price.
- Disadvantage: execution is not guaranteed, especially for off-market/evening ideas or when the limit price is too aggressive.
- Risk factors:
  - Stale limit prices across evening and next-session gaps.
  - Low liquidity near market open/close may leave the order unfilled.
  - Unexpected price moves can make a once-reasonable limit unrealistic.
- Best use when the candidate thesis is price-specific and staying within a defined entry/exit level matters more than immediate execution.

### Stop Order
- Advantage: provides a market-triggered execution once the stop price is reached, which is useful for momentum entries or risk-managed exits.
- Disadvantage: once triggered, there is no control over the fill price; the actual execution price may be worse during fast moves or gaps.
- Risk factors:
  - Gap risk between the trigger and actual fill price.
  - Wide spreads and thin liquidity in extended-hours sessions.
  - After-hours quote noise can produce false triggers or rapid activation.
- Best use when the priority is getting into or out of a position once a price level is breached and the trade thesis tolerates price uncertainty.

### Stop Limit Order
- Advantage: preserves price control by combining a stop trigger with a limit on execution price.
- Disadvantage: it may never execute if the market moves past the limit price after the stop is triggered.
- Risk factors:
  - Mispriced stop/limit pair can either never fill or fill at an undesirable level.
  - Off-market transitions amplify the chance that the order triggers but the limit is missed.
  - More complexity means more opportunity for configuration errors.
- Best use when you want a disciplined trigger but also need a hard price boundary to avoid uncontrolled fills.

### Trailing Stop Order
- Advantage: automatically adjusts the stop level in the direction of a winning move, helping protect gains while leaving room for upside.
- Disadvantage: does not guarantee the exit price, and it can be triggered prematurely by volatility or whipsaw.
- Risk factors:
  - Volatility in thin after-hours or open sessions can stop the order out on a short reversal.
  - A too-tight trailing distance may kick the order too early; a too-wide distance may leave too much downside risk.
  - Gaps can still cause fills far from the last quoted price when the stop is triggered.
- Best use for protecting profits on an established position or for a defensive exit that adjusts with favorable price movement.

## Application Guidance for the ΣCapital Picker Flow
- `Limit` is the preferred default for buy-side ideas when the desired entry price is clear and the trade can be optional rather than guaranteed.
- `Stop` is useful for disciplined entries or exits when the trade thesis is tied to a breakout or downside breach and price certainty is secondary.
- `Stop Limit` is appropriate when a triggered execution is desirable but a maximum acceptable fill price is also required.
- `Trailing Stop` is best reserved for protecting upside on existing directional exposure rather than for speculative new entries.

## Execution Certainty and Timing
- Map `execution_certainty: guaranteed` to order types and price levels that are likely to execute under the current market context.
- Treat `execution_certainty: optional` as the safer designation for `Limit`, `Stop Limit`, and `Trailing Stop` setups that can legitimately fail to fill.
- Always consider the timing rule: `Day`, `Day + extended hours`, or `Good till canceled` affect how long the order remains active and how much market risk the order carries.

## Risk Factor Summary
- Price control vs. execution risk is the primary tradeoff for all supported Schwab order types.
- Off-market/evening candidate generation must balance the desire for a clean entry/exit level with the reality that execution likelihood can be lower outside regular liquidity windows.
- The agent should favor order types that match the candidate’s thesis and risk posture, not simply the most familiar order type.
