# TODO Readiness Scheduler

`src/utils/todo_readiness_scheduler.py` provides a deterministic, pure
projection of TODO readiness. `schedule_todos` consumes `TodoContract` values,
an execution-state snapshot, optional priorities, capacity limits, and current
resource reservations. It returns `ReadinessResult` with `blocked`, `queued`,
`ready`, and `join_ineligible` tuples.

## Semantics

- Contracts are validated before scheduling. Duplicate or missing identities,
  invalid parentage, ambiguous edges, cycles, unsupported resources, invalid
  terminal policies, and inherited-FR mismatches use the existing contract
  validation rules.
- `parent_id` is structural only. A parent with children is reported as
  `join_ineligible`; it is never treated as a prerequisite of those children.
- A prerequisite is satisfied only when its snapshot state is one of that edge's
  `allowed_terminal_states`. Missing snapshot entries are non-active and are
  eligible when no prerequisite blocks them.
- `claimed` and `running` snapshot entries are existing occupancy. Terminal
  entries are omitted from candidate output. The function does not claim,
  lease, persist, or mutate any state.
- `global_capacity` limits all active and newly selected workers. FR-linked
  TODOs use `per_fr_capacity`; TODOs whose effective FR is `None` use the
  separate `pre_fr_capacity` bucket. Capacity is counted independently per
  bucket and globally.
- File and named shared resources are exclusive. Existing active reservations
  and earlier selected candidates block later candidates in deterministic order.
- Candidates are ordered by priority descending and TODO ID ascending. Missing
  priorities default to zero. Queued explanations identify capacity and/or
  reservation conflicts; blocked explanations list unmet prerequisites.

The scheduler does not implement claims, leases, heartbeats, retries, stale
recovery, persistence, execution-state writes, FR ledger mutation,
branch/worktree operations, child FRs, approval bypass, or worker coordination.

This is a pure scheduler boundary: it returns readiness projections for
downstream consumers and does not perform those actions. TODO 332 consumes the
projections for worker lifecycle, claims, and lease handling; TODO 333 consumes
them for branch, worktree, and integration handling.