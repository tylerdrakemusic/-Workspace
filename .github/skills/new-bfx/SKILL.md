---
name: new-bfx
description: "Use when starting intake for a new bugfix request (BFX); route triage through the workspace overseer and follow the governed feature-request workflow."
---

# New Bugfix Request

Confirm you are acting as `⊕workspace-overseer`. If not, hand off to that agent
before continuing. Treat the user's bug report as the title and any added
context as notes. Ask for a title only when none was supplied.

## Intake

1. Inspect the workspace with available tools before taking action. Prefer
   existing MCP capabilities and avoid ad hoc queries or scripts.
2. Infer the bug type, affected projects, motivation, risk, dependencies, and
   out-of-scope boundaries from the request and nearby code.
3. Cross-reference open TODOs with the governed manifest-coordination tools:
   call `mcp_manifest-coor_list_open_todos(project=<inferred_project>)`, then
   `mcp_manifest-coor_read_todo(todo_id=<candidate_id>)` for relevant matches.
   Surface matches in the Phase B scope card under `Related todos`. Only after
   Tyler confirms a match, call
   `mcp_manifest-coor_link_confirmed_todo_to_fr(todo_id=<matched_id>,
   fr_id=<BFX-ID>, confirmed=true)`. Skip this silently when there are no
   matches. Never query or update the manifest database with SQL.
4. Ask only about fields that cannot be inferred. If the bug is vague or
   medium/high risk, invoke the `grill-me` skill and ask one question at a time,
   offering a recommended answer for each.
5. Present a complete bugfix draft with all fields filled in one confirmation
   block. Ask: "Does this look right? Confirm, or tell me what to change."
6. On amendments, update the draft and confirm it again. On confirmation,
   proceed to Phase B triage: ledger, registry, and cycle timer.
7. Register the BFX in the database through `fr_cli.py open`. The database is
   the sole source of truth; do not create a Markdown file in `.github/fr/`.