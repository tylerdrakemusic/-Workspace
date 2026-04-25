---
description: "Agent visibility awareness — public vs private repo rules. Auto-applied to all agent and CI workflows before any git/push operation. Covers push guards, pre-commit checks, and cross-repo data safety rules."
applyTo: ".github/agents/**"
---

# Repo Visibility Awareness

All agents operating on git repositories MUST check the visibility policy before
any commit, push, or PR operation.

## Canonical Config

- **Machine-readable:** `f:\⊕Workspace\src\config\repo_visibility.json`
- **Human-readable policy:** `f:\⊕Workspace\REPO_VISIBILITY.md`

## Quick Reference

| Repo slug | Project | Visibility | Sensitive? |
|-----------|---------|------------|------------|
| `tylerdrakemusic/Life` | ∞Life | **PRIVATE** | YES — health/medical/genomic |
| `tylerdrakemusic/Music` | ❤Music | public | low-medium |
| `tylerdrakemusic/Quantum` | ⟨ψ⟩Quantum | public | low |
| `tylerdrakemusic/AI-Manifest` | 👁AI-Manifest | public | low-medium |
| `tylerdrakemusic/-Workspace` | ⊕Workspace | public | medium |

## PRIVATE Repo Rules (∞Life)

Before ANY commit to `∞Life`:

1. Verify these paths are in `.gitignore` and not being staged:
   - `src/data/infinitelife.db` (and all `*.db`)
   - `data/bloodwork/`
   - `data/medical_records/`
   - `data/genomics/`
   - `data/baseline/`
   - `logs/`
   - `tmp/`
   - `reports/`
   - `SUBJECT_PROFILE.json`

2. Run: `git -C "f:\∞Life" status --porcelain` and inspect for any health data files

3. If any health data file is staged: **HALT and alert Tyler** — do NOT proceed with commit

4. History remediation is PENDING: `infinitelife.db` exists in commit `cea7510` — Tyler must approve history purge before repo is clean

## PUBLIC Repo Rules (All Others)

Before ANY commit or push to a public repo:

1. **Credentials scan:** no API keys, tokens, passwords in staged files
   - Block: `*.env`, `.env`, `secrets.*`, `*.key`, `*.pem`, `*.pfx`
   - Block: hardcoded patterns matching `sk-`, `github_pat_`, `ghp_`, `xoxb-`, `AKIA`
   
2. **Cross-project data guard:** no files that contain or reference:
   - `infinitelife.db` paths
   - ∞Life health data (biomarker values, bloodwork, genomics)
   - Tyler's personal medical information

3. **👁AI-Manifest specific:** audit `output/tts/` and `output/briefs/` before push —
   ensure no personal audio or brief content is included

4. **⊕Workspace specific:** do not push `src/data/workspace.db`

## Agent Behavior When Visibility Is Unknown

If an agent cannot determine repo visibility from `repo_visibility.json`:

1. Treat the repo as **public** (apply the stricter public-repo guards)
2. Log a warning: "Repo visibility unknown for [repo] — applying public-safety guards"
3. Do NOT proceed with sensitive data commits until visibility is confirmed

## Updating This Policy

When Tyler makes a repo private or public:
1. Update `f:\⊕Workspace\src\config\repo_visibility.json`
2. Update `f:\⊕Workspace\REPO_VISIBILITY.md`
3. Update the table in `f:\⊕Workspace\.github\copilot-instructions.md`
4. Commit all three files together with message: `chore: update repo visibility policy`

## Branch Protection (FR-20260425, live)

Canonical detail in `f:\⊕Workspace\REPO_VISIBILITY.md` ("Branch Protection
Status" section). Summary for agents:

| Repo | Server-side protection | Local guard |
|------|------------------------|-------------|
| ⊕Workspace, ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest | ✅ Classic strict, `test` check required + up-to-date, **no admin bypass** | — |
| ∞Life | ❌ Not available (free-tier private) | ✅ `.git/hooks/pre-push` blocks direct pushes to `main` |

**Agent rules:**
- Direct pushes / merges to `main` are forbidden in all 5 repos. Always use
  feature branch → PR → green `test` check → merge.
- For the 4 public repos: GitHub will reject merges with red CI (HTTP 405);
  agents MUST wait for green `test` before attempting merge via API.
- For ∞Life: the pre-push hook lives on Tyler's local clone only. Agents
  pushing from that clone will be blocked from `main` and must use a feature
  branch + PR. Never use `--no-verify` to bypass the hook without Tyler's
  explicit per-task approval.

