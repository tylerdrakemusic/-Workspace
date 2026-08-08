---
agent: ⊕workspace-overseer
---
# Discover TODO Opportunities

Run the `⊕workspace-discovery` agent to find epic/story-level opportunities across projects and optionally insert approved items into the shared todo DB.

## Arguments

- `scope`: `all` (default) or one of `music`, `life`, `quantum`, `ai_manifest`, `workspace`, `capital`
- `limit`: max items to propose (default: `20`)
- `apply`: `false` (default) for dry-run preview, `true` for approval-gated DB insert

## Behavior

- There are MCP servers likely running; use them for MCP-related detection and avoid redundant shell/script build probes.
- The agent reads project context itself (AGENT_STARTUP.md, README, docs, active FRs,
  existing open todos) and synthesizes opportunities directly, in-session — no local
  LLM pipeline, no external API calls.
- The agent also assigns each candidate's priority (1-10) itself, calibrated against
  existing open todos for the same project — no separate scoring call.
- Flags near-duplicate existing todos
- Shows numbered candidate table for approval including a `Rationale` column (truncated to 80 chars) so you can evaluate candidates before approving
- When `apply` is used: approved items are inserted with full context fields persisted to the DB:
  - `rationale` — why this todo was surfaced and why it matters now
  - `implementation_hints` — suggested first steps, relevant files, APIs
  - `context_snapshot` — key project facts that led to the suggestion
  - `estimated_effort` — T-shirt size: `XS`, `S`, `M`, `L`, `XL`
  - `dependencies` — comma-separated todo IDs or FR IDs
- Under the hood, the agent writes its generated candidates to a temp JSON file and
  hands it to `tools/discover_todos.py --candidates-file <path>`, which only handles
  the mechanical parts (dedup against open todos, DB insert). You never need to
  invoke that script yourself.

## Example Invocations

- "Discover opportunities across all projects"
- "Discover for quantum only, limit 8"
- "Discover and apply for workspace, but prompt me for IDs"
