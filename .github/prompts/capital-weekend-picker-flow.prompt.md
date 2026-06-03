# ΣCapital Weekend Picker Flow

Run the `Σcapital-orchestrator` agent to execute the weekend picker workflow for ΣCapital.

## Required Input Source

- Use the formal Schwab instruction file at `f:\ΣCapital\schwabTradeInputs.txt` as the source of truth for execution constraints and order-entry formatting.

## Behavior

- Generate candidate weekend picks from currently available ΣCapital signals.
- Apply risk and compliance checks before finalizing picks.
- Return a concise weekend action plan for manual placement only.
- Include a reminder that all order entry must follow `f:\ΣCapital\schwabTradeInputs.txt`.

## Example Invocations

- "Run the ΣCapital weekend picker flow"
- "Generate this weekend's ΣCapital picks and format output using Schwab instructions"
