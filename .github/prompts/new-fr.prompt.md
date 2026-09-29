---
mode: ⊕workspace-overseer
---
# New Feature Request

**Title:** 

<!-- Optional: add any extra context, constraints, or notes below the title.
     Leave blank if the title says it all. -->



---

**IMPORTANT:** There are MCP servers likely running; use them before taking any action.
- Inspect the workspace with available tools first.
- Prefer existing MCP work and do not invent temporary queries or ad hoc code.
- Use `file_search`, `grep_search`, `read_file`, and only run terminal commands when needed.

## Blocking Approval Voice

When this flow reaches a blocking approval that genuinely requires Tyler's
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

The server derives timestamps, worker-capacity limits, lease duration, and retry
limits from policy. Generate `claim_idempotency_key` from at least 32 random
bytes (for example, `secrets.token_urlsafe(32)`) and keep it private; only the
same worker with that key can replay a claim and recover its existing lease.
Only claim and approved takeover return a `lease_token`; keep it private and
pass it only to that worker's heartbeat, failure, cancellation, or completion
call. Takeover also requires `takeover_enabled` in policy and `approved=true`.

Use these rules when coordinating work:

- Persist `queued` before dispatch, then update the durable state for claim,
   heartbeat, retry, failure, cancellation, stale recovery, and takeover.
- Set `completed` only after the handoff has been validated and its required
   evidence is available. A status message or coordination event is not a
   validated handoff.
- Keep branch, worktree, and integration conflicts as coordination events. Do
   not rewrite the execution state unless the execution itself is invalid.
- Parent aggregation must reuse the existing `parent_join_state` precedence;
   do not invent a second parent state reducer.
- Before advancing the FR, verify every executable parent and child has a
   persisted state and that any `completed` TODO has a validated handoff.

<!-- ⊕workspace-intake instructions:
     1. Read the title (and any notes) above.
     2. Inspect the codebase to infer as many fields as possible: type, affected
        projects, motivation, risk, dependencies, and out-of-scope boundaries.
       1.5 TODO CROSS-REFERENCE: Use the governed manifest-coordination tools;
            never query or update manifest_todos.db with SQL.
            Call `mcp_manifest-coor_list_open_todos(project=<inferred_project>)`,
            then `mcp_manifest-coor_read_todo(todo_id=<candidate_id>)` for relevant
            candidates. Surface overlapping matches in the Phase B scope card under
            "📎 Related todos". Only after Tyler confirms, call
            `mcp_manifest-coor_link_confirmed_todo_to_fr(todo_id=<matched_id>,
            fr_id=<FR-ID>, confirmed=true)` for each confirmed match. If there are no
            matches, skip silently.
     3. Run your Phase A interview — but ONLY ask about fields you genuinely cannot
        infer. Skip any question whose answer is obvious from the title, notes, or
        codebase. Fewer questions = better. Use vscode_askQuestions with prefilled
        options as normal.
     4. If the feature is vague or high-risk, invoke the grill-me skill: interview the user one question at a time, walking down each branch of the decision tree, and provide a recommended answer for each.
     5. After the interview (or immediately if nothing is ambiguous), present Tyler
        with a complete FR draft — all fields filled — as a single confirmation block.
     6. Ask Tyler: "Does this look right? Confirm, or tell me what to change."
     7. On confirmation → proceed to Phase B triage (ledger + registry + cycle timer).
     8. On amendments → update the draft and re-confirm.

   PARENT JOIN: If the FR is decomposed into child TODOs, record the required
   child IDs and join criteria in the FR plan. Incomplete child work or join
   bookkeeping does not block technical progression through FUNCTIONAL_QA,
   ARCHITECTURE_REVIEW, REVIEW_REQUESTED, or AUTO_REVIEWED. Keep missing, stale,
   conflicting, or invalid children explicit, and do not claim PARENT_JOIN:PASS
   while any required child is incomplete. Before TYLER_APPROVED, MERGED,
   SOAKING, or SIGNED_OFF, require every child to be completed, validated,
   artifact-complete, integrated into the current FR branch, and current with
   the parent head; publish PARENT_JOIN:PASS only after those checks pass.

     0. MODE CHECK: Confirm you are running as ⊕workspace-overseer. If not,
        hand off to that agent now — it provides MCP pre-flight, agent discovery,
        and the full workspace routing context required for accurate triage.
     ⚠️  DB-ONLY RULE: Register the FR in the DB via `fr_cli.py open` — do NOT
     create a `.md` file in `.github/fr/`. The DB is the sole source of truth.
     (See feature-request-flow.instructions.md § FR Identifier) -->
