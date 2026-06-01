# Workspace Repository Visibility Policy

**Last updated:** 2026-04-23 | **FR:** FR-20260423-repo-privacy-audit  
**Maintainer:** ⊕workspace-overseer

---

## Current Visibility Status

| Repo | GitHub Slug | Visibility | Sensitivity | Rationale |
|------|-------------|------------|-------------|-----------|
| ∞Life | `tylerdrakemusic/Life` | **PRIVATE** | 🔴 Critical | Contains real medical records, bloodwork PDFs (CBC, HbA1c, lipid, Lynch Syndrome genetic test), biological age reports, epigenetic test outputs, personal journal, supplement/Rx stack, body composition data, and health DB (`infinitelife.db`). **Must remain private.** |
| ❤Music | `tylerdrakemusic/Music` | PUBLIC | 🟡 Low-Medium | Contains original compositions, production files, catalog metadata, and performance data. No PII beyond artist name (public persona). Band/collaboration info is intentionally public. **Acceptable as public — enables discoverability and portfolio value.** |
| ⟨ψ⟩Quantum | `tylerdrakemusic/Quantum` | PUBLIC | 🟢 Low | Quantum computing research, algorithm implementations, IBM Quantum experiments. No personal data. Public benefits open-source community and portfolio. **Keep public.** |
| 👁AI-Manifest | `tylerdrakemusic/AI-Manifest` | PUBLIC | 🟡 Low-Medium | AI integration platform, ElevenLabs TTS, executive brief tools. Watch for: API key exposure in output files, TTS audio containing personal content, voice synthesis configs. Audit `output/` before any push. **Keep public with guards.** |
| ⊕Workspace | `tylerdrakemusic/-Workspace` | PUBLIC | 🟡 Medium | Workspace config, agent definitions, CI scripts, FR registry. Contains agent architecture (acceptable), perf/proof DBs (acceptable — no PII). **Keep public — transparency in tooling is fine.** |
| ΣCapital | `tylerdrakemusic/Capital` | **PRIVATE** | 🟠 High | Personal finance + investment tracking. Contains brokerage account numbers, holdings, statements, watchlists/picks, and Schwab employment exposure. Paper-DB simulation only (no live trading). **Must remain private.** |

---

## Sensitivity Definitions

| Level | Meaning |
|-------|---------|
| 🔴 Critical | Contains personal health, genetic, or medical data. Must be private. |
| 🟠 High | Contains financial, location, or relationship data. Should be private. |
| 🟡 Medium | Contains personal preferences, system architecture, indirect PII. Review before push. |
| 🟢 Low | Research, code, portfolio content with no personal data. Safe to be public. |

---

## Mandatory Pre-Push Rules (All Repos)

### PRIVATE repos (∞Life, ΣCapital)
- NEVER push real health data files without verifying they're in `.gitignore`
- NEVER push `*.db` files (health DB / financial DB)
- NEVER push `data/bloodwork/`, `data/medical_records/`, `data/genomics/` (∞Life)
- NEVER push `data/holdings/`, `data/statements/`, `data/picks/` or files containing account numbers (ΣCapital)
- ΣCapital: never reference Schwab employer-restricted symbols in committed code
- Both: local `.git/hooks/pre-push` blocks direct pushes to `main` (free-tier private repos lack server-side branch protection)
- History purge required for `infinitelife.db` in commit `cea7510` (see remediation section)

### PUBLIC repos (❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest, ⊕Workspace)
- NEVER push API keys, tokens, or credentials — even encrypted vaults
- NEVER push `*.env`, `.env`, `secrets.*`, `*.key`, `*.pem`
- NEVER push output files from 👁AI-Manifest that contain personal voice/audio content without review
- NEVER push files that reference ∞Life data paths or import from `infinitelife.db`
- Always run `⊕workspace-security` scan before pushing new file types

---

## History Remediation Required (∞Life)

> **Status: PENDING** — must be completed even though repo is now private.

The following items were committed to git history while the repo was public:

| Item | Commit | Action Required |
|------|--------|----------------|
| `src/data/infinitelife.db` | `cea7510` | Purge via `git filter-repo --path src/data/infinitelife.db --invert-paths` + force push |
| Bloodwork PDFs (8 files) | multiple | Purge from history if committed; confirm with `git log --all --full-history -- data/bloodwork/` |
| Medical record PDFs | multiple | Same as above |

**Commands to run (Tyler must approve before execution — rewrites history):**
```powershell
# Install if needed: pip install git-filter-repo
# Run from ∞Life root
git filter-repo --path "src/data/infinitelife.db" --invert-paths
git filter-repo --path "data/bloodwork/" --invert-paths
git filter-repo --path "data/medical_records/" --invert-paths
git push --force origin main
```

---

## Agent Visibility Awareness

All agents must check this file's visibility table before any git operation.
The canonical visibility config is also in `f:\⊕Workspace\src\config\repo_visibility.json`
(machine-readable version for agent imports).

**Key rule for agents:**
- If operating on a PUBLIC repo: apply public-safety guards (no secrets, no cross-repo health data refs)
- If operating on ∞Life (PRIVATE): apply full health-data gitignore audit before any commit

---

## Branch Protection Status

**Last verified:** 2026-04-25 | **FR:** FR-20260425-ci-test-harness-gateway

| Repo | Visibility | Server-side protection | Local hook | Notes |
|------|------------|------------------------|------------|-------|
| ⊕Workspace | PUBLIC | ✅ Classic, strict, no admin bypass | — | `test` status check required + up-to-date |
| ❤Music | PUBLIC | ✅ Classic, strict, no admin bypass | — | `test` status check required + up-to-date |
| ⟨ψ⟩Quantum | PUBLIC | ✅ Classic, strict, no admin bypass | — | `test` status check required + up-to-date |
| 👁AI-Manifest | PUBLIC | ✅ Classic, strict, no admin bypass | — | `test` status check required + up-to-date |
| ∞Life | PRIVATE | ❌ Not available — GitHub free tier does not support branch protection on private repos | ✅ `pre-push` hook blocks direct pushes to `main` | Mitigated via local hook + ⊕workspace-ci agent discipline. See `f:\∞Life\docs\PROTECTION_HOOK.md`. |

**Gap (∞Life):** server-side enforcement is not available on free-tier
private repos. The local `pre-push` hook is bypassable with `--no-verify`,
so it is not equivalent to server-side protection. If this gap proves
problematic in practice, file a separate FR to evaluate GitHub Pro upgrade
(which adds branch protection for private repos).
