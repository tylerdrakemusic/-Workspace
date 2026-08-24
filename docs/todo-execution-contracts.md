# TODO Execution Contracts

`src/utils/todo_execution_contracts.py` defines the domain-neutral contract
used by TODO intake and future scheduler/worker coordination.

## Identity and graph rules

Create a `TodoContract` with a required `todo_id`. `parent_id` is the structural
parent and is independent from `PrerequisiteEdge`, whose direction is
`todo_id -> prerequisite_id`. Validate a set of contracts with
`validate_contracts`; it rejects duplicate or missing identities, invalid
parentage, ambiguous edges, and cycles in either graph.

Refined anchors may start with `fr_id=None`. Preserve `inherited_fr_id` when an
anchor is refined, then call `associate_fr` after `/new-fr` establishes the FR.
The association is rejected if it disagrees with the inherited link. Child
TODOs remain TODOs; this contract does not create child FR state machines.

`ResourceDeclaration` supports only `file` and named `shared` resources. A
contract may carry both `branch` and `worktree` to retain one-branch/
one-worktree traceability; partial declarations are invalid.

## Execution semantics

`ExecutionState` contains `queued`, `claimed`, `running`, `completed`, `failed`,
`cancelled`, and `stale`. `claim_execution` creates an explicit worker/claim
lease. `heartbeat_execution` renews a live lease and moves it to `running`;
`expire_execution` reports `stale` after expiration. `retry_allowed` applies
the bounded `max_retries` policy, while `cancellation_state` maps active work
to terminal `cancelled`. `parent_join_state` keeps a parent running until all
children reach terminal states and propagates failure, cancellation, or stale
outcomes.

These helpers are pure: they return values and do not mutate TODO, worker, or
FR state. Claim persistence, scheduling, and capacity decisions remain
outside this contract module.

The durable worker lifecycle is implemented by
`src/utils/todo_execution_lifecycle.py`. `ExecutionLifecycle` initializes its
tables in the existing workspace SQLite database, enforces one active claim per
TODO, validates worker/lease ownership and expiry, records immutable lifecycle
events, bounds retries, and persists stale-worker recovery records. Callers
provide the existing database connection; no separate database is created.

Pure readiness and capacity projection is documented in
[`todo-readiness-scheduler.md`](todo-readiness-scheduler.md).

## Lifecycle state machine

```text
queued -> claimed -> running -> completed
					|       -> failed -> queued (explicit retry)
					|       -> cancelled
					+------> stale (expired lease)
									  -> queued (explicit retry)
```

`heartbeat` moves `claimed` to `running` and renews the lease. Completion and
failure are single-winner operations guarded by the worker ID and lease token.
Cancellation is terminal. A failed or stale attempt can return to `queued` only
while its bounded retry budget remains; exhaustion preserves `failed`.

Downstream integration may consume a successful claim and its FR anchor to
create a child branch and worktree, but must not bypass lifecycle ownership, FR
gates, approval, QA, review, or merge controls. This implementation does not
create branches, worktrees, child FRs, or background workers.