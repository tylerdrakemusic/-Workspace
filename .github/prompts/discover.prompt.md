# Discover TODO Opportunities

Run the `⊕workspace-discovery` agent to find epic/story-level opportunities across projects and optionally insert approved items into the shared todo DB.

## Arguments

- `scope`: `all` (default) or one of `music`, `life`, `quantum`, `ai_manifest`, `workspace`
- `limit`: max items to propose (default: `20`)
- `apply`: `false` (default) for dry-run preview, `true` for approval-gated DB insert
- `--model <name>`: override the Ollama model used for discovery (default: auto-detect best available). Auto-detection prefers `llama3.3:70b`; falls back to any 70b, then any 13b, then `llama3.1:8b`.

## Behavior

- There are MCP servers likely running; use them for MCP-related detection and avoid redundant shell/script build probes.
- At startup, auto-detects the best available local Ollama model via `ollama list`
- Scans project context and synthesizes opportunities
- Scores priorities with the existing 1-10 priority system
- Flags near-duplicate existing todos
- Shows numbered candidate table for approval including a `Rationale` column (truncated to 80 chars) so you can evaluate candidates before approving
- When `--apply` is used: approved items are inserted with full context fields persisted to the DB:
  - `rationale` — why this todo was surfaced and why it matters now
  - `implementation_hints` — suggested first steps, relevant files, APIs
  - `context_snapshot` — key project facts that led to the suggestion
  - `estimated_effort` — T-shirt size: `XS`, `S`, `M`, `L`, `XL`
  - `dependencies` — comma-separated todo IDs or FR IDs

## Example Invocations

- "Discover opportunities across all projects"
- "Discover for quantum only, limit 8"
- "Discover and apply for workspace, but prompt me for IDs"
- `C:\G\python.exe tools/discover_todos.py --model llama3.3:70b --apply --project workspace`
- `C:\G\python.exe tools/discover_todos.py --model llama3.1:8b --limit 10`
