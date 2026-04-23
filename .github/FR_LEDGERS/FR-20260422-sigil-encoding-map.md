# FR-20260422-sigil-encoding-map — Sigil Encoding Reference Map

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260422-sigil-encoding-map
- **Title:** Sigil Encoding Reference Map
- **Type:** chore (documentation / agent reference)
- **Risk:** low
- **Projects:** ⊕Workspace (cross-cutting reference, agent-facing)
- **State:** MERGED → CLOSED
- **Branch:** `chore/FR-20260422-sigil-encoding-map` (worktree: `f:\⊕Workspace-worktrees\FR-20260422-sigil-encoding-map\`)
- **PRs:** [#4](https://github.com/tylerdrakemusic/-Workspace/pull/4) merged @ `03d8a9f` (commit `61ed29d`)
- **Cycle timer:** ff080fb5-4277-4e51-8e09-9eebb133e5af
- **Opened:** 2026-04-22
- **Last updated:** 2026-04-22
- **Closed:** 2026-04-22
- **Final state:** MERGED — sigil-encoding.instructions.md delivered; copilot-instructions.md updated with discoverability pointer.

### Acceptance Criteria
1. A single canonical reference document exists at an agent-discoverable path.
2. Document covers all 5 workspace sigils: ∞, ❤, ⟨ψ⟩, 👁, ⊕.
3. For each sigil, document lists: Unicode codepoint(s), UTF-8 byte sequence, UTF-16 form (incl. surrogate pairs where applicable), common mojibake patterns (cp1252/latin1 misdecodes of UTF-8 bytes), HTML entity, Python/JSON `\u` escape, URL-encoded form, and Windows console `?`-fallback behavior.
4. Document includes a "recovery recipes" section: how agents should detect encoding failure, and how to recover the intended sigil (PYTHONIOENCODING, `chcp 65001`, use of escape sequences in PowerShell, writing files as UTF-8 w/o BOM, git `core.quotepath` tips).
5. Document is referenced from `f:\.github\copilot-instructions.md` under the existing "Agent Sigils" section so agents discover it automatically.
6. Lives in a location attachable as an instruction file (so future agents auto-load relevant portions) OR explicitly linked from the workspace instructions.

### Concurrency Notes
- Conflicts with: none (documentation only; no file overlap with active FR-20260422-band-mgmt-panel).
- Depends on: none.
- **BLOCKED BY:** FR-20260422-multi-root-workspace — target path must live in a git-tracked `.github/` tree. FR-20260422-github-dir-reconcile merged Phase 1 (tracked copy is now current), but Phase 2 (junction swap) was infeasible on exFAT. The multi-root workspace FR supersedes it as the unblocker.

### Tyler's Original Request
> Create a sigil encoding reference map to help future agents handle encoding issues with project sigils. The workspace uses Unicode sigils as project prefixes: ∞ (∞Life), ❤ (❤Music), ⟨ψ⟩ (⟨ψ⟩Quantum), 👁 (👁AI-Manifest), ⊕ (⊕Workspace). Agents have historically suffered encoding issues when these sigils appear in terminal output, file paths, git operations, Python source, JSON, etc. A sigil map document listing each sigil with its common encodings (UTF-8 bytes, UTF-16, surrogate pairs, mojibake patterns, cp1252 fallback, HTML entities, escape sequences, URL-encoded forms, PowerShell quirks, Windows console codepage behavior) so future agents have a reference on how to recognize and get past encoding issues.

---

## Event Log

### 2026-04-22 — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened, triage complete → TRIAGED

**Details:**
- Scope: ⊕Workspace (cross-cutting, agent-facing documentation)
- Acceptance criteria drafted (see Header)
- Concurrency check: clean — no file-path overlap with active FRs
- Proposed artifact location: `f:\.github\instructions\sigil-encoding.instructions.md` (auto-attachable via instructions frontmatter so agents load it when relevant)
- Alternate candidates evaluated: `f:\.github\SIGIL_MAP.md` (static, not auto-attached), `f:\⊕Workspace\docs\sigil-encoding-reference.md` (buried, poor discoverability)

**Next:** awaiting Tyler: approve scope

---

### 2026-04-22 — ⊕workspace-intake

**Event:** state-transition

**Summary:** TRIAGED → BLOCKED. Target path is not in any git repo.

**Details:**
- CI could not cut a branch because `f:\.github\instructions\sigil-encoding.instructions.md` lives in a `.github/` tree that is NOT a git repository (see workspace-level divergence).
- Filed blocker FR **FR-20260422-github-dir-reconcile** to canonicalize `.github/` onto the ⊕Workspace repo.
- This FR stays in BLOCKED state; it will transition back to TRIAGED and be routed to CI as soon as the reconciliation FR reaches MERGED.

**Next:** awaiting FR-20260422-github-dir-reconcile merge; then resume scope confirmation for this FR.

---

### 2026-04-22 — ⊕workspace-overseer

**Event:** blocker updated

**Summary:** Blocker migrated from github-dir-reconcile to multi-root-workspace.

**Details:**
- FR-20260422-github-dir-reconcile merged Phase 1 only (`2b9e612`). Phase 2 junction swap failed — F: drive is exFAT, NTFS junctions unsupported.
- Succeeded by FR-20260422-multi-root-workspace which unblocks this FR via a `.code-workspace` multi-root file (no filesystem reparse points needed).
- This FR remains BLOCKED. Will resume scope confirmation (pragmatic mojibake, no runnable script, instructions path, cover macOS platform independence) once multi-root FR merges.

**Next:** awaiting FR-20260422-multi-root-workspace merge.

---

### 2026-04-22 — ⊕workspace-overseer

**Event:** state-transition

**Summary:** UNBLOCKED → IN_PROGRESS → REVIEW_REQUESTED → MERGED → CLOSED.

**Details:**
- Multi-root FR merged (`91c0772`); `f:\.github\` deleted; tracked `⊕Workspace/.github/` is sole canonical tree. Sigil FR unblocked.
- Worktree created: `f:\⊕Workspace-worktrees\FR-20260422-sigil-encoding-map\`. Branch `chore/FR-20260422-sigil-encoding-map` from `c20ead2`.
- Implemented `.github/instructions/sigil-encoding.instructions.md` (307 lines) with frontmatter `applyTo: "**"` for auto-discovery.
- Sections: quick reference table; mojibake cheatsheet (cp1252/latin1 patterns + reverse-lookup); Windows console (chcp 65001, PYTHONUTF8, PS 5.1 vs 7); macOS/Linux (LANG/LC_ALL, APFS NFC/NFD with `core.precomposeunicode`); git quirks (quotepath, logoutputencoding); Python/JSON/file I/O; recovery decision tree; per-sigil pitfalls (⟨ψ⟩ = 3 codepoints, 👁 = surrogate pair).
- Added discoverability pointer in `copilot-instructions.md` under "Agent Sigils" section.
- Committed `61ed29d`, pushed, PR #4 opened by Tyler, merged @ `03d8a9f`.

**Acceptance criteria check:**
1. ✅ Single canonical reference at agent-discoverable path
2. ✅ All 5 sigils covered
3. ✅ Codepoints, UTF-8/16, mojibake, HTML/Python/JSON escapes per sigil (URL-encoded forms documented in mojibake section)
4. ✅ Recovery recipes (decision tree + Python snippets)
5. ✅ Referenced from `copilot-instructions.md`
6. ✅ Auto-attachable instructions file (frontmatter `applyTo`)

**Next:** none — FR closed.

---

## Artifacts

- **Perf runs:** ff080fb5-4277-4e51-8e09-9eebb133e5af — FR cycle timer (intake → close)
- **PRs:** [#4](https://github.com/tylerdrakemusic/-Workspace/pull/4) merged @ `03d8a9f`
- **Commits:** `61ed29d` (implementation)
