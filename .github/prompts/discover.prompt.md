# Discover TODO Opportunities

Run the `⊕workspace-discovery` agent to find epic/story-level opportunities across projects and optionally insert approved items into the shared todo DB.

## Arguments

- `scope`: `all` (default) or one of `music`, `life`, `quantum`, `ai_manifest`, `workspace`
- `limit`: max items to propose (default: `20`)
- `apply`: `false` (default) for dry-run preview, `true` for approval-gated DB insert

## Behavior

- Scans project context and synthesizes opportunities
- Scores priorities with the existing 1-10 priority system
- Flags near-duplicate existing todos
- Shows numbered candidate table for approval
- Writes only approved items with source `SCAN`

## Example Invocations

- "Discover opportunities across all projects"
- "Discover for quantum only, limit 8"
- "Discover and apply for workspace, but prompt me for IDs"
