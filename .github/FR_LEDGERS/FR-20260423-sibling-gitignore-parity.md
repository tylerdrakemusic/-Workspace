# FR-20260423-sibling-gitignore-parity — Sibling-project .gitignore parity (∞Life, ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest)

<!-- Created by ⊕workspace-intake. Header is updated in place by intake / CI only.
     Event Log and Artifacts are APPEND-ONLY for all agents. -->

## Header

- **FR ID:** FR-20260423-sibling-gitignore-parity
- **Title:** Sibling-project .gitignore parity sweep
- **Type:** chore
- **Risk:** low
- **Projects:** ∞Life, ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest
- **State:** SOAKING- **Branch:** chore/life/gitignore-parity · chore/music/gitignore-parity · chore/quantum/gitignore-parity · chore/ai-manifest/gitignore-parity
- **PRs:** https://github.com/tylerdrakemusic/Life/pull/1 · https://github.com/tylerdrakemusic/Music/pull/1 · https://github.com/tylerdrakemusic/Quantum/pull/1 · https://github.com/tylerdrakemusic/AI-Manifest/pull/5 (all ready-for-review)
- **Cycle timer:** 6b55a663-313c-45a2-a44f-d0df0da33e48
- **Opened:** 2026-04-23
- **Last updated:** 2026-04-23
- **Merged at:** —
- **Signed off at:** —
- **Closed:** —
- **Final state:** —

### Acceptance Criteria

1. Each of the 4 sibling projects' `.gitignore` covers: `__pycache__/`, `*.pyc`, `src/data/*.db`, `src/data/backups/` (where applicable — skip patterns the project doesn't use).
2. Any currently-tracked `.pyc` or binary DB is `git rm --cached` in each project (file content preserved on disk).
3. Each project gets a `src/data/schema.sql` sanitized dump if it has a SQLCipher DB. (∞Life has one — confirmed. ⟨ψ⟩Quantum / ❤Music / 👁AI-Manifest: implementer inspects and adds where applicable, documents absence otherwise.)
4. `git status --short` clean in each of the 4 projects after landing.
5. Separate branch + draft PR per project (per the one-agent-one-branch-one-PR protocol). Branch naming: `chore/<project-short-name>/gitignore-parity` (e.g. `chore/life/gitignore-parity`, `chore/music/gitignore-parity`, `chore/quantum/gitignore-parity`, `chore/ai-manifest/gitignore-parity`).

### Concurrency Notes

- Conflicts with: **FR-20260423-workspace-gitignore-sweep** (identical hygiene pattern, but ⊕Workspace-only — no file overlap with sibling repos).
- Depends on: none
- Executes as 4 parallel per-repo branches/PRs; each repo's work is independent.

### Deliverable Tracker

| #   | Deliverable                                                        | Owner                  | Status      | Proof | Updated    |
| --- | ------------------------------------------------------------------ | ---------------------- | ----------- | ----- | ---------- |
| AC1 | ∞Life: `.gitignore` + rm --cached + schema.sql + clean status       | ⊕workspace-overseer    | done (no schema.sql — init_db.py source missing on branch) | cea7510 | 2026-04-23 |
| AC2 | ❤Music: `.gitignore` + rm --cached + schema.sql (if DB) + clean     | ⊕workspace-overseer    | done (schema.sql added; no tracked pyc/db to rm)           | 051b7c4 | 2026-04-23 |
| AC3 | ⟨ψ⟩Quantum: `.gitignore` + rm --cached + schema.sql (if DB) + clean | ⊕workspace-overseer    | done                                                        | edb6bc7 | 2026-04-23 |
| AC4 | 👁AI-Manifest: `.gitignore` + rm --cached + schema.sql (if DB) + clean | ⊕workspace-overseer  | done (no schema.sql — no src/data, no init_db.py)           | a96274f | 2026-04-23 |
| AC5 | 4 PRs opened + un-drafted (one per sibling repo)                    | ⊕workspace-ci          | done                                                        | PRs     | 2026-04-23 |

### Tyler's Original Request

> Apply the same .gitignore hygiene sweep to the four sibling project repos so every project is consistently clone-ready on Mac/Linux. Tyler wants the repo close to working out-of-the-box on Mac/Linux even though dev happens on Windows. Parity across all 5 projects.

---

## Event Log

<!-- APPEND-ONLY. Newest entries at the bottom. Never edit past entries. -->

### 2026-04-23T00:00:00Z — ⊕workspace-intake

**Event:** state-transition

**Summary:** FR opened; Tyler pre-approved scope → TRIAGED → SCOPED

**Details:**
- Type: chore, Risk: low
- Projects (4 sibling repos, NOT ⊕Workspace which is covered by FR-20260423-workspace-gitignore-sweep): ∞Life, ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest
- Acceptance criteria recorded (see Header)
- Concurrency check: clean — no file overlap with ⊕Workspace sweep; per-repo branches isolate each sibling
- Cycle timer started: 6b55a663-313c-45a2-a44f-d0df0da33e48
- Tyler pre-approved scope (batch intake) — skipping scope-confirmation gateway

**Next:** ⊕workspace-ci: create 4 per-repo branches (`chore/<short>/gitignore-parity`) + open 4 draft PRs

### 2026-04-23T01:24Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** 4 per-repo branches created + 4 draft PRs opened → BRANCHED

