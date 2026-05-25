# New Feature Request

**Title:** 

<!-- Optional: add any extra context, constraints, or notes below the title.
     Leave blank if the title says it all. -->



---

<!-- ⊕workspace-intake instructions:
     1. Read the title (and any notes) above.
     2. Inspect the codebase to infer as many fields as possible: type, affected
        projects, motivation, risk, dependencies, and out-of-scope boundaries.
     1.5 TODO CROSS-REFERENCE: Query manifest_todos.db for open todos that overlap
        this request. SQL pattern (adapt project key as needed):
          SELECT id, text, priority FROM todos
          WHERE done=0 AND project=<inferred_project>
            AND text LIKE '%<keyword>%'
          ORDER BY priority DESC LIMIT 5;
        Surface any matches in the Phase B scope card under "📎 Related todos".
        On Tyler's confirmation, write the FR ID into each matched row:
          UPDATE todos SET fr_id='<FR-ID>' WHERE id=<matched_id>;
        DB path: f:\👁AI-Manifest\src\data\manifest_todos.db
        If no matches, skip silently.
     3. Run your Phase A interview — but ONLY ask about fields you genuinely cannot
        infer. Skip any question whose answer is obvious from the title, notes, or
        codebase. Fewer questions = better. Use vscode_askQuestions with prefilled
        options as normal.
     4. If the feature is vague or high-risk, invoke the grill-me skill: interview the user one question at a time, walking down each branch of the decision tree, and provide a recommended answer for each.
     5. After the interview (or immediately if nothing is ambiguous), present Tyler
        with a complete FR draft — all fields filled — as a single confirmation block.
     6. Ask Tyler: "Does this look right? Confirm, or tell me what to change."
     7. On confirmation → proceed to Phase B triage (ledger + registry + cycle timer).
     8. On amendments → update the draft and re-confirm.

     ⚠️  DB-ONLY RULE: Register the FR in the DB via `fr_cli.py open` — do NOT
     create a `.md` file in `.github/fr/`. The DB is the sole source of truth.
     (See feature-request-flow.instructions.md § FR Identifier) -->
