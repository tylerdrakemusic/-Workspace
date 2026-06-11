<!-- applyTo: .github/prompts/sigmacapital-picker-flow.prompt.md -->

# ΣCapital Order-Type Tradeoff & Risk Guidance

This file is the canonical reference for selecting order types in the ΣCapital
picker flow. Use it alongside `sigmacapital-schwab-trade-inputs.instructions.md`
(which defines input fields and definitions). This file explains **when** to
use each order type, the associated **execution vs price risk tradeoffs**, and
**risk guidance** specific to ΣCapital's off-market / evening placement workflow.

---

## Core Tradeoff Axis: Execution Certainty vs Price Certainty

Every order type sits somewhere on this axis. ΣCapital candidates must declare
their `execution_certainty` field based on this classification:

> **Note on market orders:** Pure market orders carry the highest (truly
> guaranteed) execution certainty — they fill immediately at the best available
> price. However, market orders are effectively out of scope for ΣCapital's
> off-market / weekend placement workflow. Stop and Trailing Stop orders
> approximate market-order behavior *once their trigger price is reached*, giving
> them **elevated execution certainty** within the supported order types. Limit
> and Stop Limit orders prioritise **price certainty** over execution certainty.

| Order Type | Execution Certainty | Price Certainty | Best For |
|---|---|---|---|
| Stop | **Elevated** (conditional on stop price being reached; converts to market order) | Low (slippage risk) | Breakout entries, stop-loss exits |
| Trailing Stop | **Elevated** (conditional on trailing threshold being hit; converts to market order) | Low (gap/slippage risk) | Locking in gains on open positions |
| Limit | Low (may not fill even if price is reached) | **High** (fills at limit or better) | Precision entries, off-market bids |
| Stop Limit | Low (may not fill if price gaps through limit) | **High** (fills at limit or better) | Controlled breakouts with a price floor |

> **Important:** Stop and Trailing Stop orders are **conditional** — they remain dormant until the stop price is reached. The execution certainty applies only *after* the trigger price is hit; if the stop price is never reached, the order never activates. "Elevated execution certainty" means that once triggered, the resulting market order fills with near-certainty (subject to slippage), not that the order is unconditionally guaranteed to fill.

**Rule for ΣCapital picks:** use `execution_certainty: guaranteed` for Stop and
Trailing Stop orders — these provide high execution certainty *once the trigger
price is reached* and the order converts to a market order. Use
`execution_certainty: optional` for Limit and Stop Limit orders, which are
conditional on price and may not fill at all.

---

## Order-Type Selection Guidance

### Limit Order — Use When
- You have a clear target entry or exit price and are willing to miss the trade
  if the market does not reach it.
- Volatility is low-to-moderate and the stock is range-trading near support/resistance.
- The pick is rated `execution_certainty: optional` (partial fill or no fill acceptable).
- Placing off-market or evening orders where the next-day open is uncertain.
- Selling an existing position at a specific profit-taking level.

**Risk flags:**
- Will not execute if price gaps through the limit on the open.
- Partial fills are possible; track unfilled remainder separately.
- For `Day + extended hours` timing, limit-only restriction applies — do not
  assign non-Limit order types with this timing option.

---

### Stop Order — Use When
- You need a breakout entry: buying once a resistance level is confirmed broken,
  or selling once a support level is confirmed broken.
- Implementing a hard stop-loss exit on an existing position to cap downside.
- Execution certainty matters more than execution price.

**Risk flags:**
- Converts to a market order at the stop price — slippage is possible,
  especially at the open after weekend placement.
- Do not use for illiquid tickers where the spread is wide, as market order
  execution can be significantly worse than the stop price.
- Avoid pairing a Buy Stop with an aggressive stop price near the current ask;
  the order may trigger immediately.
- For ΣCapital off-market flow: prefer Limit or Stop Limit for directional
  entries unless the breakout thesis explicitly requires unconditional execution.

---

### Stop Limit Order — Use When
- You want the discipline of a breakout trigger (Stop) but need price control
  on execution (Limit).
- The stock is liquid enough that the gap between stop price and limit price is
  unlikely to be skipped in normal trading.
- Willing to accept a non-fill in exchange for avoiding bad-fill slippage.

**Risk flags:**
- The primary risk is **non-execution**: if price gaps from below the stop to
  above the limit in one move (common on gap opens), the order will not fill.
- Set the limit price close to the stop price for liquid large-caps;
  widen the limit offset for smaller or more volatile names.
- For Sell Stop Limit: ensure limit price ≤ stop price.
- For Buy Stop Limit: ensure limit price ≥ stop price.
- Treat as `execution_certainty: optional` unless market conditions make
  a gap-through extremely unlikely.

---

