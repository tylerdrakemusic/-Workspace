<!-- applyTo: .github/prompts/*.prompt.md -->

# ΣCapital Schwab Trade Input Semantics

This file is the canonical, formalized instruction reference for ΣCapital agents and prompts that must model Schwab weekend order inputs.

## Supported Order Actions
- Buy
- Sell
- Sell Short

## Unit Rules
- Shares only for weekend flow.
- Dollars may be displayed by the Schwab UI, but ΣCapital picks must generate share quantities only for weekend execution.

## Supported Order Types

### Limit Order
**Inputs:** Action, Unit, Quantity, Limit Price, Timing

Definition:
- Buy or Sell only at the specified limit price or better.
- Execution is not guaranteed.
- If executed, the execution price will be the limit price or better.
- Sell orders execute at or above the limit price.
- Buy orders execute at or below the limit price.

### Stop Order
**Inputs:** Action, Unit, Quantity, Stop Price, Timing

Definition:
- Becomes a market order once the investment trades at or through the stop price.
- Buy stops are entered above the current market price; if the instrument trades at or above the stop price, the order becomes a market buy order.
- Sell stops are entered below the current market price; if the instrument trades at or below the stop price, the order becomes a market sell order.

### Stop Limit Order
**Inputs:** Action, Unit, Quantity, Stop Price, Limit Price, Timing

Definition:
- Becomes a limit order once the investment trades at the designated stop price.
- Execution is not guaranteed.
- Sell stop limit: stop price below current price and limit price less than or equal to stop price.
- Buy stop limit: stop price above current price and limit price above or equal to stop price.

### Trailing Stop Order
**Inputs:** Action, Unit, Quantity, Trailing Amount (% or points), Timing

Definition:
- The stop price moves dynamically as the bid/ask price moves by the specified trailing amount.
- For Sell trailing stops: stop sits below the bid price, rising as the bid price rises and remaining fixed if the bid falls.
- For Buy trailing stops: stop sits above the ask price, falling as the ask price falls and remaining fixed if the ask rises.
- If price retraces the trailing amount, the stop triggers and becomes a market order for the specified quantity.

## Timing Options
- **Day**
  - Active only for the regular trading session: 9:30 a.m. to 4:00 p.m. ET.
  - Expires at market close if not filled or canceled.
  - Orders placed after 4:00 p.m. ET, during the weekend, or on holidays become active the next trading day.

- **Day + extended hours**
  - Active for all equity trading sessions from 7:00 a.m. to 8:00 p.m. ET.
  - Only available for limit orders.
  - Orders placed after 8:00 p.m. ET, during the weekend, or on holidays become active the next trading day.

- **Good till canceled**
  - Active for up to 180 calendar days (unless filled or canceled).
  - Active only during regular trading hours: 9:30 a.m. to 4:00 p.m. ET.
  - Orders placed after 4:00 p.m. ET, during the weekend, or on holidays become active the next trading day.

## Execution Certainty Notes
- Limit and Stop Limit orders are conditional and may not execute.
- Stop orders trigger market execution once the stop price is reached.
- Trailing Stops move dynamically and trigger market execution when the trailing threshold is hit.

## Cost Basis Methods (Sell Orders Only)
ΣCapital should not assume cost basis method selection automatically, but the Schwab interface can allow one-time overrides:

- FIFO (First In First Out) — default account method.
- LIFO (Last In First Out).
- High Cost.
- Low Cost.
- Tax Lot Optimizer™.
- Specified Lots (manual lot selection; new lots may be ineligible if established today).

> Note: Cost basis method is only relevant for sell execution and tax reporting. For ΣCapital's initial weekend simulated flow, keep cost-basis metadata optional and do not auto-select it unless the user requests it.
