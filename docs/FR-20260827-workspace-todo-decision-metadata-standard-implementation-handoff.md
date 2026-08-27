# FR-20260827 Workspace Todo Decision Metadata Standard

## Implementation Handoff

- FR: `FR-20260827-workspace-todo-decision-metadata-standard`
- Repository: `tylerdrakemusic/-Workspace`
- Branch: `feature/FR-20260827-workspace-todo-decision-metadata-standard`
- Base: `main`
- Scope: workspace-owned TODO decision metadata contract and validation
- Companion repository: `tylerdrakemusic/AI-Manifest`
- Status: approved handoff; implementation intentionally not started

This baseline hands the approved FR to implementation. The implementation
should define one workspace-wide decision metadata contract, identify the
owning persistence and validation boundary, and add focused regression proof
for valid, incomplete, and invalid decision metadata. Existing TODO content
and unrelated project behavior remain unchanged.

The implementation must preserve sensitive-data boundaries, avoid creating
child TODOs, and coordinate the companion AI-Manifest adapter or consumer
through the matching handoff artifact. The final implementation should record
the contract, migration or compatibility behavior, and executable validation
results in the FR ledger.

This commit is a branch baseline only. It contains no feature implementation,
schema mutation, generated data, credentials, or sensitive records.