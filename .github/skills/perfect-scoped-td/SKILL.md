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
2. Use `update_priority()` when changing priority so `priority_history` is
   recorded. Do not change `done` or `closed_at` through this skill.
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
- It does not modify unrelated todos or repair conflicts silently.
- It does not create fallback files when either database is unavailable.