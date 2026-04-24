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

### PRIVATE repos (∞Life)
- NEVER push real health data files without verifying they're in `.gitignore`
- NEVER push `*.db` files (health DB)
- NEVER push `data/bloodwork/`, `data/medical_records/`, `data/genomics/`
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
