# FR-20260504-local-ollama-enablement

| Field | Value |
|-------|-------|
| **ID** | FR-20260504-local-ollama-enablement |
| **Title** | Local Ollama enablement for todo priority scoring (setup + validation) |
| **Type** | feature |
| **Projects** | 👁AI-Manifest, ⊕Workspace |
| **State** | TRIAGED |
| **Owner** | ⊕workspace-intake |
| **Opened** | 2026-05-04 |
| **Branches** | TBD |
| **PRs** | TBD |
| **Cycle timer** | 3c49c8ab-c9ab-474d-b72e-17fe7be3e787 |

## Motivation

Bulk todo rescoring currently falls back to OpenAI and has hit quota limits.
Local Ollama enablement is needed for stable, low-latency scoring and offline-capable
fallback behavior for priority workflows.

## Architecture Decision

- Ollama integration is workspace-canonical in `⊕Workspace/src/integrations/`.
- 👁AI-Manifest keeps a mirrored local client for CI/self-contained reliability.
- Priority scoring uses local Ollama first; OpenAI fallback remains enabled.

## Acceptance Criteria

### AC1 — System setup
Install Ollama system-wide on Windows and ensure persistent service availability.

### AC2 — Model standardization
Pull and validate `llama3.1:8b` as the default local scoring model.

### AC3 — Integration pattern
Add workspace canonical Ollama integration and mirror it in 👁AI-Manifest, following existing vendor client parity pattern.

### AC4 — Scorer wiring
Priority scorer resolves Ollama via the new integration path and continues to support OpenAI fallback.

### AC5 — Validation flow
Run health check, single-score smoke test, and rerun bulk scoring dry-run preview.

### AC6 — Extended comparison
Produce before/after proposed-priority distribution comparison in validation output.

### AC7 — Safety
Dry-run only in this FR (no DB writes).

## Out of Scope

- Bulk apply/write pass to update todo priorities
- Executive panel UI changes
- Removal of OpenAI fallback
- Multi-model benchmark bakeoff

## Dependencies

- Local admin rights for system-wide Ollama install
- Network access for initial model pull
- Existing scorer and bulk tooling in 👁AI-Manifest

## Tyler's Original Request

> "(local Ollama enablement), focused setup+validation flow: install/configure Ollama, pick model, run a scorer smoke test, then rerun bulk scoring preview"

## State History

| Date | State | Note |
|------|-------|------|
| 2026-05-04 | OPEN | Filed by Tyler via intake prompt |
| 2026-05-04 | TRIAGED | Scope and architecture pattern confirmed by Tyler |

## Event Log

### 2026-05-04T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened and triaged.

**Details:**
- Scope confirmed: local Ollama setup + integration + dry-run validation.
- Architecture locked: workspace-canonical integration + project-local mirror.
- Cycle timer started: `3c49c8ab-c9ab-474d-b72e-17fe7be3e787`.

**Next:** awaiting Tyler: approve scope for branch creation

## Artifacts

- **Perf runs:** `ea32f610-8868-431c-ac3f-270059d0dd77` — intake session
- **FR cycle timer:** `3c49c8ab-c9ab-474d-b72e-17fe7be3e787`
