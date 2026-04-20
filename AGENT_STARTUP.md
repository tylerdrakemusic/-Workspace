# ⊕Workspace — Shared Cross-Project Utilities

Workspace-level tools shared by all sigil projects (∞Life, ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest).

## Contents

- `src/utils/init_db.py` — SQLCipher-encrypted DB connection (`workspace.db`)
- `src/utils/agent_perf.py` — PerfTracker: encrypted agent orchestration timing
- `src/utils/perf_cli.py` — CLI interface for PerfTracker (called by agents via terminal)
- `src/utils/workspace_discovery.py` — Project/agent discovery, routing, alignment audit
- `src/utils/gen_qee.py` — Quantum Entropy Engine (password/key generation)
- `src/utils/proof_cli.py` — Proof-in-the-Pudding CLI (agent proof artifact recording + verification)
- `tests/` — Test suites for workspace-level utilities

## Database

| Field | Value |
|-------|-------|
| **Path** | `src/data/workspace.db` |
| **Engine** | SQLCipher |
| **Env key** | `WORKSPACE_DB_KEY` |
| **Tables** | `perf_runs`, `perf_steps`, `vulnerabilities`, `proof_artifacts` |
