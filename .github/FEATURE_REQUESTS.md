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
| FR-20260509-portal-hygiene-sprint | ⊕Workspace Portal Hygiene Sprint — desktop launcher, studio dedup, biomarker live server, Agent Ops sync, console errors | fix + chore | ⊕Workspace, ❤Music, ∞Life | MERGED | fix/workspace/fr-20260509-portal-hygiene-sprint | #113, #20, #35 | ⊕workspace-overseer | 2026-05-09 | 2026-05-09 |
| FR-20260506-master-sync-logging | Add execution-layer logging to nightly master sync | chore | ∞Life | BRANCHED | chore/life/fr-20260506-master-sync-logging | pending | ⊕workspace-overseer | 2026-05-06 | 2026-05-06 |
| FR-20260506-trainerize-workout-sync | Trainerize Workout Sync for ∞Life (Auth + Workout Import) | feature | ∞Life | REVIEW_REQUESTED | feature/life/fr-20260506-trainerize-workout-sync | [Life#14](https://github.com/tylerdrakemusic/Life/pull/14) | ⊕workspace-overseer | 2026-05-06 | 2026-05-06 |
| FR-20260505-mfp-nutrition-sync-fix | Fix MFP Nutrition Trend Live Sync (Auth Repair + Daily Auto-Refresh) | fix | ∞Life | TRIAGED | pending | pending | ⊕workspace-intake | 2026-05-05 | 2026-05-05 |
| FR-20260505-distribution-platform-comparison | Distribution Platform Comparison — DistroKid vs TuneCore vs CD Baby | chore | ❤Music | AUTO_REVIEWED | chore/music/fr-20260505-distribution-platform-comparison | [Music#32](https://github.com/tylerdrakemusic/Music/pull/32) (draft) | ⊕workspace-reviewer | 2026-05-05 | 2026-05-05 |
| FR-20260430-grill-me-intake | Integrate grill-me skill into intake Phase A | feature | ⊕Workspace | MERGED → CLOSED | chore/ledger-FR-20260430-grill-me-intake-open | [-Workspace#72](https://github.com/tylerdrakemusic/-Workspace/pull/72) (merged) | ⊕workspace-intake | 2026-04-30 | 2026-04-30 |
| FR-20260429-dashboard-panel-priority | Dashboard Panel Priority Reorder — Value-Aligned Left Sidebar | feature | ⊕Workspace + all projects | MERGED → CLOSED | feature/life/dashboard-panel-priority, feature/heartmusic/gig-inventory-checklist, fix/quantum/qft-gate-deprecation, feature/manifest/dashboard-panel-priority, chore/ledger-FR-20260428-shors-monthly-qpu-bench-open | pending PRs | ⊕workspace-overseer | 2026-04-29 | 2026-04-29 |
| FR-20260428-shors-monthly-qpu-bench | Shor's Monthly QPU Benchmark + Live Dashboard Redesign | feature | ⟨ψ⟩Quantum | REVIEW_REQUESTED | feature/quantum/shors-monthly-bench | PR #9 open | ⊕workspace-overseer | 2026-04-28 | 2026-04-28 |
| FR-20260428-quantum-cache-rebuild | ty_string_cache Cleanup + Band-Aware IBM Quantum Cache Filler | fix+feature | ⟨ψ⟩Quantum | DONE | feature/quantum/cache-rebuild | PR #7, #8 merged | ⊕workspace-overseer | 2026-04-28 | 2026-04-28 |
| FR-20260428-gig-inventory-checklist | Gig Inventory Checklist Tab in Band Management Panel | feature | ❤Music | CLOSED | feature/heartmusic/gig-inventory-checklist | [Music#20](https://github.com/tylerdrakemusic/Music/pull/20) (merged) | ❤music-orchestrator | 2026-04-28 | 2026-04-28 |
| FR-20260426-portal-icon-design | Portal Icon Design — AI-generated icon for portal.html favicon and desktop shortcut | feature | ⊕Workspace | MERGED → CLOSED | feature/workspace/portal-icon-design | https://github.com/tylerdrakemusic/-Workspace/pull/58 | ⊕workspace-ci | 2026-04-26 | 2026-04-27 |
| FR-20260426-chord-sheets-from-templates | Generate Chord Sheet DOCX Files from All Song Templates | chore | ❤Music | MERGED → CLOSED | chore/heartmusic/sheet-music-from-templates | https://github.com/tylerdrakemusic/Music/pull/15 | ⊕workspace-ci | 2026-04-26 | 2026-04-26 |
| FR-20260503-studio-equipment-panel | Studio Equipment Panel — equipment CRUD + mic config print button | feature | ❤Music, ⊕Workspace | MERGED → CLOSED | feature/heart-music/studio-equipment-panel, feature/workspace/studio-equipment-panel | [Music#28](https://github.com/tylerdrakemusic/Music/pull/28), [-Workspace#89](https://github.com/tylerdrakemusic/-Workspace/pull/89) | ❤music-orchestrator | 2026-05-03 | 2026-05-03 |
| FR-20260503-studio-panel-enhancements | Studio Panel Enhancements — new gear, context favicons, tab order, HyperThreat categories | feature | ❤Music | MERGED → CLOSED | [feature/heartmusic/studio-panel-enhancements](https://github.com/tylerdrakemusic/Music/tree/feature/heartmusic/studio-panel-enhancements) | [Music#29](https://github.com/tylerdrakemusic/Music/pull/29) | ⊕workspace-overseer | 2026-05-03 | 2026-05-03 |
| FR-20260503-studio-panel-category-ci | Studio panel category normalization + CI server auto-restart on merge | fix + chore | ❤Music, ⊕Workspace | TRIAGED | — | — | ⊕workspace-intake | 2026-05-03 | 2026-05-03 |
| FR-20260503-lily-prompt-externalization | Lily Portrait: Externalize Positive Prompt + Modal UI Editor + DB Sync | feature | 👁AI-Manifest | AUTO_REVIEWED | feature/manifest/lily-prompt-externalization | [AI-Manifest#18](https://github.com/tylerdrakemusic/AI-Manifest/pull/18) | 👁ai-manifest-orchestrator | 2026-05-03 | 2026-05-04 |
| FR-20260503-nova-biomarker-portrait | ∞Life Nova Biomarker Portrait System — AI persona portrait panel mirroring Lily architecture | feature | ∞Life | MERGED | feature/life/nova-biomarker-portrait | [Life#9](https://github.com/tylerdrakemusic/Life/pull/9) (merged) | ⊕workspace-ci | 2026-05-03 | 2026-05-03 |
| FR-20260503-lily-edit-btn-overlay | Lily edit-prompt button — portrait overlay top-right, matching Nova bio-panel | fix/UX | 👁AI-Manifest | MERGED → CLOSED | feature/ai-manifest/lily-edit-btn-overlay | [AI-Manifest#19](https://github.com/tylerdrakemusic/AI-Manifest/pull/19) (merged) | ⊕workspace-overseer | 2026-05-03 | 2026-05-03 |




## Archive

| FR ID | Title | Type | Projects | Final State | PRs / Merge SHA | Opened | Closed |
|-------|-------|------|----------|-------------|-----------------|--------|--------|
| FR-20260504-local-ollama-enablement | Local Ollama enablement for todo priority scoring (setup + validation) | feature | 👁AI-Manifest, ⊕Workspace | MERGED → CLOSED | [AI-Manifest#23](https://github.com/tylerdrakemusic/AI-Manifest/pull/23) (squash 113db852) + [-Workspace#109](https://github.com/tylerdrakemusic/-Workspace/pull/109) (squash f68ee5b3) | 2026-05-04 | 2026-05-04 |
| FR-20260504-bulk-score-existing-todos | Bulk-score existing todos | feature | 👁AI-Manifest | MERGED → CLOSED | [AI-Manifest#22](https://github.com/tylerdrakemusic/AI-Manifest/pull/22) (squash a5501c94) | 2026-05-04 | 2026-05-04 |
| FR-20260504-executive-panel-redesign | Executive Panel Redesign v2 — priority weights, add-todo UI, ⊕Workspace+👁AI-Manifest cards, Lily voice lock, glassmorphism, /new-fr next-priority workflow | feature | 👁AI-Manifest, ⊕Workspace | MERGED → CLOSED | [AI-Manifest#20](https://github.com/tylerdrakemusic/AI-Manifest/pull/20) (squash a92bbfcc) + [-Workspace#104](https://github.com/tylerdrakemusic/-Workspace/pull/104) (squash 2d9e4bb4) | 2026-05-04 | 2026-05-04 |
| FR-20260503-mic-config-template | 1-page printable mic configuration tracking template (Hyperthreat Studios) | feature | ❤Music, ⊕Workspace | MERGED | [Music#26](https://github.com/tylerdrakemusic/Music/pull/26) (squash 74ee6b1) + [-Workspace#86](https://github.com/tylerdrakemusic/-Workspace/pull/86) (squash cf94b99) | 2026-05-03 | 2026-05-03 |
| FR-20260502-import-originals-lyrics | Import Originals Lyrics from `❤Music/lyrics/` into Catalog (+ relocate People*.pdf to covers/) | feature | ❤Music | MERGED → DONE | [Music#25](https://github.com/tylerdrakemusic/Music/pull/25) (merged) + [-Workspace#83](https://github.com/tylerdrakemusic/-Workspace/pull/83) (merged) | 2026-05-02 | 2026-05-02 |
| FR-20260501-weight-trend-sync-fix | Restore Weight Trend live sync (Withings + Garmin) | fix | ∞Life | MERGED | [Life#8](https://github.com/tylerdrakemusic/Life/pull/8) (squash 3029166f) | 2026-05-01 | 2026-05-01 |
| FR-20260430-quantum-skip-slow-tests | Skip @slow tests by default in Quantum CI (pytest.ini) | chore | ⟨ψ⟩Quantum | MERGED → CLOSED | Quantum#13 (squash 69475a6) | 2026-04-30 | 2026-04-30 |
| FR-20260430-quantum-dashboard-gitignore | gitignore generated benchmark_dashboard.html (regen-only) | chore | ⟨ψ⟩Quantum | MERGED → CLOSED | Quantum#14 (squash ac2b74f) | 2026-04-30 | 2026-04-30 |
| FR-20260430-vqe-aer-bench | VQE for H₂ + LiH (Aer baseline + dashboard panel) | feature | ⟨ψ⟩Quantum | MERGED → CLOSED | Quantum#12 (merge 9b8df2e) | 2026-04-30 | 2026-04-30 |
| FR-20260430-grill-me-intake | Integrate grill-me skill into intake Phase A | feature | ⊕Workspace | MERGED → CLOSED | -Workspace#72 (merge 9b9870e) | 2026-04-30 | 2026-04-30 |
| FR-20260428-gig-inventory-checklist | Gig Inventory Checklist Tab in Band Management Panel | feature | ❤Music | MERGED → CLOSED | Music#20 (merged by Tyler 2026-04-28) | 2026-04-28 | 2026-04-28 |
| FR-20260428-gig-inventory-checklist | Gig Inventory Checklist Tab in Band Management Panel | feature | ❤Music | MERGED → CLOSED | Music#20 (merged by Tyler 2026-04-28) | 2026-04-28 | 2026-04-28 |
| FR-20260427-quantum-rt-fallback-docs | quantum_rt: document secrets fallback paths explicitly | chore | ⟨ψ⟩Quantum | MERGED → CLOSED | Quantum#5 (Tyler signed off 2026-04-28) | 2026-04-27 | 2026-04-28 |
| FR-20260426-sheet-music-catalog | Add Original Sheet Music to ❤Music Catalog | chore | ❤Music | MERGED → CLOSED | Music#— (Tyler signed off 2026-04-28) | 2026-04-26 | 2026-04-28 |
| FR-20260428-pandora-amp-claim | Log completed Pandora AMP artist claim for Tyler James Drake | chore | ❤Music | MERGED → CLOSED | Music#— (squash ed82bc6) | 2026-04-28 | 2026-04-28 |
| FR-20260427-fr-flow-auto-ledger-hygiene | FR Flow: Auto Ledger State PR + Post-Merge Hygiene | chore | ⊕Workspace | MERGED → CLOSED | -Workspace#64 (squash 8197eb75) | 2026-04-27 | 2026-04-28 |
| FR-20260427-print-setlist-button | Add Print Button to Setlist in Band Management Panel | feature | ❤Music | MERGED → CLOSED | Music#19 (squash 850313fc) | 2026-04-27 | 2026-04-28 |
| FR-20260427-originals-artwork-ingest | Originals Artwork Ingest — catalog storage + audio embed for all Tyler James Drake songs | chore | ❤Music | MERGED → CLOSED | Music#18 (squash dd410156) | 2026-04-27 | 2026-04-27 |
| FR-20260426-todo-mark-done-sync | fix(todos): mark-done sync — stale IDs, progress bar, HTTP 404 | fix | 👁AI-Manifest | MERGED → CLOSED | AI-Manifest#14 (merged by Tyler 2026-04-26) | 2026-04-26 | 2026-04-26 |
| FR-20260426-huggingface-image-integration | HuggingFace Image Generation Client — ⊕Workspace Integration | feature | ⊕Workspace | MERGED → CLOSED | -Workspace#47 (squash 3f7a2efc) | 2026-04-26 | 2026-04-26 |
| FR-20260426-todo-db-cards-executive-panel | Todo DB Cards: Executive Panel Interactive Close + DB Migration from Flat Files | feature | 👁AI-Manifest | MERGED → CLOSED | AI-Manifest#12 (squash d7b710d6) + -Workspace#52 (diagrams ab4f176b) | 2026-04-26 | 2026-04-26 |
| FR-20260426-lily-portrait-executive-brief | Lily Portrait — AI-generated persona image in Executive Audio Brief portal | feature | 👁AI-Manifest | MERGED → CLOSED | AI-Manifest#11 (squash 208daa25) | 2026-04-26 | 2026-04-26 |
| FR-20260426-dalle3-image-integration | DALL-E 3 Image Generation Client — ⊕Workspace Integration | feature | ⊕Workspace | MERGED → CLOSED | -Workspace#48 (squash 7f58f5d8) | 2026-04-26 | 2026-04-26 |
| FR-20260426-biomarker-external-portal | External Portal Integration for Biomarker Health Panel | feature | ∞Life | MERGED → CLOSED | Life#4 (merge 25e39a2) | 2026-04-26 | 2026-04-26 |
| FR-20260425-guitar-trainer-db-migration | Guitar Trainer: Full DB Migration + Data Recovery + Card CRUD UI | feature | ❤Music | MERGED → CLOSED | Music#8 (squash 61f2734f) | 2026-04-25 | 2026-04-26 |
| FR-20260429-artist-profile-create | Create ARTIST_PROFILE.json + populate artist_profiles DB from linkTyler.json | chore | ❤Music | MERGED → CLOSED | Music#24 (squash 6722e42) | 2026-04-29 | 2026-04-29 |
| FR-20260429-hyperthreat-studios-doc | Document Hyperthreat Studios in ARTIST_PROFILE.json (name + website, third-party business) | chore | ❤Music | MERGED → CLOSED | Music#24 (squash 6722e42) | 2026-04-29 | 2026-04-29 |
| FR-20260425-architecture-beautifier-styling | Architecture Beautifier: Self-Mutating Style Guide + Re-Beautify All 18 Diagrams | feature | ⊕Workspace | MERGED → CLOSED | -Workspace#41 (squash 64dc7374) | 2026-04-25 | 2026-04-26 |
| FR-20260426-reconcile-gaps-ledgers-todos | Reconcile Gaps: Agent Ops Monitor, FR Ledgers, and All-Project TODOs | chore | ⊕Workspace, ❤Music, ∞Life, ⟨ψ⟩Quantum, 👁AI-Manifest | MERGED → CLOSED | N/A — markdown-only, Tyler signed off 2026-04-26 | 2026-04-26 | 2026-04-26 |
| FR-20260426-executive-audio-brief-panel | Executive Audio Brief Panel — per-project TODO+human todo audio brief via ElevenLabs | feature | 👁AI-Manifest, ⊕Workspace | MERGED → CLOSED | AI-Manifest#7 (merged 21c08f98) | 2026-04-26 | 2026-04-26 |
| FR-20260425-guitar-trainer-data-to-db | Guitar Trainer exercise data should not be tracked by git | chore | ❤Music | CLOSED (superseded by FR-20260425-guitar-trainer-db-migration) | N/A | 2026-04-25 | 2026-04-26 |
| FR-20260425-architecture-review-agents | Architecture Review + Beautifier Agents in FR Flow (.mmd diagrams stay in sync) | feature | ⊕Workspace | PARTIAL_MERGED → CLOSED | -Workspace#38 (squash 5a5b48e8) — AC1–AC8 delivered; AC9–AC12 deferred to FR-20260425-architecture-beautifier-styling | 2026-04-25 | 2026-04-26 |
| FR-20260425-mermaid-diagrams-integration | Mermaid Diagrams Integration (replaces Unified Benchmarks panel) | feature | ⊕Workspace | MERGED | -Workspace#35→#37 (merged @ bccbb71) | 2026-04-25 | 2026-04-26 |
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
