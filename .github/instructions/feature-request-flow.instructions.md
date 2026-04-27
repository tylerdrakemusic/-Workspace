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

## State Machine

```
OPEN → TRIAGED → BRANCHED → IN_PROGRESS → ARCHITECTURE_REVIEW → REVIEW_REQUESTED → AUTO_REVIEWED
       ↑                                                                                  │
       └──── CHANGES_REQUESTED ←──────────────────────────────────────────────────────────┘
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
| `IN_PROGRESS` | Implementation agent(s) writing code | project orchestrator |
| `ARCHITECTURE_REVIEW` | Implementation done. `⊕workspace-architecture-reviewer` scans the diff for architectural impact (new agents, integrations, deps, DB tables, cross-project wiring) and verifies the relevant `f:\⊕Workspace\diagrams\*.mmd` files were updated. STALE/MISSING diagrams hand off to `⊕workspace-architecture-beautifier`, then re-verify. Only PASS / PASS_WITH_UPDATES advances to `REVIEW_REQUESTED`. | ⊕workspace-architecture-reviewer |
| `REVIEW_REQUESTED` | Implementation claims done, PR marked ready. **GitHub Actions `test` workflow auto-runs and gates merge** — see CI Gateway below. | project orchestrator |
| `AUTO_REVIEWED` | Automated review complete (alignment + security + tests + proof). Required `test` status check must be green before merge can be attempted. | ⊕workspace-reviewer |
| `BRANCH_CHECKED_OUT` | Feature branch checked out locally so Tyler can demo/inspect before approving | ⊕workspace-ci |
| `CHANGES_REQUESTED` | Auto-review or Tyler requested fixes | ⊕workspace-reviewer / Tyler |
| `TYLER_APPROVED` | Tyler approved the PR | Tyler |
| `MERGED` | PR merged to default branch; cycle timer closed | ⊕workspace-ci |
| `SOAKING` | Feature is live on main, awaiting Tyler's post-merge "confirmed in solution" signoff. FR is still visible in the portal FR panel so Tyler can exercise the feature before accepting it. | Tyler (gate) / ⊕workspace-ci (transition recorder) |
| `SIGNED_OFF` | Tyler confirmed the feature is present and working on main. Final human gateway. | Tyler |
| `ARCHIVED` | FR drops off the active portal FR panel. Ledger file remains in the repo as permanent history. | ⊕workspace-ci |
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

## Tyler's Gateways (ONLY places humans act)


1. **Open** — Tyler files the FR in plain language (chat, or a GitHub issue).
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

Single source of truth for active FRs:
**`f:\.github\FEATURE_REQUESTS.md`**

Structure: a markdown table of active FRs + an archive section for closed ones.
Only `⊕workspace-intake` and `⊕workspace-ci` write to it. Every agent reads it
before starting work to detect conflicts with in-flight FRs.

## Per-FR Ledger (shared context for every agent)

Every FR has a dedicated ledger file:
**`f:\.github\FR_LEDGERS\<FR-ID>.md`**

The ledger is the FR's **complete narrative history and shared agent context**.
Template lives at `f:\.github\FR_LEDGERS\_TEMPLATE.md`; see
`f:\.github\FR_LEDGERS\README.md` for the full spec.

### Read rule (applies to EVERY agent)
Before taking any action on an FR, read its ledger. This is how agents hand off
context without a central DB — the ledger contains the original request,
acceptance criteria, prior decisions, findings, failures, and links to all
artifacts.

### Write rule (applies to EVERY agent)
After acting on an FR, before finishing your turn, append ONE event entry to
the ledger's **Event Log** section. Format:

```markdown
### <ISO-8601 timestamp> — <agent-name>

**Event:** state-transition | delegation | decision | finding | failure | artifact | note

**Summary:** <one-line summary>

**Details:**
<optional multi-line body>

