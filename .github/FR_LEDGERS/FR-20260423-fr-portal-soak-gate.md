# FR-20260423-fr-portal-soak-gate — FR Hyperledger Portal View + SOAK/SIGNED_OFF Gate

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260423-fr-portal-soak-gate
- **Title:** FR Hyperledger Portal View + SOAK/SIGNED_OFF Gate
- **Type:** feature
- **Risk:** medium
- **Projects:** ⊕Workspace
- **State:** SOAKING
- **Branch:** feature/FR-20260423-fr-portal-soak-gate (merged & deleted)
- **PRs:** https://github.com/tylerdrakemusic/-Workspace/pull/12 (merged @ fd83eef)
- **Cycle timer:** 27eebf70-f4a2-4d8b-b9be-ab3c6b26ce5a
- **Opened:** 2026-04-23
- **Last updated:** 2026-04-24
- **Merged at:** 2026-04-24T00:48:48Z
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. **Portal panel exists.** `f:\⊕Workspace\reports\portal.html` renders a new
   "Feature Requests" panel that lists all active FRs (any state other than
   `SIGNED_OFF` / `CLOSED` / `ARCHIVED`).
2. **Per-FR card shows:** short description (title + one-line summary), current
   state, branch name, merge-to-main timestamp (if merged), soak duration
   (time since merge, if in `SOAKING`), and a link to the ledger file.
3. **Data source.** Panel is generated from `FEATURE_REQUESTS.md` registry
   + `FR_LEDGERS/*.md` ledger headers — no new DB table required. Generation
   is idempotent and runs on portal refresh (or via a dedicated build script).
4. **New states added to the state machine:** `MERGED → SOAKING → SIGNED_OFF → ARCHIVED`.
   `SOAKING` = merged to main, awaiting Tyler's post-merge "confirmed in solution"
   signoff. `SIGNED_OFF` = Tyler verified the feature is live on main.
   `ARCHIVED` = drops off active portal view; ledger file remains.
5. **Flow instructions updated.** `f:\⊕Workspace\.github\instructions\feature-request-flow.instructions.md`
   reflects the new states, diagrams, gateway list, and agent responsibility
   matrix. The "Approve PR" + "Approve merge" gateways are preserved; a new
   "Post-soak signoff" gateway is added as the final human gate.
6. **Template + registry schema updated.** `FR_LEDGERS/_TEMPLATE.md` gains a
   `Merged at` and `Signed off at` header field. `FEATURE_REQUESTS.md` Active
   table gains a `Merged` column (ISO date, or `—`). `SIGNED_OFF` FRs move to
   Archive. CI closes the cycle timer on MERGED (unchanged) but a new agent
   capability closes the FR fully at SIGNED_OFF.
7. **Backward-compatible.** Existing archived FRs (already `MERGED` / `CLOSED`)
   render correctly in the new panel under an "Already signed off / archived"
   bucket or are excluded; no data migration required beyond additive header
   fields left blank.
8. **Soak duration is visible.** For each FR in `SOAKING`, the portal card
   displays "Soaking for Xd Yh" (humanized) so Tyler can see how long a feature
   has been live before signoff.
9. **Self-hosting.** This FR's own ledger entry must appear in the new portal
   panel after merge (proof that the feature works on itself).

### Concurrency Notes

- Conflicts with: **FR-20260423-feature-request-flow-checkout** (also edits
  `feature-request-flow.instructions.md`). That FR is currently `OPEN — needs
  proper branch` (edits landed on main). New work must rebase on current main
  which already contains the `BRANCH_CHECKED_OUT` addition — no live branch
  conflict, but reviewer should confirm state-machine diagram doesn't lose
  `BRANCH_CHECKED_OUT` when adding `SOAKING` / `SIGNED_OFF`.
- Conflicts with: **FR-20260422-playwright-mcp-setup** (`REVIEW_REQUESTED`) —
  touches ⊕Workspace but different files (no conflict).
- Depends on: none
- Touches `portal.html` — also modified by Band Mgmt Panel and Agent Ops work
  already merged. Rebase on current main before implementation.

### Deliverable Tracker

| #   | Deliverable                                                        | Owner                  | Status      | Proof | Updated    |
| --- | ------------------------------------------------------------------ | ---------------------- | ----------- | ----- | ---------- |
| AC1 | Portal panel renders in `reports/portal.html`                      | ⊕workspace-orchestrator| not-started | —     | 2026-04-23 |
| AC2 | Per-FR card shows desc / state / branch / merged / soak / ledger   | ⊕workspace-orchestrator| not-started | —     | 2026-04-23 |
| AC3 | Generation pipeline (parse registry + ledger headers)              | ⊕workspace-orchestrator| not-started | —     | 2026-04-23 |
| AC4 | State machine gains SOAKING / SIGNED_OFF / ARCHIVED                | ⊕workspace-orchestrator| not-started | —     | 2026-04-23 |
| AC5 | `feature-request-flow.instructions.md` updated                     | ⊕workspace-orchestrator| not-started | —     | 2026-04-23 |
| AC6 | `_TEMPLATE.md` + registry schema get `Merged` / `Signed off` fields| ⊕workspace-orchestrator| not-started | —     | 2026-04-23 |
| AC7 | Backward-compat for existing archive entries                       | ⊕workspace-orchestrator| not-started | —     | 2026-04-23 |
| AC8 | Soak duration humanized on card                                    | ⊕workspace-orchestrator| not-started | —     | 2026-04-23 |
| AC9 | Self-hosting: this FR appears in panel post-merge                  | ⊕workspace-orchestrator| not-started | —     | 2026-04-23 |

