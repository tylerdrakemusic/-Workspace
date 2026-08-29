# FR-20260827 Workspace Todo Decision Metadata Standard

## Implementation Handoff

- FR: `FR-20260827-workspace-todo-decision-metadata-standard`
- Repository: `tylerdrakemusic/-Workspace`
- Branch: `feature/FR-20260827-workspace-todo-decision-metadata-standard`
- Base: `main`
- Scope: workspace-owned TODO decision metadata contract and validation
- Companion repository: `tylerdrakemusic/AI-Manifest`
- Status: implementation complete; focused validation passed

The implementation defines one workspace-wide decision metadata contract in
`src/utils/todo_decision_metadata.py`, with focused regression proof for valid,
incomplete, invalid, high-impact, persistence, and priority-guidance behavior.
Existing TODO content and unrelated project behavior remain unchanged.

The implementation must preserve sensitive-data boundaries, avoid creating
child TODOs, and coordinate the companion AI-Manifest adapter or consumer
through the matching handoff artifact. The final implementation should record
the contract, migration or compatibility behavior, and executable validation
results in the FR ledger.

Validation: `C:\\G\\python.exe -m pytest tests/test_todo_decision_metadata.py -q`
passed with 11 tests. This handoff contains no generated data, credentials, or
sensitive records.