---
name: discover
description: "Use when asked to discover epic- or story-level TODO opportunities across workspace projects; route execution to the workspace discovery agent."
---

# Discover TODO Opportunities

Confirm you are acting as `⊕workspace-overseer`. If not, hand off to that agent.
Run the `⊕workspace-discovery` agent to find epic/story-level opportunities
across projects and optionally insert approved items into the shared todo DB.

## Arguments

- `scope`: `all` (default) or one of `music`, `life`, `quantum`, `ai_manifest`, `workspace`, `capital`
- `limit`: max items to propose (default: `20`)
- `apply`: `false` (default) for dry-run preview, `true` for approval-gated DB insert

## Behavior

- There are MCP servers likely running; use them for MCP-related detection and
  avoid redundant shell/script build probes.
- The agent reads project context itself (`AGENT_STARTUP.md`, README, docs,
  active FRs, and existing open todos) and synthesizes opportunities
  directly, in-session. It does not use a local LLM pipeline or external API
  calls.
- The agent assigns each candidate's priority (1-10), calibrated against
  existing open todos for the same project; no separate scoring call is needed.
- The agent flags near-duplicate existing todos.
- Show the numbered candidate table for approval, including a `Rationale`
  column truncated to 80 characters.
- When `apply` is used, insert approved items with full context fields:
  - `rationale`: why this todo was surfaced and why it matters now
  - `implementation_hints`: suggested first steps, relevant files, and APIs
  - `context_snapshot`: key project facts that led to the suggestion
  - `estimated_effort`: T-shirt size: `XS`, `S`, `M`, `L`, or `XL`
  - `dependencies`: comma-separated todo IDs or FR IDs
- Under the hood, the agent writes generated candidates to a temporary JSON
  file and hands it to `tools/discover_todos.py --candidates-file <path>`,
  which handles deduplication against open todos and DB insertion. Do not
  invoke that script directly.

## Example Invocations

- "Discover opportunities across all projects"
- "Discover for quantum only, limit 8"
- "Discover and apply for workspace, but prompt me for IDs"