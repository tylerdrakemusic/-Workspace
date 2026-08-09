# Gold-Standard MCP Registry

Last updated: 2026-05-12  
FR: FR-20260512-workspace-mcp-registry

## Purpose

This registry identifies high-value MCP servers for the workspace and ranks them with a repeatable scoring model.

Scope of this FR:
- Research and recommendation only
- No runtime installation changes
- No mcp.json mutation

## Current Installed Baseline

Already active in this workspace:
- GitHub MCP
- SQLite MCP
- Playwright MCP

This registry is now framed as optimization and standardization on top of that baseline.

## Governed Coordination Servers

The FR-20260809 coordination surface is intentionally separate from the
generic SQLCipher server:

Coordination invocation policy is deterministic MCP-first invocation: use the
coordination MCP when it is available, and call only the fixed allowlisted
operations documented below. If the coordination MCP is unavailable, use the
explicit local fallback path (the canonical `fr_cli.py` or Manifest todo
utility) and report that the coordination MCP is unavailable; do not silently
substitute an arbitrary database or SQL call.

- `workspace-coordination` → `src/utils/coordination_mcp_server.py`
- `get_fr`
- `record_fr_event`
- `record_fr_artifact`
- Delegates FR writes to `fr_cli.py`, which remains the canonical state
	mutation path.
- `manifest-coordination` →
	`👁AI-Manifest/src/integrations/coordination/mcp_server.py`
- `list_open_todos`
- `link_confirmed_todo_to_fr`
- Requires explicit confirmation before setting `todos.fr_id`.

These tools do not accept database names or SQL. They must not be implemented
by expanding the five-database `sqlcipher_mcp_server.py` contract, and they do
not add access for ∞Life, ❤Music, ⟨ψ⟩Quantum, or ΣCapital.

The user-level VS Code `mcp.json` is outside the approved isolated worktrees;
registration there is a deployment step and is not changed by this FR.

## Weighted Scoring Rubric

Each candidate is scored 0-10 per criterion, then multiplied by the weight.

| Criterion | Weight | What "10" Means |
|---|---:|---|
| Security posture | 30 | Strong auth model, least-privilege behavior, clear data boundaries |
| Workspace fit | 25 | Directly accelerates daily workflows across active projects |
| Reliability and maintenance | 20 | Maintained, stable behavior, clear ownership/docs |
| Performance and latency | 15 | Fast enough for iterative agent workflows |
| Setup and operability | 10 | Easy to configure, low operational overhead |

Final score formula:

`final_score = sum((criterion_score / 10) * weight)`

Maximum final score is 100.

## Candidate Registry (8)

| Rank | MCP Server | Category | Final Score | Rationale | Suggested Rollout |
|---:|---|---|---:|---|---|
| 1 | SQLite MCP | Data | 90 | Direct DB read/query loop for workspace analytics and rapid troubleshooting. High leverage across all projects. | Adopt now (read-only first) |
| 2 | Filesystem MCP | Core tooling | 88 | High-utility file operations with predictable behavior; reduces shell glue for path-heavy workflows. | Adopt now (strict path sandbox) |
| 3 | Fetch/HTTP MCP | Research | 84 | Reliable source retrieval for research and validation workflows with lower overhead than browser automation. | Adopt now |
| 4 | GitHub MCP | SCM | 82 | Strong lifecycle support for issues/PRs/reviews. Already in use and valuable for CI-style workflows. | Keep and standardize usage |
| 5 | Playwright MCP | Browser automation | 76 | Excellent for web automation and UI checks, but heavier and slower than fetch-first workflows. | Keep for targeted flows |
| 6 | Memory MCP | Knowledge layer | 70 | Useful for long-running context retention, but needs strict guardrails and lifecycle policy. | Later (policy first) |
| 7 | Container tools MCP | Infra | 66 | Useful when container-heavy work increases; currently moderate fit to daily workspace paths. | Later |
| 8 | Sequential Thinking MCP | Reasoning support | 52 | Helpful in niche deep-reasoning tasks, but less consistent ROI versus direct tooling servers. | Avoid by default; opt-in only |

## Top-3 Recommendations

1. SQLite MCP - Keep and standardize now
- Rollout mode: enforce read-only-by-default profile and explicit write policy
- Reason: already installed and highest cross-project acceleration for data workflows
- Policy artifact: `src/config/mcp_sqlite_policy.json`

2. Playwright MCP - Keep and standardize now
- Rollout mode: targeted automation profile (UI verification, screenshots, browser-only tasks)
- Reason: already installed and high value when used for the right workload class

3. GitHub MCP - Keep and standardize now
- Rollout mode: use for PR/issue/review automation with visibility guardrails
- Reason: already installed and core to branch/PR lifecycle orchestration

## Guardrails by Repo Visibility

Visibility policy source: REPO_VISIBILITY.md

### Private repo guardrails (∞Life)
- Default to read-only operations for data tools.
- Never expose medical/genomic records via public-facing outputs.
- Block any MCP workflow that attempts to write sensitive data outside approved DB paths.
- Require explicit user confirmation for any write-capable MCP action touching private-health scope.

### Public repo guardrails (❤Music, ⟨ψ⟩Quantum, 👁AI-Manifest, ⊕Workspace)
- Enforce secret scanning on generated content before push.
- Prohibit references/imports that leak ∞Life private data paths.
- Prefer read-only queries and explicit allowlists for write operations.
- Keep output/ artifacts reviewed before publication where personal content may appear.

## Adoption Plan (Short)

Phase 1:
- Baseline lock: document GitHub/SQLite/Playwright as standard installed set
- Standardize SQLite MCP in read-only mode
- Standardize Playwright usage profile and limits
- Ship SQLite MCP hardening profile at `src/config/mcp_sqlite_policy.json`

Phase 2:
- Add Filesystem MCP with strict path sandbox rules
- Add Fetch MCP for research-first retrieval

Phase 3:
- Evaluate Memory MCP policy and pilot with bounded scope
- Re-score registry quarterly or after major workflow changes

## Change Log

- 2026-05-12: Initial registry created with weighted scoring, top-3 decisions, and visibility guardrails.
- 2026-05-12: Corrected baseline to reflect already-installed GitHub/SQLite/Playwright MCP servers and shifted recommendations to keep-and-standardize.
- 2026-05-12: Added SQLite MCP hardening policy artifact (`src/config/mcp_sqlite_policy.json`) with read-only default and explicit write gate.
