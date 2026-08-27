---
name: perfect-scoped-td
description: Resolve and refine a workspace todo against the manifest todo database and FR ledger, then synchronize approved changes.
disable-model-invocation: true
argument-hint: "A workspace todo ID, todo text, or approved FR ID"
---

# Perfect Scoped Todo

Turn a workspace work item into an implementation-ready todo while keeping
the manifest todo database and feature-request ledger aligned. This skill is
workspace-specific and approval-gated.

## Sources Of Truth

Use both sources when the input can be resolved to both:

- `f:\👁AI-Manifest\src\data\manifest_todos.db`
- `f:\⊕Workspace\src\data\fr_ledgers.db`, accessed through
  `f:\⊕Workspace\src\utils\fr_cli.py`

Use the existing `src.utils.todos_db` helpers for todo reads and writes where
they provide the needed operation. Use parameterized SQLite statements for
fields without a helper. Use `fr_cli.py get <FR-ID>` for FR reads and
`fr_cli.py record-event` for an approved event record.

Decision metadata follows the workspace contract in
`src/utils/todo_decision_metadata.py` and
`docs/todo-decision-metadata-standard.md`. Consumers must use that validator
and field vocabulary rather than defining a second schema.

The canonical fields are `expected_value`, `user_or_system_benefit`,
`strategic_alignment`, `confidence`, `cost_of_delay`,
`primary_benefit_category`, optional `secondary_benefit_category`,
`benefit_summary`, `justification`, and `evidence`. Categories are `user`,
`system`, `strategic`, `revenue`, `risk_reduction`, `learning`, `maintenance`,
and `compliance`. Scores use the inclusive 1-10 scale with anchors from
minimal at 1 to exceptional at 10. Scores of 8 or more require evidence, and
scores of 9 or 10 require at least two evidence items. Never translate legacy
metadata into canonical values or invent missing historical values.

## Input

Accept one of:

- An existing todo ID.
- Todo text that can be matched to an open todo.
- An approved FR ID.

If an ID is ambiguous, missing, closed, or not found, stop and report the
handshake failure. Do not guess, create a duplicate, or fall back to a local
file.

## Handshake

Perform this read-only sequence before drafting:

1. Resolve the input to a todo and/or FR.
2. Load the complete todo row, including `project`, `source`, `done`,
   `priority`, `autonomy_level`, `fr_id`, `rationale`,
   `implementation_hints`, `context_snapshot`, `estimated_effort`, and
   `dependencies`.
3. If an FR is present, load its state and event history with `fr_cli.py get`.
4. Check consistency:
   - A todo's `fr_id`, when present, must identify the same FR being used.
   - The todo must not be marked done while the linked FR is active unless the
     input explicitly explains the intentional mismatch.
   - The todo project must be one of `music`, `life`, `capital`, `quantum`,
     `ai_manifest`, or `workspace`.
   - Do not treat an FR as approved unless its current state and event history
     establish that approval.
5. Surface conflicts, stale links, missing IDs, and data that would be
   overwritten before proposing any changes.

## Refinement

Preserve the source intent while producing:

- A concise implementation-ready `text` value.
- A concrete user outcome and problem statement.
- Explicit scope and out-of-scope boundaries.
- Observable acceptance criteria.
- Dependencies, blockers, assumptions, risks, and validation.
- Values for `rationale`, `implementation_hints`, `context_snapshot`,
  `estimated_effort`, and `dependencies`.
- A recommended `priority`, `source`, and `autonomy_level` only when the
  evidence supports changing them.

Do not invent project facts, FR approvals, dependencies, or implementation
details. Preserve existing fields when the input does not justify a change.

### Oversized scope

Treat a todo as oversized when it spans multiple projects, introduces a schema
or integration, or contains more than three independently testable outcomes.
For oversized scope, propose an approval-gated child chain: preserve the parent
as the outcome anchor, list implementation-ready children, and show the graph
edges and inherited confirmed FR link before writing. Do not create child rows,
edges, or FR links until Tyler explicitly approves the full decomposition.

## Approval Gate

Show a handshake report and proposed mutations before writing:

```markdown
## Todo/FR Handshake
- Todo: <id and current status>
- FR: <id, state, or none>
- Project: <canonical key>
- Consistency: <aligned, conflict, or unresolved>

## Proposed Todo
<implementation-ready todo>

## Proposed Database Changes
- <table, record ID, field, old value, new value>

## Proposed FR Event
- <event type and summary, or none>
```

Ask for explicit confirmation of the listed mutations. A request to “perfect”
or “sync” a todo is not by itself permission to write.

## Approved Writes

After confirmation only:

1. Update the existing todo using a transaction and parameterized values.
   When the approved refinement transaction succeeds, set the nullable
   `perfected_at` field to the current UTC timestamp in that same transaction.
   A denied, unapproved, or failed refinement must not set or update
   `perfected_at`; it remains null unless a prior approved successful
   refinement already stamped it.
2. Use `update_priority()` when changing priority so `priority_history` is
   recorded. Do not change `done` or `closed_at` through this skill.
   Decision metadata may provide advisory priority guidance only; it must
   never automatically mutate `priority` or `priority_history`. Applying a
   recommendation remains an explicit, human-approved priority operation.
3. Set `fr_id` only to a confirmed existing FR ID. Never create an FR or
   transition its state here.
4. If an FR event was explicitly approved, record it with `fr_cli.py` after the
   todo transaction succeeds. Never claim an event was recorded if the command
   failed.
5. Re-read both databases and report the persisted values and any remaining
   inconsistency.

If the input is text with no matching todo, present a proposed new todo and
wait for approval. Insert it through `todos_db.add_todo()` with the approved
rich fields, then re-read it by its returned ID. Do not insert duplicates.

If any write fails, report the error, do not retry with a different mutation,
and do not partially continue the handshake.

## Boundaries

- This skill does not implement code, create branches, or open FRs.
- It does not transition FR states or mark todos complete.
- Do not create FR transitions from todo code; FR state changes remain owned by
   the governed FR workflow and its CLI.
- It only stamps `perfected_at` for an approved successful refinement
   transaction; failed or unapproved refinement does not stamp it.
- Decision metadata migration is additive and idempotent. Legacy rows retain
   null metadata, and no historical values may be fabricated or backfilled.
- Validated assessments replace current metadata and append immutable history;
   incomplete high-impact assessments and malformed evidence are rejected.
- It does not modify unrelated todos or repair conflicts silently.
- It does not create fallback files when either database is unavailable.