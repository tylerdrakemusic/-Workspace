# ⊕Workspace — Shared Cross-Project Utilities

Workspace-level tools shared by all sigil projects (∞Life, ❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest).

## Contents

- `src/utils/init_db.py` — SQLCipher-encrypted DB connection (`workspace.db`)
- `src/utils/agent_perf.py` — PerfTracker: encrypted agent orchestration timing
- `src/utils/perf_cli.py` — CLI interface for PerfTracker (called by agents via terminal)
- `src/utils/workspace_discovery.py` — Project/agent discovery, routing, alignment audit
- `src/utils/gen_qee.py` — Quantum Entropy Engine (password/key generation)
- `src/utils/proof_cli.py` — Proof-in-the-Pudding CLI (agent proof artifact recording + verification)
- `src/integrations/gmail/` — Dedicated service-email (Gmail) capability. Import `from integrations.gmail import GmailServiceClient, ServiceEmailPolicy, EmailDraft, describe_capability`; call `describe_capability()` (or read `src/config/service_email_capability.json`) to discover actions, governance, and residual risk. Outbound is operator-gated: `create_draft()` composes a local draft with no delivery, and `send_draft(draft, operator_approved=True)` delivers only on explicit operator approval (default is disabled and refuses with no Gmail API call). Governed by `src/config/service_email_policy.json`. Credentials via `GMAIL_SERVICE_TOKEN` env var only.
- `tests/` — Test suites for workspace-level utilities

## Database

| Field | Value |
|-------|-------|
| **Path** | `src/data/workspace.db` |
| **Engine** | SQLCipher |
| **Env key** | `WORKSPACE_DB_KEY` |
| **Tables** | `perf_runs`, `perf_steps`, `vulnerabilities`, `proof_artifacts` |

## Dependency Sync

Sync external skill repositories to latest main and refresh local copies:

```powershell
cd F:\superpowers
git fetch origin
git merge --ff-only origin/main
Copy-Item "F:\superpowers\skills\test-driven-development\SKILL.md" `
    "f:\⊕Workspace\.github\skills\test-driven-development\SKILL.md" -Force
Write-Host "superpowers synced + TDD skill refreshed"
```
