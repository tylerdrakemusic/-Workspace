# FR-20260425-architecture-beautifier-styling — Architecture Beautifier: Self-Mutating Style Guide + Re-Beautify All 18 Diagrams

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260425-architecture-beautifier-styling
- **Title:** Architecture Beautifier: Self-Mutating Style Guide + Re-Beautify All 18 Diagrams
- **Type:** feature
- **Risk:** medium
- **Projects:** ⊕Workspace
- **State:** BRANCHED
- **Branch:** feature/workspace/architecture-beautifier-styling
- **PRs:** https://github.com/tylerdrakemusic/-Workspace/pull/41 (draft)
- **Cycle timer:** 7705dd8d-10dc-4b20-8600-2fb2e602a367
- **Opened:** 2026-04-25
- **Last updated:** 2026-04-26
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria
1. Create `diagrams/STYLE_GUIDE.md` with: per-sigil **muted/pastel** color palette (∞=pastel-blue, ❤=pastel-red/rose, ⟨ψ⟩=pastel-purple/lavender, 👁=pastel-amber, ⊕=pastel-teal — exact hex values defined in the file), concept-category node shapes (agents=stadium, files=rect, DBs=cylinder, integrations=hexagon, external=cloud), edge semantics (sync=solid, async=dotted, dependency=dashed), neutral/base mermaid theme directive (no forced dark/light — viewer's renderer decides), layout conventions.
2. Beautifier `--refresh-knowledge` mode: fetches latest mermaid.js docs/changelog + community style trends, proposes style-guide updates as a unified diff (no silent writes); `--dry-run` mandatory.
3. Self-mutation safety model (looser per Tyler): **any non-destructive change** (additive token additions, new categories, new color entries, new shape mappings) MAY auto-commit when tagged appropriately; destructive/modifying changes (renaming tokens, changing existing palette hex values, removing categories) MUST land via FR/PR; `--dry-run` mandatory for both `--refresh-knowledge` and `--apply-style` modes.
4. Beautifier `--apply-style` mode walks all `diagrams/*.mmd` and brings them into compliance with current style guide (with `--dry-run`); includes the four selected extras: (a) auto-add per-diagram legend (sigil → color key), (b) auto-group nodes by sigil into subgraphs, (c) auto-collapse subgraphs over configurable N nodes, (d) validate syntax via mermaid CLI before write.
5. Re-beautify all 18 existing `diagrams/*.mmd` as proof-in-the-pudding — committed alongside the agent updates so Tyler can SEE the styled result on the diagrams dashboard.

### Concurrency Notes
- Conflicts with: none (CI cleanup branch `chore/workspace/close-fr-architecture-review-agents` for FR-20260425-architecture-review-agents touches different files; this FR's branch will be created off `origin/main` AFTER that cleanup PR merges)
- Depends on: FR-20260425-architecture-review-agents (PR #38 merged; provides the `⊕workspace-architecture-beautifier` agent file this FR extends)

### Deliverable Tracker

| #   | Deliverable                                                              | Owner                              | Status      | Proof | Updated |
| --- | ------------------------------------------------------------------------ | ---------------------------------- | ----------- | ----- | ------- |
| AC1 | `diagrams/STYLE_GUIDE.md` with palette/shapes/edges/theme/layout         | ⊕workspace-architecture-beautifier | not-started | —     | —       |
| AC2 | Beautifier `--refresh-knowledge` mode (diff-only, --dry-run mandatory)    | ⊕workspace-architecture-beautifier | not-started | —     | —       |
| AC3 | Self-mutation safety model (non-destructive auto-commit, destructive=PR) | ⊕workspace-architecture-beautifier | not-started | —     | —       |
| AC4 | Beautifier `--apply-style` mode + 4 extras (legend/group/collapse/validate) | ⊕workspace-architecture-beautifier | not-started | —     | —       |
| AC5 | Re-beautify all 18 existing `diagrams/*.mmd` (proof-in-the-pudding)      | ⊕workspace-architecture-beautifier | not-started | —     | —       |

### Tyler's Original Request
> "I do appreciate the highest quality styling and thematic for architecture considering adjusting the beautifier to be self mutating keeping up with the latest trends and mermaid knowledge as well as applying styling and beautification techniques to the diagrams"

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-25 — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ⊕Workspace (single-project)
- Picks up deferred styling work from FR-20260425-architecture-review-agents (PR #38 merged with only AC1–AC8)
- Tyler interview confirmed:
  - Palette: **muted/pastel** variant of proposed hues (∞=pastel-blue, ❤=pastel-red, ⟨ψ⟩=pastel-purple, 👁=pastel-amber, ⊕=pastel-teal)
  - Self-mutation: **looser** model — auto-commit allowed for any non-destructive change; destructive via PR; --dry-run mandatory
  - Bundle re-beautify: **yes** — this is the follow-up FR, AC5 stays
  - Theme: **neutral/base** — let viewer's renderer decide (no forced dark/light)
  - Extras: legend, group-by-sigil, auto-collapse over N, mermaid CLI validation (4 of 5 optional extras selected)
- Concurrency check: clean (parallel CI cleanup on different branch/files)
- Acceptance criteria drafted and reflect interview answers

**Next:** awaiting Tyler: approve scope

---

### 2026-04-26 — ⊕workspace-ci

**Event:** state-transition

**Summary:** TRIAGED → BRANCHED. Tyler approved both gateways (intake scope + branch cut). Feature branch created off freshly-pulled `main` (`e5ed94be`, post-PR-#40-merge); empty branch pushed; ledger + registry updated.

**Details:**
- Branch: `feature/workspace/architecture-beautifier-styling` (pushed to origin)
- Base commit: `e5ed94be` (PR #40 — close FR-20260425-architecture-review-agents PARTIAL_MERGED)
- Draft PR: https://github.com/tylerdrakemusic/-Workspace/pull/41
- Registry: state cell updated to BRANCHED, branch cell de-suffixed
- Implementation deferred to overseer's next pass per Tyler's instruction

**Next:** ⊕workspace-overseer picks up branch and begins AC1 (`diagrams/STYLE_GUIDE.md`)

---

## Artifacts

<!-- APPEND-ONLY. Links to concrete evidence. -->

- **Perf runs:** 7705dd8d-10dc-4b20-8600-2fb2e602a367 — fr-cycle timer (intake start)
- **Proof artifacts:** —
- **PRs:** https://github.com/tylerdrakemusic/-Workspace/pull/41 (draft)
- **Commits:** b5d49cb — chore(fr): branch FR-20260425-architecture-beautifier-styling (TRIAGED -> BRANCHED)
- **Reports / dashboards:** —
