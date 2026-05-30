<!-- applyTo: .github/agents/*.agent.md -->

# Feature Request Flow — Canonical State Machine

Shared protocol for ALL workspace agents (overseer, orchestrators, CI,
commitment, reviewer, intake). Defines how a new feature request travels from
Tyler's intent to a merged PR, how concurrent requests stay isolated, and
exactly where Tyler acts as the human gateway.

## Ground Truth

- **Each project is its own GitHub repository.** The five projects (∞Life,
  ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest, ⊕Workspace) are separate repos under
  `tylerdrakemusic/*` on GitHub. `f:\` itself is NOT a single repo.
- **A feature request (FR) is scoped to one or more projects.** Multi-project FRs
  produce **one PR per affected repo**, tracked by a parent FR record.
- **One code-changing session = one branch = one worktree = one draft PR.**
- **Tyler is the only human in the loop.** Every agent-to-agent handoff is
  automated; every gate where intent, scope, safety, or finality matters is
  Tyler's.

## FR Identifier

Every feature request gets a stable ID: `FR-YYYYMMDD-<slug>` (e.g.
`FR-20260422-multi-agent-flow`). The ID is reused for:
- The branch name suffix
- The registry row
- The PR title prefix
- Commit message references

> **AGENT RULE — NO .md FILES:** NEVER create a `.github/fr/*.md` file as the
> FR record. The DB (`fr_ledgers.db` via `fr_cli.py`) is the sole source of
> truth. Use `fr_cli.py open` to register every FR. Existing `.md` files in
> `.github/fr/` are legacy supplements only — do not create new ones.

## State Machine

```
OPEN → TRIAGED → BRANCHED → IN_PROGRESS → FUNCTIONAL_QA → ARCHITECTURE_REVIEW → REVIEW_REQUESTED → AUTO_REVIEWED
       ↑                                                                                               │
       └──── CHANGES_REQUESTED ←──────────────────────────────────────────────────────────────────────┘
                                                                                          │
                                                                         BRANCH_CHECKED_OUT
                                                                                          │
                                                                   TYLER_APPROVED ←───────┘
                                                                        │
                                                                     MERGED → SOAKING → SIGNED_OFF → ARCHIVED
```

### State Definitions

| State | Meaning | Owner |
|-------|---------|-------|
| `OPEN` | Tyler filed a request; not yet scoped | ⊕workspace-intake |
| `TRIAGED` | Scope, affected projects, acceptance criteria recorded | ⊕workspace-intake |
| `BRANCHED` | Isolated branch + worktree + draft PR created per repo | ⊕workspace-ci |
| `IN_PROGRESS` | Implementation agent(s) writing code. **TDD gate required** — load `f:\⊕Workspace\.github\skills\test-driven-development\SKILL.md` before writing any production code (see TDD Gate section below). | project orchestrator |
| `FUNCTIONAL_QA` | Implementation complete. `⊕workspace-qa` derives a test plan from FR acceptance criteria + diff, executes functional tests (DB queries, CLI runs, script executions, Playwright for HTML-touching changes), and records proof artifacts. PASS → advances to `ARCHITECTURE_REVIEW`; FAIL → `CHANGES_REQUESTED` with per-criterion failure details. Hard-blocking gate. | ⊕workspace-qa |
| `ARCHITECTURE_REVIEW` | Implementation done. `⊕workspace-architecture-reviewer` scans the diff for architectural impact (new agents, integrations, deps, DB tables, cross-project wiring) and verifies the relevant `f:\⊕Workspace\diagrams\*.mmd` files were updated. STALE/MISSING diagrams hand off to `⊕workspace-architecture-beautifier`, then re-verify. Only PASS / PASS_WITH_UPDATES advances to `REVIEW_REQUESTED`. | ⊕workspace-architecture-reviewer |
| `REVIEW_REQUESTED` | Implementation claims done, PR marked ready. **GitHub Actions `test` workflow auto-runs and gates merge** — see CI Gateway below. Playwright validation is handled by `⊕workspace-qa` during `FUNCTIONAL_QA` — the orchestrator does NOT run it separately before this state. | project orchestrator |
| `AUTO_REVIEWED` | Automated review complete (alignment + security + tests + proof). Required `test` status check must be green before merge can be attempted. | ⊕workspace-reviewer |
| `BRANCH_CHECKED_OUT` | Feature branch checked out locally so Tyler can demo/inspect before approving | ⊕workspace-ci |
| `CHANGES_REQUESTED` | Auto-review or Tyler requested fixes | ⊕workspace-reviewer / Tyler |
| `TYLER_APPROVED` | Tyler approved the PR | Tyler |
| `MERGED` | PR merged to default branch; cycle timer closed | ⊕workspace-ci |
| `SOAKING` | Feature is live on main, awaiting Tyler's post-merge "confirmed in solution" signoff. FR is still visible in the portal FR panel so Tyler can exercise the feature before accepting it. | Tyler (gate) / ⊕workspace-ci (transition recorder) |
| `SIGNED_OFF` | Tyler confirmed the feature is present and working on main. Final human gateway. | Tyler |
| `ARCHIVED` | FR drops off the active portal FR panel. FR record persists in `fr_ledgers.db` as permanent history. | ⊕workspace-ci |
| `CLOSED` | Legacy terminal state (pre-SOAK protocol). Still accepted for backward compat; treat as equivalent to `ARCHIVED` for portal filtering. | ⊕workspace-ci |

## CI Gateway (LIVE as of FR-20260425)

Every PR to `main` in every repo runs `.github/workflows/test.yml` (pytest,
Python 3.11, 10-min timeout). The required status check is named **`test`**.

- **All 4 public repos** (⊕Workspace, ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest) have
  GitHub classic branch protection on `main`: strict mode, `test` check
  required + must be up-to-date, **no admin bypass**, no force-push, no
  deletions. GitHub will reject merge attempts on red CI with HTTP 405.
- **∞Life** (private, free tier — no server-side branch protection available)
  is mitigated by a local `pre-push` hook at `.git/hooks/pre-push` that blocks
  direct pushes to `main`, plus `⊕workspace-ci` agent discipline (always PR).
  See `f:\∞Life\docs\PROTECTION_HOOK.md`.
- **∞Life CI** also runs a health-data gitignore audit step (deny list:
  `*.db`, `data/bloodwork/`, `data/medical_records/`, `data/genomics/`,
  `SUBJECT_PROFILE.json`) that fail-closes the build if any match the diff.

### Hard merge rules
- **Direct pushes / merges to `main` are forbidden** in every repo. All work
  flows: feature branch → PR → green `test` check → merge.
- Agents MUST wait for the `test` status check to be green before invoking
  the merge API. Attempting merge on a red PR will be rejected by GitHub
  (public repos) or fail review (∞Life).
- `--no-verify` on ∞Life pushes requires Tyler's explicit per-task approval.

## TDD Gate (IN_PROGRESS)

Before writing any production code during `IN_PROGRESS`, the implementation
agent **MUST** invoke the TDD skill:

```
read_file: f:\⊕Workspace\.github\skills\test-driven-development\SKILL.md
```

The Iron Law: **NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.**
Red-Green-Refactor is not optional. If an agent writes implementation code
before a failing test exists, delete it and start over.

Exceptions (require explicit Tyler approval): throwaway prototypes, generated
scaffolding code, configuration-only changes.

## Dependency Sync (BRANCHED Gate)

At `BRANCHED → IN_PROGRESS`, before any implementation agent starts work,
sync external skill dependencies:

```powershell
# Sync superpowers to latest main + refresh local TDD skill copy
cd F:\superpowers
git fetch origin
git merge --ff-only origin/main
Copy-Item "F:\superpowers\skills\test-driven-development\SKILL.md" `
    "f:\⊕Workspace\.github\skills\test-driven-development\SKILL.md" -Force
```

This ensures implementation agents always use the latest TDD skill version.

## Tyler's Gateways (ONLY places humans act)


1. **Open** — Tyler files the FR in plain language (chat, or a GitHub issue).

   **UI/UX capture (intake, before interview questions):** when a FR or BFX touches UI/UX surfaces (detected by file-impact heuristics or keywords), `⊕workspace-intake` invokes the `ui-baseline-capture` skill (`f:\.github\skills\ui-baseline-capture\SKILL.md`) before the Phase A interview. The skill takes a Playwright screenshot and page structure snapshot of the affected surfaces, shows them inline in the Phase B scope card, and stores the screenshot as a `fr_artifact` (key `ui-baseline`) for the QA agent's before/after comparison.

2. **Approve scope** — After `TRIAGED`, Tyler confirms scope + acceptance
   criteria before any branch is cut. *Agents MUST wait here.*
3. **Approve PR** — After `AUTO_REVIEWED` passes AND the branch has been
   checked out locally (`BRANCH_CHECKED_OUT`), Tyler reviews the automated
   report **plus the live running feature** and either approves or requests changes.
4. **Approve merge** — Tyler initiates the merge (or authorizes the CI agent
   to merge on his behalf for a specific FR).
5. **Post-soak signoff** — After `MERGED` the FR enters `SOAKING`. The feature
   is live on `main`; Tyler exercises it in the real solution for as long as
   he wants. When he is satisfied the feature is actually present and working
   post-merge (not "vanished" by a subsequent commit), he signs off → state
   becomes `SIGNED_OFF`, then `⊕workspace-ci` moves it to `ARCHIVED` and the
   FR drops off the active portal panel. **This is the net-new gate introduced
   to prevent proof-on-branch / feature-missing-on-main gaps.**
6. **Priority override** — Tyler can reorder or pause any FR at any time.

Tyler NEVER manually: writes code, creates branches, runs reviews, amends
commits, resolves conflicts, or edits the registry.

## Registry

Single source of truth for active FRs: **`fr_ledgers.db`** (at
`f:\⊕Workspace\src\data\fr_ledgers.db`), accessed via `fr_cli.py`.

Key commands:
```powershell
$env:PYTHONUTF8="1"
# List all active FRs
C:\G\python.exe f:\⊕Workspace\src\utils\fr_cli.py list --active
# Get a specific FR
C:\G\python.exe f:\⊕Workspace\src\utils\fr_cli.py get <FR-ID>
```

Only `⊕workspace-intake` and `⊕workspace-ci` call `fr_cli.py open` and
`fr_cli.py update-state`. Every agent reads the registry before starting work
to detect conflicts with in-flight FRs.

## Per-FR Events (shared context for every agent)

Every FR has a history of events stored in `fr_ledgers.db` via `fr_cli.py`.
This is the FR's **complete narrative history and shared agent context**.

### Read rule (applies to EVERY agent)
Before taking any action on an FR, retrieve its current state and event history:
```powershell
$env:PYTHONUTF8="1"
C:\G\python.exe f:\⊕Workspace\src\utils\fr_cli.py get <FR-ID>
```
This returns the original request, acceptance criteria, current state, prior
decisions, findings, failures, and links to all artifacts.

### Write rule (applies to EVERY agent)
After acting on an FR, before finishing your turn, record ONE event:
```powershell
$env:PYTHONUTF8="1"
C:\G\python.exe f:\⊕Workspace\src\utils\fr_cli.py record-event <FR-ID> <agent> <event-type> "<summary>"
```

Event types: `state-transition` | `delegation` | `decision` | `finding` | `failure` | `artifact` | `note`

For state transitions, also call:
```powershell
C:\G\python.exe f:\⊕Workspace\src\utils\fr_cli.py update-state <FR-ID> <new-state> [--branch "..."] [--prs "..."]
```

For recording artifacts (proof files, PRs, SHAs):
```powershell
C:\G\python.exe f:\⊕Workspace\src\utils\fr_cli.py record-artifact <FR-ID> <type> "<label>" --path "<path>"
```

### Hard event rules
- **Intake opens** the FR on first contact: `fr_cli.py open <FR-ID> ...`
- **Every state transition** gets a `record-event` call with type `state-transition`
- **Every delegation** (agent → agent) gets a `record-event` call from the sending agent
- **Every artifact** (perf run ID, proof ID, PR URL, commit SHA, report path) gets a `record-artifact` call
- **Events are append-only** — never delete or modify past events

## FR Cycle Timer (full intake-to-merge timing)

Every FR has one perf_cli run that measures the full cycle: from intake open
to merge. This is separate from each agent's own short-lived perf runs — it
spans the entire FR lifecycle, including all human approval gates.

### Protocol

1. **Intake starts the cycle timer** on FR open:
   ```
   C:\G\python.exe f:\⊕Workspace\src\utils\perf_cli.py start "fr-cycle-<FR-ID>"
   ```
   Stash the returned run_id; record it via:
   ```powershell
   $env:PYTHONUTF8="1"
   C:\G\python.exe f:\⊕Workspace\src\utils\fr_cli.py record-artifact <FR-ID> metric "Cycle timer run_id" --path "<run_id>"
   ```

2. **Every state transition** appends an Event Log entry with an ISO timestamp.
   Phase durations (open→scope-approved, branched→review, review→merge) are
   derivable by parsing these timestamps — no extra perf calls needed.

3. **CI closes the cycle timer when it merges the PR** (primary path):
   ```
   C:\G\python.exe f:\⊕Workspace\src\utils\perf_cli.py end <cycle_run_id> \
       --status ok --detail "FR-<ID> merged: <merge SHAs>"
   ```

4. **Safety net — reconciliation** (for when Tyler merges on GitHub.com without
   CI agent action): `⊕workspace-ci` exposes a `reconcile-fr-timers` capability
   that:
   - Queries `fr_cli.py list --active` for FRs in `TYLER_APPROVED` or `AUTO_REVIEWED`
     state with an open (unclosed) Cycle timer
   - Queries GitHub via `mcp_github` tools for each PR's `merged_at` timestamp
   - For any merged PR, closes the cycle timer with `--at <merged_at>` to
     backfill the true merge time
   - Updates FR state via `fr_cli.py update-state` and records a reconciliation event
   - Can be invoked on-demand (`@⊕workspace-ci reconcile`) or scheduled

### Why this design
- **Zero infrastructure** — no webhook server, no always-on daemon
- **Accurate timing** — GitHub's `merged_at` is authoritative even if Tyler
  merges manually
- **Tyler stays sovereign** — he can merge via GitHub UI, CLI, or the CI agent;
  reconciliation closes the loop either way
- **Optional acceleration** — a GitHub Actions workflow per repo can trigger
  reconciliation automatically on merge (template at
  `.github/workflow-templates/fr-merge-reconcile.yml`), but is not required

### Reporting
After close, `perf_cli report <cycle_run_id>` shows total FR wall-clock time.
For phase breakdowns, parse the ledger's Event Log timestamps.

## Concurrency Rules

1. Multiple FRs can be `IN_PROGRESS` simultaneously as long as each has its own
   branch + worktree per repo.
2. Two FRs touching the same file in the same repo must serialize:
   - The second FR waits in `BRANCHED` state until the first reaches
     `TYLER_APPROVED` or earlier release, OR
   - The second FR rebases on top of the first's branch (designating one as
     base) — ⊕workspace-ci handles the rebase plan.
3. Cross-project FRs: one branch per repo, but all branches share the FR ID
   suffix for traceability.
4. Max concurrent `IN_PROGRESS` FRs: **3** (matches agent fan-out cap).
   Additional FRs sit in `TRIAGED` queue.

## Branch Naming

```
feature/<fr-id>     # for feature FRs
fix/<fr-id>         # for bug fix FRs
chore/<fr-id>       # for maintenance/refactor FRs
```

Example: `feature/FR-20260422-multi-agent-flow`

Per-repo branches use the same name in each affected repo.

## Worktree Layout

```
F:\worktrees\<fr-id>\<project-short-name>
```

Example:
```
F:\worktrees\FR-20260422-multi-agent-flow\workspace
F:\worktrees\FR-20260422-multi-agent-flow\infinitelife
```

## End-to-End Flow (Happy Path)

```
1. Tyler → ⊕workspace-intake: "Add X to projects A and B"
2. ⊕workspace-intake: triage, open FR in `fr_ledgers.db` via `fr_cli.py open`, ask Tyler to confirm scope
3. Tyler: "approved"  ← GATEWAY
4. ⊕workspace-intake → ⊕workspace-ci: create branches + worktrees + draft PRs for A and B
5. ⊕workspace-ci: records BRANCHED state, returns PR URLs
6. ⊕workspace-intake → ⊕workspace-overseer: route implementation
7. ⊕workspace-overseer → project orchestrators (A and B in parallel): implement
8. Orchestrators: push commits to their branches; when done, mark PR ready
9. ⊕workspace-overseer → ⊕workspace-reviewer: auto-review both PRs
10. ⊕workspace-reviewer: posts review comments, sets AUTO_REVIEWED or CHANGES_REQUESTED
11. ⊕workspace-ci: checks out the feature branch(es) locally in their worktree paths
    so Tyler can run demos and inspect proof artifacts. Sets BRANCH_CHECKED_OUT.
    Notifies Tyler: "Branch checked out at F:\worktrees\<fr-id>\<project> — ready to demo."
12. Tyler: reviews the automated report AND the live feature  ← GATEWAY
13. Tyler: "merge"  ← GATEWAY
14. ⊕workspace-ci: merge PRs, delete branches + worktrees, update state via
    `fr_cli.py update-state <FR-ID> MERGED` and `fr_cli.py update-state <FR-ID> SOAKING`.
    Records `Merged at` in the FR record. FR remains visible on
    the portal FR panel with "Soaking for Xd Yh" badge.
15. Tyler: exercises the feature on main for as long as he wants.
16. Tyler: "signed off on FR-<ID>"  ← GATEWAY (post-soak)
17. ⊕workspace-ci: updates state via `fr_cli.py update-state <FR-ID> SIGNED_OFF` and
    `fr_cli.py update-state <FR-ID> ARCHIVED`.
    FR drops off active portal panel; FR record persists in `fr_ledgers.db`.
```

## Agent Responsibility Matrix

| Agent | Role |
|-------|------|
| `⊕workspace-intake` | Own the registry. Triage FRs. Route to CI for branching. |
| `⊕workspace-ci` | Own branches, worktrees, merges, conflict resolution. After AUTO_REVIEWED, check out the feature branch locally and set BRANCH_CHECKED_OUT before notifying Tyler. |
| `⊕workspace-overseer` | Route implementation to orchestrators; coordinate multi-project FRs. |
| project orchestrators | Implement on the assigned branch only. |
| `⊕workspace-architecture-reviewer` | Detect architectural impact in the PR diff; verify the relevant `.mmd` diagrams were updated. Hard-blocks merge on STALE/MISSING. |
| `⊕workspace-architecture-beautifier` | Update or create `.mmd` files in `f:\⊕Workspace\diagrams\` per the architecture-reviewer's required-updates list. |
| `⊕workspace-reviewer` | Run alignment + security + tests + proof; post automated PR review. |
| `⊕workspace-security` | Security gate invoked by reviewer; can block before merge. |

## Hard Rules (apply to every agent)

- NEVER start implementation before the FR is in `BRANCHED` state.
- NEVER push or merge directly to `main` in any repo — every change goes
  through a PR with a green `test` status check.
- NEVER merge a PR that is not in `TYLER_APPROVED` state.
- NEVER merge a PR while its required `test` status check is red or pending.
- NEVER archive an FR before it reaches `SIGNED_OFF`. Merged ≠ done.
- NEVER let two agent sessions write to the same worktree.
- NEVER make direct writes to FR state — always use `fr_cli.py`.
- ALWAYS retrieve FR context with `fr_cli.py get <FR-ID>` before acting on an FR.
- ALWAYS record events with `fr_cli.py record-event` after acting on an FR.
- ALWAYS check active FRs with `fr_cli.py list --active` before starting work.
- ALWAYS include the FR ID in commit messages and PR titles.
