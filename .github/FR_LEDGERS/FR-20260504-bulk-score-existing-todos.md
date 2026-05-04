# FR-20260504-bulk-score-existing-todos

| Field | Value |
|-------|-------|
| **ID** | FR-20260504-bulk-score-existing-todos |
| **Title** | Bulk-score existing todos |
| **Type** | feature |
| **Projects** | 👁AI-Manifest |
| **State** | TRIAGED |
| **Owner** | ⊕workspace-intake |
| **Opened** | 2026-05-04 |
| **Branches** | TBD |
| **PRs** | TBD |
| **Cycle timer** | 68bb320e-fb58-4d31-8abe-81768fad0baf |

## Motivation

Existing open todos have mixed/manual priorities and legacy defaults, which weakens
cross-project ranking quality in the executive workflow. We need a one-time bulk
recalibration pass so current backlog priorities are coherent.

## Acceptance Criteria

### AC1 — Bulk scoring CLI command
Add a CLI workflow in 👁AI-Manifest that bulk-scores existing todos.

### AC2 — Target scope
Only open todos (`done=0`) are targeted; include all project keys in the same DB.

### AC3 — Overwrite policy
Re-score all targeted rows and overwrite existing priority values.

### AC4 — Safety gate
Default flow is dry-run preview first, then explicit confirmation before writes.

### AC5 — Resilience
If a row fails to score, skip it, continue processing, and report failures.

### AC6 — Summary output
Print a final summary with scanned/updated/skipped/failed counts.

## Out of Scope

- Executive panel UI button for bulk scoring
- DB audit table
- CSV/JSON audit artifact export
- Changes to additive blend routing model

## Risk

Medium — operation can rewrite many priorities at once.

## Dependencies

- `f:\👁AI-Manifest\src\utils\priority_scorer.py`
- `f:\👁AI-Manifest\src\utils\todos_db.py`
- `OPENAPI_TOKEN` when Ollama is unavailable

## Tyler's Original Request

> "bulk-score exsisting todos"

## State History

| Date | State | Note |
|------|-------|------|
| 2026-05-04 | OPEN | Filed by Tyler via intake prompt |
| 2026-05-04 | TRIAGED | Scope confirmed by Tyler |

## Event Log

### 2026-05-04T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened and triaged.

**Details:**
- Scope confirmed in intake interview and Tyler confirmation.
- Bulk scoring will run as CLI-first flow with dry-run safety.
- Cycle timer started: `68bb320e-fb58-4d31-8abe-81768fad0baf`

**Next:** awaiting Tyler: approve scope for branch creation

## Artifacts

- **Perf runs:** `4bd43d31-aa27-46e0-b141-aede795c38b6` — intake session
- **FR cycle timer:** `68bb320e-fb58-4d31-8abe-81768fad0baf`
