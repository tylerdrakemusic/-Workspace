# TODO Operational Runbook

The operational runtime composes the existing contract validator, deterministic
readiness scheduler, durable lifecycle, child worktree coordinator, and parent
join gate. It does not create child FR state machines or bypass approval, QA,
review, merge, soak, or signoff gates.

## Initial configuration

`src/config/todo_execution_policy.json` is the initial policy. It permits up to
8 parallel TODOs for one FR and 16 TODO workers across the workspace. These are
bounded starting defaults, not performance claims. Tune them only from
allowlisted telemetry after observing queue depth, readiness, lease health,
retry volume, stale recovery, integration conflicts, and gate outcomes.

Each claim has a 300-second lease and two retries by default. The lifecycle
persists the worker, claim, lease, attempt, and idempotency identities, while
telemetry deliberately excludes lease tokens, errors, credentials, health
data, and financial PII.

## Normal workflow

1. Validate the complete DAG and resource declarations.
2. Project readiness. Prerequisites must be in their declared terminal states;
   parentage alone never makes a child runnable.
3. Dispatch in priority-descending, TODO-ID-ascending order. File and named
   shared-resource conflicts remain queued, and capacity is enforced per FR
   and globally.
4. Claim work through the durable lifecycle, then heartbeat it before expiry.
5. Complete and validate the child work. The coordinator admits only claimed,
   running, or completed work with valid traceability and an isolated branch and
   worktree.
6. Rebase stale child work onto the current parent head and integrate it under
   the FR branch lock. A conflict leaves the child source available for repair.
7. Evaluate the parent join. Every required child must be completed, validated,
   have its required artifacts, be integrated into the parent branch, and be
   based on the current parent head before parent QA and review can proceed.

## Recovery

An expired claim is marked `stale`; it is never silently reclaimed. Recover it,
then explicitly retry it while the retry budget remains. A failed attempt follows
the same explicit retry path. Retry exhaustion leaves the work `failed` and
blocks the parent join. Ownership mismatches, expired heartbeats, duplicate
claims, invalid transitions, and unclaimed work are rejected and audited.

Integration conflicts are reported as conflicts rather than discarded. Repair
or rebase the preserved child source, validate it again, and retry integration.
Unvalidated, expired, failed, stale, conflicting, or otherwise unjoined work
cannot satisfy the parent gate.

## Telemetry

The runtime emits only these operational event kinds: queue depth, readiness,
claim, lease, retry, stale recovery, integration, conflict, and gate. Event
fields are allowlisted to aggregate counts, attempts, and human-actionable
reasons. Do not add secrets, tokens, credentials, medical or genomic data, or
financial account information to telemetry.