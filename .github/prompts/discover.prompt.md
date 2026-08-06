---
mode: ⊕workspace-overseer
---
# Discover TODO Opportunities

Run the `⊕workspace-discovery` agent to find epic/story-level opportunities across projects and optionally insert approved items into the shared todo DB.

## Arguments

- `scope`: `all` (default) or one of `music`, `life`, `quantum`, `ai_manifest`, `workspace`, `capital`
- `limit`: max items to propose (default: `20`)
- `apply`: `false` (default) for dry-run preview, `true` for approval-gated DB insert
- `--manual`: perform discovery directly (agent reasoning over project context) instead of running `tools/discover_todos.py`. Use for scopes not wired into that script (e.g. `capital`) or whenever a local LLM pipeline should be skipped.

## Behavior

- There are MCP servers likely running; use them for MCP-related detection and avoid redundant shell/script build probes.
- Scans project context (AGENT_STARTUP.md, README, docs, active FRs, existing open todos) and synthesizes opportunities directly — no local LLM dependency
- Scores priorities with the existing 1-10 priority system
- Flags near-duplicate existing todos
- Shows numbered candidate table for approval including a `Rationale` column (truncated to 80 chars) so you can evaluate candidates before approving
- When `apply` is used: approved items are inserted with full context fields persisted to the DB:
  - `rationale` — why this todo was surfaced and why it matters now
  - `implementation_hints` — suggested first steps, relevant files, APIs
  - `context_snapshot` — key project facts that led to the suggestion
  - `estimated_effort` — T-shirt size: `XS`, `S`, `M`, `L`, `XL`
  - `dependencies` — comma-separated todo IDs or FR IDs

## Example Invocations

- "Discover opportunities across all projects"
- "Discover for quantum only, limit 8"
- "Discover and apply for workspace, but prompt me for IDs"
- `C:\G\python.exe tools/discover_todos.py --apply --project workspace`
- `C:\G\python.exe tools/discover_todos.py --limit 10`
