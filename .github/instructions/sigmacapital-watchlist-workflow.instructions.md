---
description: "Canonical SigmaCapital deferred-symbol watchlist workflow. Use with the picker flow prompt when classifying, persisting, enriching, reviewing, or promoting watchlist observations."
applyTo: ".github/prompts/sigmacapital-picker-flow.prompt.md"
---

# SigmaCapital Watchlist Workflow

This instruction defines how the SigmaCapital picker handles promising symbols
that are not eligible for an immediate trade candidate. Watchlist observations
are research records, not recommendations, approvals, or orders.

## Runtime Wiring

The picker runtime is implemented in the SigmaCapital repository:

- `src/agents/research.py` owns candidate generation and deferred-symbol capture.
- `src/utils/watchlist.py` owns classification, persistence, re-enrichment,
  deterministic shadow replay, listing, promotion, and candidate validation.
- `src/utils/init_db.py` creates the `watchlist_observations` table and its
  `(symbol, observed_at)` index.
- `src/utils/trade_gate.py` exposes the separate review API:
  - `GET /api/watchlist`
  - `POST /api/watchlist/<observation_id>/promote`

The picker must use these runtime helpers rather than writing ad hoc JSON or
inserting directly into `trade_candidates` for watchlist-only observations.

## Picker-Cycle Contract

For every evaluated symbol:

1. Run the normal research, quote, financial-signal, sentiment, scoring, and
   risk checks first.
2. If the symbol qualifies for an immediate recommendation, preserve the
   existing `trade_candidates` path and its pending approval status.
3. If the symbol is promising but below the candidate threshold, classify it as
   `watchlist` with `eligible: false` and persist a deferred observation through
   `record_observation()`.
4. Include an evidence-backed reason explaining why it was deferred. Do not
   lower thresholds or convert a deferred observation into a candidate.
5. On a later cycle, locate the active observation and call
   `reenrich_observation()` with fresh evidence and provenance. This appends a
   new observation and must not overwrite prior history.
6. Use `shadow_replay()` for deterministic, non-writing qualification previews.
   Shadow replay must never create a candidate or invoke Trade Gate execution.

The current runtime capture path is connected to symbols from the configured
`data/watchlist.json` source. Do not describe a newly discovered off-watchlist
symbol as durably watchlisted unless the runtime has first routed it through
`record_observation()`; adding that broader discovery path requires a separate
SigmaCapital implementation change.

## Required Observation Contract

Each observation must include:

- `symbol`
- `status`: `deferred`, `watchlist`, `promoted`, or `archived`
- A nonblank deferred reason
- Complete evidence: `query`, `summary`, `sentiment`, `quote`,
  `financial_signal`, `score`, and `threshold`
- Provenance containing `source`, `signal_id`, `captured_at`, sanitized
  citations, and freshness metadata
- Freshness with `evaluated_at`, `age_seconds`, and `max_age_seconds`, where
  the age is timestamp-consistent and not greater than the maximum
- Picker batch and model information when available
- Qualification metadata, including deferred status, score, and threshold

The persistence boundary is fail-closed. Invalid, partial, stale, or
inconsistent evidence/provenance must be rejected before a database write.

## Promotion Boundary

Promotion is a human-supervised review action, not a picker action:

- Require explicit `human_confirmed: true`.
- Validate all order fields before insertion, including order-type-specific
  prices, timing compatibility, and execution-certainty mapping.
- Insert only a fresh `trade_candidates` row with `approval_status='pending'`.
- Preserve the original observation and its append-only history.
- Never approve a candidate, create an execution row, call `place_order`, or
  bypass the existing Trade Gate and real-money confirmation path.

The prompt must never instruct the picker to add a `mode` field to either
watchlist observations or `trade_candidates`.

## Review Surface

The watchlist review surface is separate from candidate review. It may expose
observation status, thesis/reason, evidence, provenance, freshness, enrichment
history, and promotion state. Rejection, archival, snooze, or promotion actions
must remain explicit and auditable; none may silently approve or execute a
trade.
