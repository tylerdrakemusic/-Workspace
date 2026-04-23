# Feature Request Registry

Live board of all active feature requests (FRs) across the workspace.
**Single source of truth** — only `⊕workspace-intake` and `⊕workspace-ci`
write to this file. Every agent reads it before starting work.

See `f:\.github\instructions\feature-request-flow.instructions.md` for the
state machine, gateway definitions, and naming rules.

---

## How Tyler Uses This

- **Open a new FR:** ask `⊕workspace-intake` in plain language ("I want X in
  project Y"). The intake agent will triage and ask you to confirm scope.
- **Check status:** ask `⊕workspace-intake` "status of my FRs" or read the
  table below.
- **Approve / request changes / merge:** reply to the relevant handoff or
  review comment with `approve`, `changes requested`, or `merge`.

## States

`OPEN → TRIAGED → BRANCHED → IN_PROGRESS → REVIEW_REQUESTED → AUTO_REVIEWED → TYLER_APPROVED → MERGED → CLOSED`

(`CHANGES_REQUESTED` loops back to `IN_PROGRESS`.)

---

## Active FRs

| FR ID | Title | Type | Projects | State | Branch | PRs | Owner | Opened | Updated |
|-------|-------|------|----------|-------|--------|-----|-------|--------|---------|
| FR-20260422-remove-service-label-field | Remove "Service/Label" Field from Password Generator Panel | chore | ⊕Workspace | TRIAGED | pending | pending | ⊕workspace-intake | 2026-04-22 | 2026-04-22 |
| FR-20260422-band-mgmt-panel | Band Management Panel (Workspace Portal) | feature | ❤Music, ⊕Workspace | REVIEW_REQUESTED | main (inline) | n/a | ⊕workspace-overseer | 2026-04-22 | 2026-04-22 |



## Archive

| FR ID | Title | Type | Projects | Final State | PRs / Merge SHA | Opened | Closed |
|-------|-------|------|----------|-------------|-----------------|--------|--------|
| FR-20260422-music-repo-purge | Purge oversized binaries from ❤Music history | chore | ❤Music | MERGED | force-push @ 0abdef4 | 2026-04-22 | 2026-04-22 |
| FR-20260422-db-backup-strategy | DB backup strategy for all project databases | chore | All 5 projects | CLOSED (rejected — deferred) | N/A | 2026-04-22 | 2026-04-22 |
| FR-20260422-gitignore-sweep | Add .gitignore to all remaining projects | chore | ∞Life, ⟨ψ⟩Quantum, 👁AI-Manifest, ⊕Workspace | CLOSED | e3586e6 / af188c9 / f90f64c / bab2dad | 2026-04-22 | 2026-04-22 |
| FR-20260422-sigil-encoding-map | Sigil Encoding Reference Map | chore | ⊕Workspace | MERGED | [#4](https://github.com/tylerdrakemusic/-Workspace/pull/4) @ 03d8a9f | 2026-04-22 | 2026-04-22 |
| FR-20260422-github-dir-reconcile | Reconcile Divergent `.github/` Directory Trees | chore | ⊕Workspace | MERGED_PARTIAL (Phase 1 only; Phase 2 infeasible — F: is exFAT, junctions unsupported) | [#2](https://github.com/tylerdrakemusic/-Workspace/pull/2) @ 2b9e612 | 2026-04-22 | 2026-04-22 |
| FR-20260422-multi-root-workspace | Adopt Multi-Root VS Code Workspace (`.code-workspace`) | chore | ⊕Workspace | MERGED | [#3](https://github.com/tylerdrakemusic/-Workspace/pull/3) @ 91c0772 + bookkeeping c20ead2; smoke test passed; f:\.github\ deleted | 2026-04-22 | 2026-04-22 |

---

## Concurrency Cap

Maximum **3** FRs may be in `IN_PROGRESS` state simultaneously. Additional
FRs queue in `TRIAGED` state until a slot opens.