### Tyler's Original Request

> we seem to be creating a hyperledger for the feature requests of this project. It should be integrated into the portal interface, so Tyler can keep track of features perform signoff. Also I have signed off on proofs and then come to see the feature vanish because of merge. I need to must allow a feature to soak into the solution before signing off on it. It would help to have a short feature description, status, branch, when it was merged to main to help me provide sign off. Once I've signed off I expect the feature to remain, I don't need it in the FR view however. Lots to digest, but let's take it through FR flow. I will let you implement in isolation as this is a powerful feature.

### Pre-authorized gates (Tyler)

- **Scope approval:** PRE-AUTHORIZED ("I will let you implement in isolation
  as this is a powerful feature"). Intake proceeds straight to CI.
- **Remaining Tyler gates:** approve merge, final post-soak signoff.

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-23T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triaged, scope pre-authorized by Tyler → TRIAGED

**Details:**
- Scope: ⊕Workspace only (portal HTML, FR flow instructions, registry
  schema, ledger template, generation script)
- Acceptance criteria drafted (9 items, see Header)
- Concurrency: flagged overlap with FR-20260423-feature-request-flow-checkout
  (same instructions file — but that FR's edits already landed on main, so
  rebase-on-main resolves cleanly). No live branch conflict.
- Cycle timer started: 27eebf70-f4a2-4d8b-b9be-ab3c6b26ce5a
- Tyler pre-authorized scope gate — proceeding straight to CI for branch
  creation. Remaining Tyler gates: approve merge, post-soak signoff.

**Next:** → ⊕workspace-ci: create branch + worktree + draft PR

---

### 2026-04-23T00:00:00Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** TRIAGED → BRANCHED (isolated worktree + branch created, draft PR opening)

**Details:**
- Verified local `main` == `origin/main` (0 ahead / 0 behind) — no rebase needed
- Branch: `feature/FR-20260423-fr-portal-soak-gate` created from `main` @ `176aacd`
- Worktree: `F:\worktrees\FR-20260423-fr-portal-soak-gate\workspace`
- Initial commit brings the ledger file onto the branch (was untracked on main)
- Draft PR: https://github.com/tylerdrakemusic/-Workspace/pull/12

**Next:** → ⊕workspace-orchestrator: begin implementation per Acceptance Criteria

---

### 2026-04-23T18:30:00Z — ⊕workspace-overseer

**Event:** state-transition

**Summary:** BRANCHED → REVIEW_REQUESTED (implementation complete in isolation)

**Details:**
- AC4 (state machine): added SOAKING / SIGNED_OFF / ARCHIVED states to
  `feature-request-flow.instructions.md` (diagram + state table)
- AC5 (flow instructions): added post-soak signoff as Tyler's gate #5;
  updated happy-path flow steps 14-17; tightened hard rules
- AC6 (template + registry): `_TEMPLATE.md` and this FR's ledger header
  gained `Merged at` / `Signed off at` fields; `FEATURE_REQUESTS.md` states
  section documents new terminal flow + soak rationale
- AC1-AC3, AC8 (portal panel + data source + soak humanizer): new
  `tools/fr_dashboard.py` parses all `FR_LEDGERS/*.md` headers, renders
  `reports/fr_dashboard.html` with active-FR cards (title/summary/state/
  branch/PR/opened/merged/signoff/ledger-link) and collapsed archive section.
  SOAKING cards show "Soaking for Xd Yh" humanized duration.
- AC2: CTA block on SOAKING cards tells Tyler exactly how to sign off.
- Registered in `dashboard.json` as `fr-board` (static_html, category=workflow,
  icon=📋). Portal integration landed on branch; auto-activates at merge time
  because `dashboard_registry.py` scans the main checkout's dashboard.json.
- AC7 (backward compat): archived entries with legacy `CLOSED` state render
  in the Archived section; missing `Signed off at` / `Merged at` fields
  degrade gracefully to "—".
- AC9 (self-hosting): this FR's own ledger appears on the generated board
  (15 FRs total detected; this one in Active bucket in `BRANCHED` state).
- Commit: 5f3ad82 on `feature/FR-20260423-fr-portal-soak-gate`, pushed.
- PR #12 updated via branch push. Marked ready for review.

**Next:** → ⊕workspace-reviewer: run auto-review (alignment + security + tests + proof)

## Artifacts

<!-- APPEND-ONLY. Links to concrete evidence. -->

- **Perf runs:** 27eebf70-f4a2-4d8b-b9be-ab3c6b26ce5a — FR cycle timer (intake → merge)
- **Proof artifacts:** —
- **PRs:** pending (CI handoff)
- **Commits:** —
- **Reports / dashboards:** target = `f:\⊕Workspace\reports\portal.html` (new FR panel)

### 2026-04-24T00:50:00Z — ⊕workspace-overseer

**Event:** state-transition

**Summary:** Tyler approved merge; PR #12 merged into main → SOAKING

**Details:**
- Merge commit: fd83eef
- PR #12 auto-closed by GitHub
- Feature branch deleted (local + remote)
- Scope delivered: FR board dashboard, signoff CLI, portal server with live POST signoff button, compound-state parser fix, 7-ledger legacy backfill

**Next:** awaiting Tyler: exercise feature on main, then click ✓ Sign off in the FR Board (or run tools/fr_signoff.py).
