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
| FR-20260425-guitar-trainer-db-migration | Guitar Trainer: Full DB Migration + Data Recovery + Card CRUD UI | feature | ❤Music | BRANCHED | feature/heartmusic/guitar-trainer-db-migration | https://github.com/tylerdrakemusic/Music/pull/8 | ⊕workspace-intake | 2026-04-25 | 2026-04-25 |
| FR-20260425-guitar-trainer-data-to-db | Guitar Trainer exercise data should not be tracked by git | chore | ❤Music | TRIAGED (superseded by FR-20260425-guitar-trainer-db-migration — recommend close) | chore/heartmusic/guitar-trainer-data-to-db | pending | ⊕workspace-intake | 2026-04-25 | 2026-04-25 |
| FR-20260425-mermaid-diagrams-integration | Mermaid Diagrams Integration (replaces Unified Benchmarks panel) | feature | ⊕Workspace | IN_PROGRESS | feature/workspace/mermaid-diagrams-integration | https://github.com/tylerdrakemusic/-Workspace/pull/35 | ⊕workspace-overseer | 2026-04-25 | 2026-04-26 |
| FR-20260425-architecture-review-agents | Architecture Review + Beautifier Agents in FR Flow (.mmd diagrams stay in sync) | feature | ⊕Workspace | REVIEW_REQUESTED | feature/workspace/architecture-review-agents | https://github.com/tylerdrakemusic/-Workspace/pull/38 | ⊕workspace-overseer | 2026-04-25 | 2026-04-25 |



## Archive