### Trailing Stop Order — Use When
- You hold an open position with unrealized gains and want to lock in profits
  while allowing further upside.
- The trend is intact but you want to set-and-forget the exit trigger.
- You are comfortable that execution is market-quality (no price guarantee).

**Risk flags:**
- Trailing amount calibration is critical: too tight → early trigger on normal
  pullbacks; too wide → large drawdown before exit.
- Percentage-based trailing amounts (`%`) are usually preferable to point-based
  for positions in higher-priced stocks; points work well for low-priced names.
- Not suitable as an entry order type for ΣCapital's off-market picks workflow —
  use only for exit management on positions already held.
- Gap-down opens can cause execution well below the trailing stop level.
- For ΣCapital picks, always note the trailing amount and type in `notes`
  field so Tyler can verify before placing on Schwab.

---

## Risk Guidance by Market Context

### Off-Market / Weekend Placement (Primary ΣCapital Context)
- **Prefer Limit orders** for entries: price is uncertain at the next open, and
  a limit protects against gap-up overpay on buy or gap-down undersell on sell.
- Stop orders placed over a weekend become active at Monday open as market
  orders — use only when the breakout thesis is robust enough to absorb slippage.
- Stop Limit orders provide the best balance of trigger discipline + price
  control for off-market placements; recommended for most breakout-style entries.
- Trailing Stops placed over a weekend trail from the first available bid/ask
  at market open — verify the trailing amount is calibrated to handle the
  open-session volatility, not just overnight range.

### High-Volatility / Earnings Context
- Avoid Stop orders around earnings; gap risk is extreme.
- Limit orders with a realistic limit price (not too aggressive) are preferred.
- Stop Limit orders are acceptable if limit offset is wide enough (≥1–2% for
  large-caps, ≥3–5% for small/mid-caps).
- Trailing Stops should not be initiated into an earnings event; confirm
  earnings date before recommending a trailing stop on an open position.

### Low-Liquidity / Small-Cap Context
- Never use Stop orders (market execution) on tickers with low average volume
  (< 500k ADV). Slippage risk is prohibitive.
- Limit orders only; accept the non-fill risk.
- Stop Limit with a tight limit offset is acceptable only if the ticker
  regularly trades through narrow spreads.

---

## Picker Flow Decision Protocol

When assigning an order type to a candidate, the picker must follow this
decision sequence:

1. **Determine direction and intent:**
   - Entry (new position)? → Limit preferred; Stop/Stop Limit for breakout.
   - Exit (take profit)? → Limit preferred.
   - Exit (stop-loss)? → Stop or Stop Limit.
   - Trailing exit (lock gains)? → Trailing Stop only for existing holdings.

2. **Assess execution certainty requirement:**
   - Is the thesis contingent on hitting an exact price? → Limit or Stop Limit.
   - Is the thesis contingent on confirming a price level is broken? → Stop or Stop Limit.
   - Is filling more important than price? → Stop (but document slippage risk in `notes`).

3. **Check timing compatibility:**
   - `Day + extended hours` → Limit only.
   - `Day` or `Good till canceled` → any supported type.

4. **Set `execution_certainty`:**
   - `guaranteed` → Stop or Trailing Stop (elevated execution certainty *once the stop price is triggered*; the order remains dormant and inactive until that trigger is reached).
   - `optional` → Limit or Stop Limit (conditional on price; may not fill even if the target level is approached).

5. **Populate required fields per order type:**
   - Limit: `limit_price` required.
   - Stop: `stop_price` required.
   - Stop Limit: both `stop_price` and `limit_price` required.
   - Trailing Stop: `trailing_amount` and `trailing_amount_type` required.

6. **Document risk in `notes`:**
   - State the primary risk (e.g., "gap-fill risk at open", "non-fill risk if
     price gaps through limit", "slippage risk at market open").
   - For Trailing Stop: state the trailing amount rationale.

---

## Hard Rules

- Do **not** recommend a Stop order on a ticker with ADV < 500k.
- Do **not** pair `Day + extended hours` timing with any order type other than
  Limit.
- Do **not** use Trailing Stop as an entry order type.
- Do **not** set `execution_certainty: guaranteed` on a Limit or Stop Limit
  order.
- Do **not** set `execution_certainty: optional` on a Stop or Trailing Stop
  order. Stop and Trailing Stop orders provide elevated execution certainty *once
  triggered* — but note that activation is conditional on the stop price being
  reached; if the price never hits the stop, the order never activates.
- Always include a primary risk flag in `notes` for any Stop or Trailing Stop
  recommendation.
- Always cross-check `sigmacapital-schwab-trade-inputs.instructions.md` for
  the exact field requirements of the chosen order type before finalizing a
  candidate.
