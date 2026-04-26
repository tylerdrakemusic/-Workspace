# FR-20260425-architecture-review-agents — Architecture Review + Beautifier Agents in FR Flow

## Header

- **FR ID:** FR-20260425-architecture-review-agents
- **Title:** Architecture Review + Beautifier Agents in FR Flow (.mmd diagrams stay in sync)
- **Type:** feature
- **Risk:** medium
- **Projects:** ⊕Workspace
- **State:** TRIAGED
- **Branch:** feature/workspace/architecture-review-agents (pending CI creation)
- **PRs:** pending
- **Cycle timer:** 68252422-8919-4a26-9bf0-3b7d7fa2eb04
- **Opened:** 2026-04-25
- **Last updated:** 2026-04-25
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. New agent file `.github/agents/⊕workspace-architecture-reviewer.agent.md` exists and follows shared-instructions pattern (frontmatter + self-regen block).
2. New agent file `.github/agents/⊕workspace-architecture-beautifier.agent.md` exists and follows shared-instructions pattern.
3. FR flow instructions (`.github/instructions/feature-request-flow.instructions.md`) updated to insert the architecture-review step between implementation (`IN_PROGRESS`) and `⊕workspace-reviewer` (`AUTO_REVIEWED`).
4. New diagram `diagrams/workspace-integrations.mmd` seeded with current cross-project integration points (e.g. ⟨ψ⟩Quantum QRNG → ❤Music signatures, 👁AI-Manifest TTS → ∞Life briefs, ⊕Workspace perf_cli consumed by all projects).
5. Architecture-reviewer is invocable as a subagent and produces a structured impact report: list of `.mmd` files needing update + list of missing diagrams. Report format documented in the agent file.
6. Beautifier produces a styled `.mmd` given a topic + textual description, or rewrites an existing one in place with consistent styling, layout, color, and node-naming conventions.
7. `⊕workspace-reviewer`'s checklist includes "architecture diagrams updated for any architectural change in this PR" and **HARD-BLOCKS merge** when reviewer reports stale diagrams (per Tyler's gateway choice).
8. Tests for both new agents added under `tests/agents/` (existence + frontmatter validity per existing pattern).

### Concurrency Notes
- Conflicts with: none (no other active FR touches `.github/agents/⊕workspace-*` or `.github/instructions/feature-request-flow.instructions.md`)
- Depends on: FR-20260425-mermaid-diagrams-integration (MERGED — provides the 18 .mmd files + diagrams dashboard this FR keeps in sync)

### Deliverable Tracker

| #   | Deliverable                                                                       | Owner                              | Status      | Proof | Updated    |
| --- | --------------------------------------------------------------------------------- | ---------------------------------- | ----------- | ----- | ---------- |
| AC1 | `.github/agents/⊕workspace-architecture-reviewer.agent.md`                        | ⊕workspace-overseer                | not-started | —     | —          |
| AC2 | `.github/agents/⊕workspace-architecture-beautifier.agent.md`                      | ⊕workspace-overseer                | not-started | —     | —          |
| AC3 | FR flow instructions updated to insert architecture-review step                   | ⊕workspace-overseer                | not-started | —     | —          |
| AC4 | `diagrams/workspace-integrations.mmd` seeded                                      | ⊕workspace-architecture-beautifier | not-started | —     | —          |
| AC5 | Architecture-reviewer subagent + structured impact report                         | ⊕workspace-overseer                | not-started | —     | —          |
| AC6 | Beautifier produces styled .mmd from topic+description or rewrites in place       | ⊕workspace-overseer                | not-started | —     | —          |
| AC7 | ⊕workspace-reviewer checklist updated; HARD-BLOCK on stale diagrams               | ⊕workspace-overseer                | not-started | —     | —          |
| AC8 | Tests under `tests/agents/` for both new agents (existence + frontmatter)         | ⊕workspace-overseer                | not-started | —     | —          |

### Tyler's Original Request
> While we're on branch the FR flow may want to check for architectural impacts and update and beautify the .mmd files accordingly when architecture shifts, new dependencies are added, a .mmd for workspace integrations could come in handy in the future as well. Consider adding an architecture review agent and architecture beautifier to the FR flow

---

## Event Log

### 2026-04-25 — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, interview complete, triage complete → TRIAGED

**Details:**
- Scope: ⊕Workspace (cross-project agent infrastructure; no other repos touched in this FR)
- Type: feature; Risk: medium (touches FR flow + reviewer gating logic)
- Interview confirmed (4 questions via vscode_askQuestions):
  - **Agent split:** TWO agents (reviewer + beautifier) — separation of concerns
  - **Blocking behavior:** **HARD-BLOCK merge** when diagrams are stale (not just flag)
  - **workspace-integrations.mmd:** seed in THIS FR (bundled with agents)
  - **Naming:** `⊕workspace-architecture-reviewer` + `⊕workspace-architecture-beautifier`
- Acceptance criteria drafted (8 ACs; AC7 reflects hard-block decision)
- Concurrency check: clean — no overlap with active FRs (guitar-trainer-db-migration is ❤Music-only)
- Builds on FR-20260425-mermaid-diagrams-integration (just merged): 18 .mmd files + diagrams dashboard now exist in `f:\⊕Workspace\diagrams\`
- Cycle timer started: run_id 68252422-8919-4a26-9bf0-3b7d7fa2eb04

**Next:** awaiting ⊕workspace-ci to create branch `feature/workspace/architecture-review-agents` + worktree + draft PR on `tylerdrakemusic/-Workspace`. After BRANCHED, route to `⊕workspace-overseer` for implementation.

---

## Artifacts

- **Perf runs:** 68252422-8919-4a26-9bf0-3b7d7fa2eb04 — fr-cycle-FR-20260425-architecture-review-agents
- **Proof artifacts:** —
- **PRs:** pending CI
- **Commits:** —
- **Reports / dashboards:** existing `f:\⊕Workspace\reports\diagrams_dashboard.html` (target dashboard this FR keeps fresh)
