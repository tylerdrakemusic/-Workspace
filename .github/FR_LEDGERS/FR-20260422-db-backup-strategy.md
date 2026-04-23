# FR-20260422-db-backup-strategy — DB backup strategy across all projects

## Header

- **FR ID:** FR-20260422-db-backup-strategy
- **Title:** Design and implement DB backup strategy for all project SQLite databases
- **Type:** chore
- **Risk:** medium (touches data layer; no schema changes, only backup tooling)
- **Projects:** ❤Music, ∞Life, ⟨ψ⟩Quantum, 👁AI-Manifest, ⊕Workspace
- **State:** CLOSED
- **Branch:** N/A
- **PRs:** N/A
- **Cycle timer:** 69cf6ed4-7f95-4c4f-9016-45a9e2ad39bf
- **Opened:** 2026-04-22
- **Last updated:** 2026-04-22
- **Closed:** 2026-04-22
- **Final state:** REJECTED (deferred — revisit when DB growth becomes a pain point)

### Acceptance Criteria
1. Backup strategy documented per project (which DBs, frequency, retention)
2. At minimum: automated local backup script that copies `.db` files to a dated `_backups/` folder before each schema migration or on a schedule
3. `heartmusic.db`, `infinitelife.db`, `quantumpsi.db`, `workspace.db` (SQLCipher) all covered
4. Backup filenames include timestamp + schema version where known
5. Backups excluded from git via `.gitignore` (already handled for ❤Music; check others)
6. Optional: offsite copy strategy noted (e.g. Backblaze B2 or scheduled robocopy to external drive) — decision deferred but documented

### Concurrency Notes
- Conflicts with: none
- Depends on: FR-20260422-gitignore-sweep (other project .gitignores should exclude *.db before this rolls out)

### Tyler's Original Request
> "yes" (to filing follow-ups from FR-20260422-music-repo-purge: "heartmusic.db is no longer versioned in git; needs a separate backup approach")

### Context
Surfaced when `.gitignore` was added during FR-20260422-music-repo-purge. The ❤Music DB (`heartmusic.db`, `src/data/backups/heartmusic_plaintext_20260418_075304.db`) was previously tracked in git — that's now gone. The ∞Life, ⟨ψ⟩Quantum, and ⊕Workspace DBs may have the same gap. All project DBs are SQLCipher encrypted (except during plaintext backup windows) and grow over time — git is the wrong tool for them.

---

## Event Log

### 2026-04-22T23:59:00 — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened and triaged → TRIAGED; awaiting Tyler scope approval

**Details:**
- Scope: all 5 projects (any project with a `.db` file)
- Risk: medium — adds tooling, no destructive ops
- Cycle timer started: 69cf6ed4-7f95-4c4f-9016-45a9e2ad39bf
- Dependency noted: gitignore sweep should land first in other projects

**Next:** awaiting Tyler: approve scope

---

### 2026-04-23T00:06:00 — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR rejected by Tyler → CLOSED (deferred)

**Details:**
- Tyler: "reject, let's defer backup until later"
- No implementation started, no branches cut
- Cycle timer closed as rejected
- Revisit when DB growth / data loss risk becomes pressing

**Next:** archived

---

## Artifacts

- **Perf runs:**
  - 69cf6ed4-7f95-4c4f-9016-45a9e2ad39bf — full FR cycle timer
- **Proof artifacts:** (pending)
- **PRs:** (pending)
- **Parent FR:** FR-20260422-music-repo-purge (surfaced this gap)
