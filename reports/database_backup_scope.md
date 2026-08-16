# Workspace Database Backup Scope

Manifest schema version: 1

This report is generated from the versioned policy manifest. It contains database paths and policy metadata only; no database contents are read or copied.

## Classification Taxonomy

canonical, coordination, derived, temporary, legacy, unknown, approval-required

## Database Inventory

| ID | Path | Classification | Backup allowed | Reason |
| --- | --- | --- | --- | --- |
| life-infinitelife | life/health-store | approval-required | no | Health and genomic store; default-denied pending explicit approval. |
| life-nova-config | ∞Life/src/data/nova_config.db | unknown | no | Discovered configuration database; authority and sensitivity not yet established. |
| music-heartmusic | ❤Music/src/data/heartmusic.db | canonical | yes | Authoritative ❤Music application database. |
| music-spirit | ❤Music/spirit.db | unknown | no | Discovered database at project root; authority not yet established. |
| music-vera-config | ❤Music/src/data/vera_config.db | derived | no | Generated configuration store, not an authoritative catalog. |
| music-legacy-heartmusic | ❤Music/data/legacy_heartmusic.db | legacy | no | Explicitly retained legacy store; excluded from future backup scope. |
| quantum-quantumpsi | ⟨ψ⟩Quantum/src/data/quantumpsi.db | canonical | yes | Authoritative ⟨ψ⟩Quantum application database. |
| quantum-orion-config | ⟨ψ⟩Quantum/src/data/orion_config.db | derived | no | Generated configuration store, not an authoritative application database. |
| manifest-todos | 👁AI-Manifest/src/data/manifest_todos.db | coordination | yes | Coordination database used by the manifest service. |
| manifest-todos-legacy | 👁AI-Manifest/src/data/todos.db | legacy | no | Superseded coordination store. |
| manifest-lily-config | 👁AI-Manifest/src/data/lily_config.db | derived | no | Generated configuration store. |
| workspace-agent-perf | ⊕Workspace/src/data/agent_perf.db | coordination | yes | Shared agent performance coordination store. |
| workspace-fr-ledgers | ⊕Workspace/src/data/fr_ledgers.db | coordination | yes | Feature-request coordination ledger. |
| workspace-manifest-todos | ⊕Workspace/src/data/manifest_todos.db | coordination | yes | Shared coordination todo store. |
| workspace | ⊕Workspace/src/data/workspace.db | canonical | yes | Authoritative shared workspace database. |
| capital-sigmacapital | capital/financial-store | approval-required | no | Financial store; default-denied pending explicit approval. |

## Explicit Exclusions

- `**/.git/**`: Version-control internals are not database scope.
- `**/.venv/**`: Virtual environments are reproducible and transient.
- `**/venv/**`: Virtual environments are reproducible and transient.
- `**/.worktrees/**`: Isolated worktrees are non-authoritative copies.
- `**/{cache,caches,.cache}/**`: Caches are regenerable.
- `**/output/**`: Generated output is not an authoritative database source.
- `**/backups/**`: Backup artifacts are excluded from discovery and future scope.
- `**/{tmp,logs,qbackups}/**`: Transient areas are excluded unless separately registered.
- `**/tmp*.{db,sqlite,sqlite3}`: Root-level transient database artifacts are excluded unless separately registered.
- `❤Music/src/data/backups/**`: Existing plaintext backup artifacts are excluded from future scope.

## Scope Boundary

No upload, cloud provider, encryption-key, retention, or restore behavior is implemented by this policy.
