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
| FR-20260423-audio-brief-base64-embed | Embed TTS Audio as Base64 in Executive Brief Portal HTML | feature | 👁AI-Manifest | CLOSED (redundant) | feature/ai-manifest/audio-brief-base64-embed | [#4](https://github.com/tylerdrakemusic/AI-Manifest/pull/4) | ⊕workspace-overseer | 2026-04-23 | 2026-04-23 |
| FR-20260423-vscode-session-autodetect | Auto-detect live VS Code Copilot chat sessions in agent ops monitor | feature | ⊕Workspace | MERGED | https://github.com/tylerdrakemusic/-Workspace/pull/11 | 5cf3f05 | ⊕workspace-ci | 2026-04-23 | 2026-04-23 |
| FR-20260423-ai-manifest-portal-static-fix | Executive Audio Brief Portal: Static-File Mode Fixes | fix | 👁AI-Manifest | CHANGES_REQUESTED | fix/ai-manifest/portal-static-mode | [#3](https://github.com/tylerdrakemusic/AI-Manifest/pull/3) | ⊕workspace-reviewer | 2026-04-23 | 2026-04-23 |
| FR-20260423-feature-request-flow-checkout | Add BRANCH_CHECKED_OUT state to FR flow instructions | chore | ⊕Workspace | OPEN — needs proper branch (instructions edited directly on main; see ledger note) | none | none | ⊕workspace-ci | 2026-04-23 | 2026-04-23 |
| FR-20260422-playwright-mcp-setup | Wire Playwright MCP into workspace — install Node.js + @playwright/mcp + configure mcp.json | chore | ⊕Workspace | REVIEW_REQUESTED | pending | pending | ⊕workspace-intake | 2026-04-22 | 2026-04-23 |
| FR-20260422-disable-plumbing-agents-dropdown | Disable Plumbing Agents from VS Code Agent Dropdown | chore | ⊕Workspace | TRIAGED | pending | pending | ⊕workspace-intake | 2026-04-22 | 2026-04-22 |



## Archive

| FR ID | Title | Type | Projects | Final State | PRs / Merge SHA | Opened | Closed |
|-------|-------|------|----------|-------------|-----------------|--------|--------|
| FR-20260423-agent-ops-live-session-fix | Fix agent ops live session detection + phantom agent purge | fix | ⊕Workspace | MERGED | [#10](https://github.com/tylerdrakemusic/-Workspace/pull/10) @ 921b891f43d3 | 2026-04-23 | 2026-04-23 |
| FR-20260423-audio-brief-elevenlabs-fix | Fix Executive Audio Brief Dashboard + Centralize ElevenLabs Client | fix | 👁AI-Manifest, ⊕Workspace | CLOSED | [#9](https://github.com/tylerdrakemusic/-Workspace/pull/9) @ d1f15cafa328, [#2](https://github.com/tylerdrakemusic/AI-Manifest/pull/2) @ 162124421e1a | 2026-04-23 | 2026-04-23 |
| FR-20260422-music-repo-purge | Purge oversized binaries from ❤Music history | chore | ❤Music | MERGED | force-push @ 0abdef4 | 2026-04-22 | 2026-04-22 |
| FR-20260423-agent-ops-monitor-sync | Reconcile agent ops monitor with current workspace architecture and improve portal visibility | fix | ⊕Workspace | MERGED | [#7](https://github.com/tylerdrakemusic/-Workspace/pull/7) @ 46c8eed | 2026-04-23 | 2026-04-23 |
| FR-20260422-db-backup-strategy | DB backup strategy for all project databases | chore | All 5 projects | CLOSED (rejected — deferred) | N/A | 2026-04-22 | 2026-04-22 |
| FR-20260422-gitignore-sweep | Add .gitignore to all remaining projects | chore | ∞Life, ⟨ψ⟩Quantum, 👁AI-Manifest, ⊕Workspace | CLOSED | e3586e6 / af188c9 / f90f64c / bab2dad | 2026-04-22 | 2026-04-22 |
| FR-20260422-sigil-encoding-map | Sigil Encoding Reference Map | chore | ⊕Workspace | MERGED | [#4](https://github.com/tylerdrakemusic/-Workspace/pull/4) @ 03d8a9f | 2026-04-22 | 2026-04-22 |
| FR-20260422-github-dir-reconcile | Reconcile Divergent `.github/` Directory Trees | chore | ⊕Workspace | MERGED_PARTIAL (Phase 1 only; Phase 2 infeasible — F: is exFAT, junctions unsupported) | [#2](https://github.com/tylerdrakemusic/-Workspace/pull/2) @ 2b9e612 | 2026-04-22 | 2026-04-22 |
| FR-20260422-multi-root-workspace | Adopt Multi-Root VS Code Workspace (`.code-workspace`) | chore | ⊕Workspace | MERGED | [#3](https://github.com/tylerdrakemusic/-Workspace/pull/3) @ 91c0772 + bookkeeping c20ead2; smoke test passed; f:\.github\ deleted | 2026-04-22 | 2026-04-22 |
| FR-20260422-remove-service-label-field | Remove "Service/Label" Field from Password Generator Panel | chore | ⊕Workspace | MERGED | delivered by other agent; confirmed by Tyler | 2026-04-22 | 2026-04-22 |
| FR-20260422-band-mgmt-panel | Band Management Panel (Workspace Portal) | feature | ❤Music, ⊕Workspace | MERGED | delivered inline on main by other agent; confirmed by Tyler | 2026-04-22 | 2026-04-22 |

---

## Concurrency Cap

Maximum **3** FRs may be in `IN_PROGRESS` state simultaneously. Additional
FRs queue in `TRIAGED` state until a slot opens.
