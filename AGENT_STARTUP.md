# ⊕Workspace - Agent-Facing Guide

Canonical guide for workspace-wide agents. The workspace owns shared utilities,
governance, routing, and cross-project coordination for the six project roots
that contain `AGENT_STARTUP.md`: `∞Life`, `❤Music`, `⟨ψ⟩Quantum`,
`👁AI-Manifest`, `⊕Workspace`, and `ΣCapital`.

## First Read

1. Read this file and the applicable project `AGENT_STARTUP.md`.
2. Discover project roots and agents from the filesystem. Do not hardcode the
	active project list in workflow logic.
3. Check `src/config/repo_visibility.json` and `REPO_VISIBILITY.md` before any
	git or cross-project operation.
4. Read `MCP_REGISTRY.md`; run `C:\G\python.exe src\utils\mcp_status.py`
	when MCP availability is needed. The status script is the live lookup;
	there is no committed `src/config/mcp_status.json`.
5. Use `src/utils/fr_cli.py` for the governed FR ledger and
	`src/utils/proof_cli.py` for proof artifacts. Use the manifest-todo public
	contract for TODO operations; do not write its database directly.

## Shared Interfaces

- `src/utils/workspace_discovery.py` - project, agent, routing, and alignment discovery.
- `src/utils/init_db.py` - SQLCipher connection for `src/data/workspace.db`.
- `src/utils/agent_perf.py` and `src/utils/perf_cli.py` - governed orchestration timing.
- `src/utils/fr_cli.py` - feature-request state, event, and artifact ledger.
- `src/utils/proof_cli.py` - proof recording and verification.
- `src/utils/complexity_router.py` - QA/reviewer tier selection.
- `src/integrations/gmail/` - governed service-email capability. Read
  `src/config/service_email_capability.json` and
  `src/config/service_email_policy.json`; credentials are supplied only by
  `GMAIL_SERVICE_TOKEN`, and outbound delivery requires explicit operator approval.
- `tests/` - workspace utility tests. Use temporary or in-memory fixtures and
  never modify production databases.

The shared workspace database is `src/data/workspace.db`, encrypted with
`WORKSPACE_DB_KEY`. The FR ledger and manifest-todo registry are separate
governed stores. Agents must use their public CLIs/contracts rather than
assuming either database schema.

## Routing and Handoffs

- New feature requests: `⊕workspace-intake` first, then `⊕workspace-overseer`.
- Identical cross-project scaffolding: `⊕workspace-doer`.
- Project-specific work: the owning project orchestrator.
- QA and review: the tier selected by `complexity_router.py`.
- Branch, commit, push, PR, merge, and conflict work: `⊕workspace-ci`.
- Security and integrity gates: `⊕workspace-security` before cross-project writes.
- Final functional evidence: `⊕workspace-qa`; architecture and review follow
  the FR state machine in `.github/instructions/feature-request-flow.instructions.md`.

Preserve each agent's responsibility and governed handoff. Do not mutate
project repositories, production data, credentials, schemas, or integrations
from a workspace documentation task.

## Repository and Security Rules

`REPO_VISIBILITY.md` and `src/config/repo_visibility.json` are authoritative
for public/private boundaries and push guards. Never expose health data from
`∞Life` or financial data from `ΣCapital` in public repositories. Agent
integrity and prompt-injection checks use the live manifest at
`.github/!!☾⛧security/agent-manifest.json`; the security agent owns that audit.

Use UTF-8 for paths and content. Keep documentation ASCII where practical,
but preserve the workspace sigils in canonical project names and paths.

## Dependency Sync

Sync external skill repositories only with explicit operator approval:

```powershell
Set-Location F:\superpowers
git fetch origin
git merge --ff-only origin/main
f:\⊕Workspace\tools\sync-skills.ps1 -ApproveProtectedSync
```

The scheduled sync omits `-ApproveProtectedSync` and skips protected files.
