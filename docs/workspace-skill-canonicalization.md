# Workspace Skill Canonicalization

The canonical inventory is [skill-catalog.json](../.github/skills/skill-catalog.json).
It is the auditable source for all local `.github/skills/*/SKILL.md` directories.
The validator in [skill_catalog.py](../src/utils/skill_catalog.py) checks exact
coverage, required audit fields, canonical-ID collisions, and external sync
collisions.

## Taxonomy

- `workspace-specific`: depends on the workspace FR/manifest, agent, or project
  operating model and should remain local.
- `agnostic/public candidate`: has reusable behavior, but needs the listed
  adaptations before extraction into a public skills repository.
- `domain-specific`: tied to a project domain and should not be generalized as
  part of this FR.

The catalog records provenance conservatively. Where a local file does not state
its upstream source, provenance is explicitly recorded as not recorded rather
than inferred.

## Ownership Boundaries

- Interview intent with `interview-me`; use `grill-me` only to stress-test a
  plan or design that already exists.
- Use `spec-driven-development` when requirements or architecture are unclear;
  use `planning-and-task-breakdown` once the work is clear and needs ordering.
- Use `code-review-and-quality` for completed changes; use
  `doubt-driven-development` during high-risk work to challenge assumptions.
- Use `security-and-hardening` for code defenses; use `scope-creep` for project
  ownership and misplaced-artifact audits.
- Use `debugging-and-error-recovery` for observed failures; use
  `karpathy-guidelines` for implementation discipline and complexity control.
- Use `git-workflow-and-versioning` for repository lifecycle mechanics,
  `incremental-implementation` for delivery slices, and `handoff` for agent
  context transfer.

## Resolved Overlaps

`perfect-td` remains the generic, non-mutating todo-refinement skill and is a
public candidate. `perfect-scoped-td` remains workspace-specific because it
coordinates the manifest todo database and FR ledger under approval gates.
They share refinement language but do not own the same state or audience.

`tdd` remains the reusable TDD reference. `test-driven-development` remains the
workspace operational gate that requires a failing test before production code.
The former explains test seams and anti-patterns; the latter enforces the
workflow required by this workspace's tiered implementation agents.

## Public-Candidate Adaptations

The catalog marks reusable candidates individually. Before publishing them,
adaptations are required:

- Remove hard-coded `f:\` workspace paths and FR/manifest database assumptions.
- Replace workspace-specific agent names, state-machine references, and
  `Protect-Command` conventions with host-neutral interfaces.
- Keep `documentation-and-adrs`, `debugging-and-error-recovery`,
  `doubt-driven-development`, `git-workflow-and-versioning`, `incremental-implementation`,
  `interview-me`, `karpathy-guidelines`, `observability-and-instrumentation`,
  `planning-and-task-breakdown`, `prototype`, `scope-creep`,
  `security-and-hardening`, `spec-driven-development`, `tdd`, `tradeoffs`,
  `ui-baseline-capture`, and `wizard` as candidates pending those adaptations.
- Do not extract `perfect-scoped-td`, `test-driven-development`, or the other
  workspace-specific entries without redesigning their local governance
  dependencies.

No public skills repository is created by this FR.

## External Evaluation

gstack evaluation is deferred. No gstack checkout, manifest, or local candidate
was available in this worktree, so adopt/map/reject decisions would require
fabricated evidence. No runtime tooling or external skill was installed, and
`external_sync` is intentionally empty until a unique approved mapping exists.