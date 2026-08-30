# Copilot Model Selection and Delegation

This feature selects an available Copilot model for `tdd`, `qa`, or `review`
at a complexity tier of `light`, `standard`, or `heavy`. Contracts are
versioned and metadata-only. They may contain model/provider identity,
availability, benchmark provenance, pricing provenance, latency, retries,
failure state, and accepted-outcome state. They must never contain prompts,
task payloads, source code, medical data, financial data, or task outputs.

## Availability

`CachedInventory` prefers a supported Copilot or VS Code enumeration provider.
The cache has a freshness window. A stale cache is returned only as
`stale-fallback`, and live preflight remains required before delegation. If no
supported enumeration or cache exists, selection and dispatch are fail-closed.

The repository does not claim an undocumented Copilot activation API. A live
consumer must implement the narrow `DelegationConsumer` boundary. The default
`UnsupportedDelegationConsumer` always fails closed until a supported consumer
is supplied.

## Selection

Selection first applies hard gates for availability, role/tier coverage,
comparable benchmark evidence, quality, confidence, and provider health. Only
then does it rank observed cost per accepted outcome plus latency, retry,
reliability, and load penalties. Ties are deterministic by score, provider,
and model identifier. Provider diversity is preferred when an equivalent
candidate is available. Hysteresis prevents small score changes from causing
churn, and candidate cooldowns suppress recently unhealthy routes.

## Delegation and overrides

Delegation retries only within the manifest's bounded retry limit, then tries
the deterministic failover list, then a same-FR, same-role last-known-good
manifest. A scoped override must identify the FR, may identify a role, names a
model, includes a reason, and expires. Invalid scope, failed preflight, missing
evidence, and unsupported consumers are fail-closed. This system never mutates
agent YAML or frontmatter.

## Telemetry and proof

`TelemetryRecord` correlates FR, role, tier, model, provider, latency, retries,
failure, accepted outcome, and pricing provenance. Use the existing
`copilot_cost.py` and `fr_cost_lifecycle.py` for cost calculation and FR ledger
reconciliation, and `perf_cli.py` for run timing. Persist only ledger-compatible
metadata. `shadow_replay` exercises selection without activation and is the
preferred dry-run for FR-flow validation.