**Next:** <next agent/action, or "awaiting Tyler: <gateway>">
```

### Hard ledger rules
- **Intake creates** the ledger on FR open (copy `_TEMPLATE.md`, fill header)
- **Only intake / CI** update the Header section in place
- **Event Log and Artifacts are append-only** — never edit or delete past entries
- **Every state transition** gets an Event Log entry
- **Every delegation** (agent → agent) gets an Event Log entry from the sending agent
- **Every artifact** (perf run ID, proof ID, PR URL, commit SHA, report path) gets
  appended to the Artifacts section
- **On close**, the ledger stays in the repo as permanent historical record

### Ledger Persistence Protocol (MANDATORY)

Ledger files and the registry MUST be committed immediately after every write.
Dangling uncommitted ledger changes are a protocol violation.

Branch protection blocks direct pushes to `main` in all repos (including
⊕Workspace), so the strategy differs by lifecycle phase:

**Pre-merge (OPEN through TYLER_APPROVED):**
Ledger and registry writes during this phase go on the **feature branch**
alongside implementation commits. They merge to `main` with the PR. The
writing agent appends to the ledger and commits to the active feature branch:
```bash
cd f:\⊕Workspace
git add .github/FR_LEDGERS/<FR-ID>.md .github/FEATURE_REQUESTS.md
git commit -m "⊕ workspace: ledger — <FR-ID> → <new-state>"
# pushed to the feature branch, not main
```

**Post-merge (MERGED through ARCHIVED):**
After the feature branch PR is merged, any remaining ledger updates (cycle
timer close, soak/sign-off state transitions) must go through a short-lived
`chore/ledger-<FR-ID>` branch and an immediate PR. The PR touches only
markdown files so pytest passes trivially → CI is green → merge promptly.
```bash
cd f:\⊕Workspace
git switch -c chore/ledger-<FR-ID>-closeout
git add .github/FR_LEDGERS/<FR-ID>.md .github/FEATURE_REQUESTS.md
git commit -m "⊕ workspace: ledger — <FR-ID> → MERGED"
git push origin chore/ledger-<FR-ID>-closeout
# open PR immediately; merge after green CI
```

For reconcile runs covering multiple FRs, batch all updates onto a single
`chore/ledger-reconcile-<YYYYMMDD>` branch in one PR.

**Commit scope:**
- Include both the ledger file AND `FEATURE_REQUESTS.md` if either changed.
- Only include files that actually changed (use `git diff --name-only` to
  confirm before staging).

**Trigger points — when the commit is required:**

| Event | Phase | Writing agent | Branch |
|-------|-------|---------------|--------|
| FR opened / triaged | pre-merge | `⊕workspace-intake` | feature branch |
| Scope approved → BRANCHED | pre-merge | `⊕workspace-intake` | feature branch |
| Any in-progress event log append | pre-merge | any agent | feature branch |
| PR merged → MERGED | post-merge | `⊕workspace-ci` | `chore/ledger-<FR-ID>-closeout` |
| Tyler signs off → SIGNED_OFF / ARCHIVED | post-merge | `⊕workspace-ci` | `chore/ledger-<FR-ID>-archive` |
| Reconcile run | post-merge | `⊕workspace-ci` | `chore/ledger-reconcile-<YYYYMMDD>` |

**Commit message format:** `⊕ workspace: ledger — <FR-ID> → <new-state>`

Examples:
- `⊕ workspace: ledger — FR-20260426-foo → TRIAGED`
- `⊕ workspace: ledger — FR-20260426-foo → MERGED`
- `⊕ workspace: ledger — FR-20260426-foo → ARCHIVED`
- `⊕ workspace: ledger — reconcile 3 FRs (MERGED)` (for multi-FR reconcile runs)

## FR Cycle Timer (full intake-to-merge timing)

Every FR has one perf_cli run that measures the full cycle: from intake open
to merge. This is separate from each agent's own short-lived perf runs — it
spans the entire FR lifecycle, including all human approval gates.

### Protocol

1. **Intake starts the cycle timer** on FR open:
   ```
   C:\G\python.exe f:\⊕Workspace\src\utils\perf_cli.py start "fr-cycle-<FR-ID>"
   ```
   Stash the returned run_id in the ledger header's `Cycle timer` field and in
   the registry row (Artifacts section of the ledger as well).

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
   - Reads the registry for FRs in `TYLER_APPROVED` or `AUTO_REVIEWED` state
     with an open (unclosed) Cycle timer
   - Queries GitHub via `mcp_github` tools for each PR's `merged_at` timestamp
   - For any merged PR, closes the cycle timer with `--at <merged_at>` to
     backfill the true merge time
   - Updates the ledger: state → MERGED → CLOSED, appends Event Log entry
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
2. ⊕workspace-intake: triage, record in registry as TRIAGED, ask Tyler to confirm scope
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
14. ⊕workspace-ci: merge PRs, delete branches + worktrees, state → MERGED → SOAKING.
    Records `Merged at` timestamp in the FR ledger header. FR remains visible on
    the portal FR panel with "Soaking for Xd Yh" badge.
15. Tyler: exercises the feature on main for as long as he wants.
16. Tyler: "signed off on FR-<ID>"  ← GATEWAY (post-soak)
17. ⊕workspace-ci: records `Signed off at` timestamp, state → SIGNED_OFF → ARCHIVED.
    FR drops off active portal panel; ledger file persists in repo as permanent history.
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
| `⊕workspace-commitment` | Protected commit batching inside an active FR branch. |
| `⊕workspace-security` | Security gate invoked by reviewer; can block before merge. |
| `⊕workspace-alignment` | Consistency gate invoked by reviewer for cross-project FRs. |

## Hard Rules (apply to every agent)

- NEVER start implementation before the FR is in `BRANCHED` state.
- NEVER push or merge directly to `main` in any repo — every change goes
  through a PR with a green `test` status check.
- NEVER merge a PR that is not in `TYLER_APPROVED` state.
- NEVER merge a PR while its required `test` status check is red or pending.
- NEVER archive an FR before it reaches `SIGNED_OFF`. Merged ≠ done.
- NEVER let two agent sessions write to the same worktree.
- NEVER edit the registry except via `⊕workspace-intake` or `⊕workspace-ci`.
- NEVER edit past Event Log entries in an FR ledger — append only.
- ALWAYS read the FR's ledger before acting on the FR.
- ALWAYS append an Event Log entry to the FR's ledger after acting.
- ALWAYS include the FR ID in commit messages and PR titles.
- ALWAYS record `Merged at` (ISO-8601) in the ledger header when transitioning
  to `SOAKING`, and `Signed off at` when transitioning to `SIGNED_OFF`.
- ALWAYS read `f:\.github\FEATURE_REQUESTS.md` before starting work to check
  for conflicts.
