---
name: new-fr
description: "Use when starting intake for a new feature request (FR); route triage through the workspace overseer and follow the governed feature-request workflow."
---

# New Feature Request

Confirm you are acting as `⊕workspace-overseer`. If not, hand off to that agent
before continuing. Treat the user's feature request as the title and any added
context as notes. Ask for a title only when none was supplied.

## Intake

1. Inspect the workspace with available tools before taking action. Prefer
   existing MCP capabilities and avoid ad hoc queries or scripts.
2. Infer the feature type, affected projects, motivation, risk, dependencies,
   and out-of-scope boundaries from the request and project context.
3. Before presenting a scope draft, read
   `.github/instructions/bdd-workflow.instructions.md` and classify whether
   the request changes observable behavior. For behavior-changing FRs, write
   explicit Given/When/Then acceptance scenarios and resolve missing context
   or outcomes before asking Tyler to approve scope. Include the scenarios in
   the complete FR draft and confirmation block. Pure documentation,
   housekeeping, and behavior-neutral refactors are exempt; for mixed requests,
   write scenarios for the behavior-changing parts only.
4. Cross-reference open TODOs with the governed manifest-coordination tools:
   call `mcp_manifest-coor_list_open_todos(project=<inferred_project>)`, then
   `mcp_manifest-coor_read_todo(todo_id=<candidate_id>)` for relevant matches.
   Surface matches in the Phase B scope card under `Related todos`. Only after
   Tyler confirms a match, call
   `mcp_manifest-coor_link_confirmed_todo_to_fr(todo_id=<matched_id>,
   fr_id=<FR-ID>, confirmed=true)`. Skip this silently when there are no
   matches. Never query or update the manifest database with SQL.
5. Ask only about fields that cannot be inferred. If the request is vague or
   medium/high risk, invoke the `grill-me` skill and ask one question at a
   time, offering a recommended answer for each.
6. Present a complete FR draft with all fields filled in one confirmation
   block. Ask: "Does this look right? Confirm, or tell me what to change."
7. On amendments, update the draft and confirm it again. On confirmation,
   proceed to Phase B triage: ledger, registry, and cycle timer.
8. Register the FR in the database through `fr_cli.py open`. For a
   behavior-changing FR, persist the approved scenarios unchanged as its
   acceptance criteria through the canonical `fr_cli.py
   set-acceptance-criteria` command before implementation is dispatched. The
   database is the sole source of truth; do not create a Markdown file in
   `.github/fr/`.

## Blocking Approval Voice

When the workflow reaches a blocking approval that genuinely requires Tyler's
input, keep the normal text request authoritative and use voice only as a
governed diagnostic channel. The injected AI-Manifest MCP capability must call
`start_streaming_tts`, poll `streaming_tts_status` to a bounded deadline, and
call `cancel_streaming_tts` for timeout, cancellation, or interrupted cleanup
when a session exists.

This capability is injected and governed. Do not call ElevenLabs directly,
create audio artifacts, make arbitrary MCP/SQL calls, or use the durable
repository-voice queue as a fallback for this approval path. Provider,
streaming, audio, and cleanup errors are fail-open: continue the text
workflow, preserve its state, and treat voice results as diagnostic only.
Ordinary status narration is unauthorized and out of scope.

## TODO Execution State Contract

Every executable parent and child TODO created or adopted by this flow must
persist and update exactly one canonical execution state:
`queued`, `claimed`, `running`, `completed`, `failed`, `cancelled`, or `stale`.

Use these `workspace-coordination` MCP tools with the listed inputs:

- `todo_register_queued(todo_id, idempotency_key, fr_id?)`
- `todo_claim(todo_id, worker_id, claim_idempotency_key, fr_id?)`
- `todo_heartbeat(todo_id, worker_id, lease_token)`
- `todo_fail(todo_id, worker_id, lease_token, error)`
- `todo_retry(todo_id)`
- `todo_cancel(todo_id, worker_id, lease_token)`
- `todo_recover_stale()`
- `todo_takeover(todo_id, worker_id, approved)`
- `todo_complete(todo_id, worker_id, lease_token, validated_handoff, handoff_evidence)`
- `todo_get(todo_id)` and `todo_events(todo_id)` for read-only inspection.

The server derives timestamps, worker-capacity limits, lease duration, and
retry limits from policy. Generate `claim_idempotency_key` from at least 32
random bytes (for example, `secrets.token_urlsafe(32)`) and keep it private;
only the same worker with that key can replay a claim and recover its existing
lease. Only claim and approved takeover return a `lease_token`; keep it private
and pass it only to that worker's heartbeat, failure, cancellation, or
completion call. Takeover also requires `takeover_enabled` in policy and
`approved=true`.

Use these rules when coordinating work:

- Persist `queued` before dispatch, then update durable state for claim,
  heartbeat, retry, failure, cancellation, stale recovery, and takeover.
- Set `completed` only after the handoff has been validated and its required
  evidence is available. A status message or coordination event is not a
  validated handoff.
- Keep branch, worktree, and integration conflicts as coordination events.
  Do not rewrite execution state unless the execution itself is invalid.
- Parent aggregation must reuse the existing `parent_join_state` precedence;
  do not invent a second parent state reducer.
- Before advancing the FR, verify every executable parent and child has a
  persisted state and that any `completed` TODO has a validated handoff.

If the FR is decomposed into child TODOs, record the required child IDs and
join criteria in the FR plan. Incomplete child work or join bookkeeping does
not block technical progression through `FUNCTIONAL_QA`, `ARCHITECTURE_REVIEW`,
`REVIEW_REQUESTED`, or `AUTO_REVIEWED`. Keep missing, stale, conflicting, or
invalid children explicit, and do not claim `PARENT_JOIN:PASS` while any
required child is incomplete. Before `TYLER_APPROVED`, `MERGED`, `SOAKING`, or
`SIGNED_OFF`, require every child to be completed, validated, artifact-complete,
integrated into the current FR branch, and current with the parent head.
Publish `PARENT_JOIN:PASS` only after those checks pass.