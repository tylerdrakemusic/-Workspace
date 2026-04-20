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
- **∞Life project root:** `f:\executedcode\∞Life\`
- **∞Life database:** `f:\executedcode\∞Life\src\data\infinitelife.db`
- **∞Life DB access:** `from utils.init_db import get_connection`
- **∞Life subject profile:** `f:\executedcode\∞Life\SUBJECT_PROFILE.json`
- **∞Life agent bootstrap:** `f:\executedcode\∞Life\AGENT_STARTUP.md`
- **❤Music project root:** `f:\executedcode\❤Music\`
- **❤Music agent bootstrap:** `f:\executedcode\❤Music\AGENT_STARTUP.md`
- **⟨ψ⟩Quantum project root:** `f:\executedcode\⟨ψ⟩Quantum\`
- **⟨ψ⟩Quantum agent bootstrap:** `f:\executedcode\⟨ψ⟩Quantum\AGENT_STARTUP.md`
- **⟨ψ⟩Quantum project profile:** `f:\executedcode\⟨ψ⟩Quantum\PROJECT_PROFILE.json`
- **👁AI-Manifest project root:** `f:\executedcode\👁AI-Manifest\`
- **👁AI-Manifest agent bootstrap:** `f:\executedcode\👁AI-Manifest\AGENT_STARTUP.md`
- **👁AI-Manifest project profile:** `f:\executedcode\👁AI-Manifest\PROJECT_PROFILE.json`
- **⊕Workspace project root:** `f:\executedcode\⊕Workspace\`
- **⊕Workspace agent bootstrap:** `f:\executedcode\⊕Workspace\AGENT_STARTUP.md`
- **⊕Workspace perf CLI:** `f:\executedcode\⊕Workspace\src\utils\perf_cli.py`
- **⊕Workspace perf DB:** `f:\executedcode\⊕Workspace\src\data\workspace.db` (SQLCipher, env key: `WORKSPACE_DB_KEY`)

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

### Workspace-Level Agents (`⊕`)
- **⊕workspace-overseer** — Top-level coordinator for cross-project tasks. Entry point for "do X to all projects."
- **⊕workspace-doer** — Batch file writer for identical scaffolding across projects. Subagent only.
- **⊕workspace-alignment** — Audits cross-project consistency after changes. Subagent only.
- **⊕workspace-ci** — Git operations, auto-commit, test-before-commit workflows.
- **⊕workspace-security** — Agent file integrity checks, OWASP Top 10 vulnerability scans, secret exposure scanning, prompt injection detection. Run before any multi-project write workflow.
- **⊕workspace-bench-analyzer** — Benchmark analysis across quantum and agent perf data. Discrepancy detection, trend analysis, dashboard generation.
- **⊕workspace-dashboards** — Spec-driven dashboard discovery, portal generation, dashboard registration. Manages unified portal across all projects.
- **⊕workspace-proof** — Proof-in-the-pudding protocol. Records, verifies, and audits concrete proof artifacts from agent runs. Ensures agents produce demonstrable evidence of work.

## Working Conventions
- Research notes → `∞Life/research/<domain>/` as markdown
- Data → SQLite DB, NOT loose JSON files
- Experiment protocols → `∞Life/docs/protocols/` AND protocols DB table
- Prefer editing existing files over creating new ones
- Clean up temporary/test files after use
- Tests → `<project>/tests/` using pytest (see `testing-base.instructions.md`)
