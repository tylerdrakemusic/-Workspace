# Workspace Instructions

## Project Context
This workspace contains Tyler James Drake's personal software projects with five projects:
- **∞Life/** — Longevity optimization system (primary)
- **❤Music/** — Music production, catalog management, and performance tracking
- **⟨ψ⟩Quantum/** — Quantum computing toolkit (IBM Quantum, algorithms, quantum RNG)
- **👁AI-Manifest/** — AI integration platform (ElevenLabs voice synthesis, AI services)
- **⊕Workspace/** — Shared workspace utilities (perf tracking, discovery, alignment)

## Code Standards
- Python 3.11+ with type hints on all function signatures
- Docstrings on public functions only
- SQLite as the data layer — all health data goes through `∞Life/src/data/infinitelife.db`
- Shared utilities in each project's `src/utils/`, import from there
- Python executable: `C:\G\python.exe`

## Key Paths
| Project | Root | Notes |
|---------|------|-------|
| ∞Life | `f:\∞Life\` | DB: `src/data/infinitelife.db`; access: `from utils.init_db import get_connection`; profile: `SUBJECT_PROFILE.json` |
| ❤Music | `f:\❤Music\` | — |
| ⟨ψ⟩Quantum | `f:\⟨ψ⟩Quantum\` | Profile: `PROJECT_PROFILE.json` |
| 👁AI-Manifest | `f:\👁AI-Manifest\` | Profile: `PROJECT_PROFILE.json` |
| ⊕Workspace | `f:\⊕Workspace\` | Perf CLI: `src/utils/perf_cli.py`; DB: `src/data/workspace.db` (key: `WORKSPACE_DB_KEY`) |

All projects: bootstrap at `<root>/AGENT_STARTUP.md`.

## Budget Discipline
All purchases and expenditures for ∞Life must be logged in the budget ledger (`∞Life/src/data/infinitelife.db` budget table) before proceeding. Monthly target: $100-500. Always present cost-benefit analysis before recommending purchases.

## Agent Sigils
Each scope has a Unicode sigil prefix for visual identification and agent discovery:

| Sigil | Scope | Agent Glob |
|-------|-------|------------|
| **∞** | ∞Life project | `∞life-*.agent.md` |
| **❤** | ❤Music project | `❤music-*.agent.md` |
| **⟨ψ⟩** | ⟨ψ⟩Quantum project | `⟨ψ⟩quantum-*.agent.md` |
| **👁** | 👁AI-Manifest project | `👁ai-manifest-*.agent.md` |
| **⊕** | Workspace-wide (cross-project) | `⊕workspace-*.agent.md` |

**Encoding reference:** see `.github/instructions/sigil-encoding.instructions.md`
for UTF-8/16 byte sequences, mojibake recovery, Windows/macOS/Linux console
setup, and per-sigil pitfalls. Auto-attached by VS Code when relevant.

### Workspace-Level Agents (`⊕`)
- **⊕workspace-overseer** — Top-level coordinator for cross-project tasks. Entry point for "do X to all projects."
- **⊕workspace-intake** — Feature request intake + triage. First stop for any new feature/fix/chore Tyler files. Owns the FR registry and Tyler's scope gateway.
- **⊕workspace-reviewer** — Automated PR review (alignment + security + tests + proof). Produces the structured review Tyler reads before approving merge.
- **⊕workspace-doer** — Batch file writer for identical scaffolding across projects. Subagent only.
- **⊕workspace-discovery** — Epic/story TODO opportunity scanner. Mines project context, proposes approval-gated candidates, and writes approved SCAN-labeled items into the shared todo DB.
- **⊕workspace-ci** — Git operations, auto-commit, test-before-commit workflows, branch/worktree/PR lifecycle, merges.
- **⊕workspace-security** — Agent file integrity checks, OWASP Top 10 vulnerability scans, secret exposure scanning, prompt injection detection. Run before any multi-project write workflow.
- **⊕workspace-bench-analyzer** — Benchmark analysis across quantum and agent perf data. Discrepancy detection, trend analysis, dashboard generation.
- **⊕workspace-dashboards** — Spec-driven dashboard discovery, portal generation, dashboard registration. Manages unified portal across all projects.
- **⊕workspace-hygiene** — Unified workspace hygiene agent. Cleans all 5 projects, audits and self-repairs agent files, enforces self-regeneration protocol. Replaces all per-project hygiene agents. Run weekly.
- **⊕workspace-gen-qee** — Quantum Entropy Engine. Generates cryptographically strong passwords and DB keys using quantum-assisted randomness. Output is console-only, never stored.
- **⊕workspace-qa** — Functional QA gate. Runs after implementation (FUNCTIONAL_QA state), derives a test plan from FR acceptance criteria, executes functional tests (DB queries, CLI runs, Playwright for UI changes), records proof artifacts. Hard-blocking: FAIL prevents architecture review.
- **⊕workspace-protector** — Reality check audit. Scans all projects for file explosion, complexity drift, scope creep, dead code, and IDE errors. Produces truth report for course-correction.

## Repository Visibility (AGENT-CRITICAL)

Machine-readable config: `f:\⊕Workspace\src\config\repo_visibility.json`
Human-readable policy: `f:\⊕Workspace\REPO_VISIBILITY.md`

| Repo | Visibility | Sensitivity |
|------|------------|-------------|
| ∞Life (`tylerdrakemusic/Life`) | **🔒 PRIVATE** | 🔴 Critical — real medical/genomic data |
| ❤Music (`tylerdrakemusic/Music`) | 🌐 Public | 🟡 Low-Medium |
| ⟨ψ⟩Quantum (`tylerdrakemusic/Quantum`) | 🌐 Public | 🟢 Low |
| 👁AI-Manifest (`tylerdrakemusic/AI-Manifest`) | 🌐 Public | 🟡 Low-Medium |
| ⊕Workspace (`tylerdrakemusic/-Workspace`) | 🌐 Public | 🟡 Medium |

**Agent rules for git/push operations:**
- ∞Life (PRIVATE): always run health-data gitignore audit before any commit. Block: `*.db`, `data/bloodwork/`, `data/medical_records/`, `data/genomics/`, `logs/`, `tmp/`, `SUBJECT_PROFILE.json`
- PUBLIC repos: block secrets/credentials in ALL files. For 👁AI-Manifest: audit `output/` before push. Never reference ∞Life health paths in public repos.
- Before any cross-project push: check `repo_visibility.json` for the target repo's push guards.

## Working Conventions
- Research notes → `∞Life/research/<domain>/` as markdown
- Data → SQLite DB, NOT loose JSON files
- Experiment protocols → `∞Life/docs/protocols/` AND protocols DB table
- Prefer editing existing files over creating new ones
- Clean up temporary/test files after use
- Tests → `<project>/tests/` using pytest (see `testing-base.instructions.md`)
- **Portal left nav is high-level only** — do NOT add every new feature page as a portal sidebar entry. Embed feature sub-pages as tab-nav pills or routes inside their owning dashboard. Only top-level standalone dashboards belong in the sidebar. Ask Tyler before adding anything new to the portal left nav.

<skills>
<skill>
<name>test-driven-development</name>
<description>Use when implementing any feature, bugfix, or behavior change. Enforces Red-Green-Refactor: write a failing test first, verify it fails for the right reason, write minimal code to pass, then refactor. MANDATORY before writing any production code. Exceptions (ask Tyler): throwaway prototypes, generated code, configuration files.</description>
<file>f:\⊕Workspace\.github\skills\test-driven-development\SKILL.md</file>
</skill>
</skills>