| FR ID | Title | Type | Projects | Final State | PRs / Merge SHA | Opened | Closed |
|-------|-------|------|----------|-------------|-----------------|--------|--------|
| FR-20260425-guitar-trainer-metronome | Add metronome to Guitar Trainer portal panel | feature | ❤Music | MERGED → CLOSED | feature/heartmusic/guitar-trainer-metronome — Tyler signed off 2026-04-25 | 2026-04-25 | 2026-04-25 |
| FR-20260425-band-mgmt-playback-sheets | Band Management Panel: Per-Row Audio Playback + Sheet Music Viewer | feature | ❤Music | MERGED → CLOSED | Music#7 — Tyler signed off 2026-04-25 | 2026-04-25 | 2026-04-25 |
| FR-20260425-intake-interview-driven | Make Intake More Interview-Driven and Less Assumption-Heavy | chore | ⊕Workspace | MERGED → CLOSED | -Workspace#32 — Tyler signed off 2026-04-25 | 2026-04-25 | 2026-04-25 |
| FR-20260425-guitar-trainer-panel-startup | Guitar Trainer Panel: Server Auto-Start + Remove Live-Dash Chrome | fix | ❤Music, ⊕Workspace | MERGED → CLOSED | -Workspace#29 (squash 229807ac) | 2026-04-25 | 2026-04-25 |
| FR-20260425-guitar-trainer-album-art | Guitar Trainer — Album Art Display from Embedded Audio Metadata | feature | ❤Music | MERGED → CLOSED | Music#3 (merged 08cfd48) | 2026-04-25 | 2026-04-25 |
| FR-20260425-guitar-trainer-new-card-timestamp | Guitar Trainer — "Add New Card" uses wrong song segment timestamps | fix | ❤Music | MERGED → CLOSED | Music#2 (merged c03de6f) | 2026-04-25 | 2026-04-25 |
| FR-20260425-live-fr-ledger-panel | Live FR Ledger Panel — Synchronous CI Observability + In-Panel Signoff | feature | ⊕Workspace | MERGED → CLOSED | -Workspace#23 | 2026-04-25 | 2026-04-25 |
| FR-20260425-ci-test-harness-gateway | CI Test Harness Gateway + Branch Protection (All 5 Repos) | feature | All 5 | MERGED → CLOSED | -Workspace#24 (d780d9a8), Life#3 (ce448ea), Music#4, Quantum#2, AI-Manifest#6 — 4 public branch-protected, ∞Life pre-push hook + doc, AC7 smoke verified merge-block (PR#25 405) | 2026-04-25 | 2026-04-25 |
| FR-20260424-infinitelife-db-restore | ∞Life — Restore DB, data sync pipeline, and live Biomarker Dashboard | feature | ∞Life, ⊕Workspace | CLOSED | Life#2 | 2026-04-24 | 2026-04-25 |
| FR-20260424-sqlcipher-mcp-server | Custom SQLCipher MCP Server — encrypted multi-DB access for all workspace DBs | feature | ⊕Workspace | CLOSED (user-config-only, no tracked files) | none | 2026-04-24 | 2026-04-25 |
| FR-20260424-sql-mcp-server | Investigate + Install SQL MCP Server for Workspace | feature | ⊕Workspace | CLOSED | none | 2026-04-24 | 2026-04-25 |
| FR-20260424-todo-ledger-reconcile | Reconcile TODO Lists with FR Ledger + Add ❤Music Human Todos | chore | ⊕Workspace, ❤Music | CLOSED | N/A — markdown-only | 2026-04-24 | 2026-04-25 |
| FR-20260424-cc-prost-setlist-05022026 | CC Prost 05022026 — Setlist DB Update (Revised) | chore | ❤Music | MERGED → CLOSED | merged main 6af031a | 2026-04-24 | 2026-04-25 |
| FR-20260423-band-mgmt-panel-music | Band Management Panel — ❤Music portal pane with multi-band selector, setlist, sheet music links | feature | ❤Music, ⊕Workspace | MERGED → CLOSED | -Workspace#22 | 2026-04-23 | 2026-04-23 |
| FR-20260423-repo-privacy-audit | Repo Privacy Audit — Privatize Sensitive Repos + Agent Awareness | feature | All 5 + .github/ | MERGED → CLOSED | -Workspace#20 @ d092dcd | 2026-04-23 | 2026-04-23 |
| FR-20260422-playwright-mcp-setup | Wire Playwright MCP into workspace — install Node.js + @playwright/mcp + configure mcp.json | chore | ⊕Workspace | MERGED → CLOSED | chore/workspace/playwright-mcp-setup — Tyler signed off 2026-04-25 | 2026-04-22 | 2026-04-25 |
| FR-20260423-living-security-dashboard | Living Security Dashboard + close remediated SQL injection findings (IDs 7–11) | feature | ⊕Workspace | CLOSED (NOT MERGED) | -Workspace#19 — PR closed, work missed scope. Re-open via fresh intake if needed. | 2026-04-23 | 2026-04-23 |
| FR-20260423-fr-state-drift-fix | FR state drift reconciliation (signoff queue accuracy) | chore | ⊕Workspace | MERGED | -Workspace#13 | 2026-04-23 | 2026-04-23 |
| FR-20260423-stash-audit | Audit + drop orphaned git stashes across all projects | chore | All 5 projects | MERGED | -Workspace#15 | 2026-04-23 | 2026-04-23 |
| FR-20260422-music-repo-purge | Purge oversized binaries from ❤Music history | chore | ❤Music | MERGED | force-push @ 0abdef4 | 2026-04-22 | 2026-04-22 |
| FR-20260422-db-backup-strategy | DB backup strategy for all project databases | chore | All 5 projects | CLOSED (rejected — deferred) | N/A | 2026-04-22 | 2026-04-22 |
| FR-20260422-gitignore-sweep | Add .gitignore to all remaining projects | chore | ∞Life, ⟨ψ⟩Quantum, 👁AI-Manifest, ⊕Workspace | CLOSED | e3586e6 / af188c9 / f90f64c / bab2dad | 2026-04-22 | 2026-04-22 |
| FR-20260422-sigil-encoding-map | Sigil Encoding Reference Map | chore | ⊕Workspace | MERGED | -Workspace#4 @ 03d8a9f | 2026-04-22 | 2026-04-22 |
| FR-20260422-github-dir-reconcile | Reconcile Divergent `.github/` Directory Trees | chore | ⊕Workspace | MERGED_PARTIAL (Phase 1 only; Phase 2 infeasible — F: is exFAT, junctions unsupported) | -Workspace#2 @ 2b9e612 | 2026-04-22 | 2026-04-22 |
| FR-20260422-multi-root-workspace | Adopt Multi-Root VS Code Workspace (`.code-workspace`) | chore | ⊕Workspace | MERGED | -Workspace#3 @ 91c0772 + bookkeeping c20ead2; smoke test passed; f:\.github\ deleted | 2026-04-22 | 2026-04-22 |
| FR-20260422-remove-service-label-field | Remove "Service/Label" Field from Password Generator Panel | chore | ⊕Workspace | MERGED | delivered by other agent; confirmed by Tyler | 2026-04-22 | 2026-04-22 |
| FR-20260422-band-mgmt-panel | Band Management Panel (Workspace Portal) | feature | ❤Music, ⊕Workspace | MERGED | delivered inline on main by other agent; confirmed by Tyler | 2026-04-22 | 2026-04-22 |

---

## Concurrency Cap

Maximum **3** FRs may be in `IN_PROGRESS` state simultaneously. Additional
FRs queue in `TRIAGED` state until a slot opens.