**Details:**
- ∞Life: branch `chore/life/gitignore-parity` @ seed `6f7b4778` → PR https://github.com/tylerdrakemusic/Life/pull/1 (draft)
- ❤Music: branch `chore/music/gitignore-parity` @ seed `34bd8e4d` → PR https://github.com/tylerdrakemusic/Music/pull/1 (draft)
- ⟨ψ⟩Quantum: branch `chore/quantum/gitignore-parity` @ seed `5697646f` → PR https://github.com/tylerdrakemusic/Quantum/pull/1 (draft)
- 👁AI-Manifest: branch `chore/ai-manifest/gitignore-parity` @ seed `534e9ef4` → PR https://github.com/tylerdrakemusic/AI-Manifest/pull/5 (draft)
- Each branch has a single intake breadcrumb file at `.github/FR_INTAKE/FR-20260423-sibling-gitignore-parity.breadcrumb.md`

**Next:** implementation dispatch to ⊕workspace-overseer (fan-out across 4 sibling repos)

### 2026-04-23T02:15Z — ⊕workspace-ci

**Event:** state-transition

**Summary:** Parity sweep implemented across all 4 sibling repos → BRANCHED → IMPLEMENTED → REVIEW_REQUESTED

**Details (per project):**

- **∞Life** — commit `cea7510` on `chore/life/gitignore-parity` (pushed)
  - `.gitignore` extended with FR-D parity block: `*.pyd`, `.playwright-mcp/`, `src/data/*.db`, `src/data/*.db-journal`, `src/data/*.db-wal`, `src/data/*.db-shm`, `src/data/backups/`, `*.tmp` (existing file already covered `__pycache__/`, `*.pyc`, `*.pyo`, `.env`, `.venv/`)
  - `git rm --cached`: 39 `__pycache__/*.pyc`, `src/data/infinitelife.db`, 2 files under `src/data/backups/`
  - **schema.sql SKIPPED** — `src/utils/init_db.py` source not present on this branch (only compiled `.pyc` remains in `src/utils/__pycache__`). Schema dump deferred to a follow-up FR when the source is restored.
  - Breadcrumb removed.
  - PR https://github.com/tylerdrakemusic/Life/pull/1 un-drafted.

- **❤Music** — commit `051b7c4` on `chore/music/gitignore-parity` (pushed)
  - `.gitignore` extended with FR-D parity block: `*.pyo`, `*.pyd`, `.playwright-mcp/`, `src/data/*.db`, `src/data/*.db-journal`, `src/data/*.db-wal`, `src/data/*.db-shm`, `src/data/backups/`, `*.tmp`, `.venv/` (existing file already covered `__pycache__/`, `*.pyc`, `*.db`, `.env`)
  - No previously-tracked `__pycache__` / binary DBs to untrack.
  - **schema.sql ADDED** at `src/data/schema.sql` — extracted from `_SCHEMA_SQL` constant in `src/utils/init_db.py` (albums, tracks, recordings, lyrics, catalog_index, releases, release_signatures, catalog_songs, setlists, setlist_songs, bands, band_song_arrangements + indexes).
  - Breadcrumb removed.
  - PR https://github.com/tylerdrakemusic/Music/pull/1 un-drafted.

- **⟨ψ⟩Quantum** — commit `edb6bc7` on `chore/quantum/gitignore-parity` (pushed)
  - `.gitignore` extended with FR-D parity block: `*.pyd`, `.playwright-mcp/`, `src/data/*.db`, `src/data/*.db-journal`, `src/data/*.db-wal`, `src/data/*.db-shm`, `src/data/backups/`, `*.tmp` (existing file already covered `__pycache__/`, `*.pyc`, `*.pyo`, `*.py[cod]`, `*.db*`, `.env`, `.venv/`)
  - `git rm --cached`: 22 `__pycache__/*.pyc`, `src/data/quantumpsi.db`
  - **schema.sql ADDED** at `src/data/schema.sql` — extracted from `init_db()` executescript in `src/utils/init_db.py` (`benchmarks` table + indexes on `algorithm` and `backend`).
  - Breadcrumb removed.
  - PR https://github.com/tylerdrakemusic/Quantum/pull/1 un-drafted.

- **👁AI-Manifest** — commit `a96274f` on `chore/ai-manifest/gitignore-parity` (pushed)
  - `.gitignore` extended with FR-D parity block: `.playwright-mcp/`, `src/data/*.db-journal`, `src/data/backups/`, `*.tmp` (existing file already covered `__pycache__/`, `*.pyc`, `*.pyo`, `*.pyd`, `src/data/*.db`, `src/data/*.db-shm`, `src/data/*.db-wal`, `.env`, `.venv/`)
  - No previously-tracked `__pycache__` / binary DBs to untrack.
  - **schema.sql SKIPPED** — project has no `src/data/` directory and no `src/utils/init_db.py`; no SQLCipher DB in this repo.
  - Breadcrumb removed.
  - PR https://github.com/tylerdrakemusic/AI-Manifest/pull/5 un-drafted.

- All 4 worktrees used for implementation: `f:\worktrees\fr-d-{life,music,quantum,ai-manifest}\<proj>`. Worktree creation on sigil-named repos succeeded in all 4 cases (no temp-clone fallback required).

**Next:** Tyler review → merge → close cycle timer `6b55a663-313c-45a2-a44f-d0df0da33e48` (or ⊕workspace-ci reconcile-fr-timers after GitHub merge).

---

## Artifacts

<!-- APPEND-ONLY. Links to concrete evidence. -->

- **Perf runs:** 6b55a663-313c-45a2-a44f-d0df0da33e48 — FR cycle timer (intake → merge across 4 PRs)
- **Commits:** 6f7b4778 (Life), 34bd8e4d (Music), 5697646f (Quantum), 534e9ef4 (AI-Manifest) — intake breadcrumb seed commits
- **Implementation commits:** cea7510 (Life), 051b7c4 (Music), edb6bc7 (Quantum), a96274f (AI-Manifest)
- **PRs:** Life#1 · Music#1 · Quantum#1 · AI-Manifest#5 (all ready-for-review)
