# FR-20260427-fr-flow-auto-ledger-hygiene — Remedy FR Flow: Auto-Commit Ledger Updates Post-Merge + Hygiene Cleanup After Feature Proven

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260427-fr-flow-auto-ledger-hygiene
- **Title:** Remedy FR Flow: Auto-Commit Ledger Updates Post-Merge + Hygiene Cleanup After Feature Proven
- **Type:** chore
- **Risk:** medium
- **Projects:** ⊕Workspace
- **State:** TRIAGED
- **Branch:** pending
- **PRs:** pending
- **Cycle timer:** 8a695c95-230a-4fcb-88b5-d318f4e41c4a
- **Opened:** 2026-04-27
- **Last updated:** 2026-04-27
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. `⊕workspace-ci` agent instructions updated: after merging a feature PR, the ledger state-transition commit (MERGED / SIGNED_OFF / ARCHIVED) is pushed directly to ⊕Workspace `main` without requiring a separate Tyler approval gate.
2. `feature-request-flow.instructions.md` updated: explicitly states that ledger-only commits to ⊕Workspace `main` (state transitions only — no code changes) bypass Tyler's approval gateways.
3. `⊕workspace-commitment` agent instructions updated: ledger-only commits are excluded from the approval-gate workflow.
4. `⊕workspace-ci` agent instructions updated: after a feature PR is marked MERGED, invoke `⊕workspace-hygiene` to clean up untracked files (test artifacts, `tmp/`, `logs/`) in the affected project's local checkout. Tracked-but-uncommitted files are NOT deleted.
5. The hygiene invocation is scoped: only untracked/ignored files in `tmp/`, `logs/`, and named test artifact patterns — not the entire working tree.
6. All four modified agent/instruction files have the new behavior documented with at least one concrete example or command snippet.

### Concurrency Notes
- Conflicts with: none (⊕Workspace main docs-only change)
- Depends on: none

### Deliverable Tracker

| #   | Deliverable                                                        | Owner              | Status      | Proof | Updated    |
| --- | ------------------------------------------------------------------ | ------------------ | ----------- | ----- | ---------- |
| AC1 | ⊕workspace-ci: auto-push ledger commits to main post-merge        | ⊕workspace-ci      | not-started | —     | —          |
| AC2 | feature-request-flow: ledger-only commits bypass Tyler gate        | ⊕workspace-ci      | not-started | —     | —          |
| AC3 | ⊕workspace-commitment: exclude ledger commits from approval gate  | ⊕workspace-ci      | not-started | —     | —          |
| AC4 | ⊕workspace-ci: invoke hygiene after MERGED                        | ⊕workspace-ci      | not-started | —     | —          |
| AC5 | Hygiene scope limited to untracked tmp/logs/test artifacts only    | ⊕workspace-hygiene | not-started | —     | —          |
| AC6 | All modified files have concrete example or command snippet        | ⊕workspace-ci      | not-started | —     | —          |

### Tyler's Original Request
> "We need to remedy the fr flow, I see too many dangling FR ledgers uncommitted after a feature has been merged. I am ok being out of the loop on ledger updates and merges to main. I also see a lot of dangling uncommitted files that can just be canned after the feature is proven. Perhaps calling the hygiene agent to delete unneeded files in local after a feature is merged."

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-27T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ⊕Workspace (agent instruction files only — no code changes to any project)
- Risk: medium — touches CI agent merge workflow and hygiene invocation logic; incorrect scoping of hygiene cleanup could delete work-in-progress files
- Type: chore
- Acceptance criteria drafted (6 ACs, see Header)
- Concurrency check: clean — no active FRs touching the same agent files
- Interview: skipped — all four triage dimensions (motivation, outcome, scope, boundary) fully stated by Tyler in the request

**Next:** awaiting Tyler scope approval

---

## Artifacts

- **Perf runs:** 8a695c95-230a-4fcb-88b5-d318f4e41c4a — FR-20260427-fr-flow-auto-ledger-hygiene cycle timer
