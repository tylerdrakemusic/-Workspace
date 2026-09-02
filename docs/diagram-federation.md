# Federated Diagram Discovery

Each of the six repositories owns `diagrams/diagram-manifest.json` beside its
Mermaid sources. A manifest contains only repository-relative source paths and
semantic metadata: diagram kind, renderer risk, fallback risk, split status, and
parent/derived-view lineage. UTF-8 byte and character counts are not schema
fields and cannot block validation or trigger splitting.

Workspace discovery reads the six canonical repository roots at portal or
dashboard generation time. It ignores `.worktrees` and does not require a
Workspace file edit when a repository adds or changes a diagram. The aggregate
dashboard, gallery, inventory, and architecture checks consume the discovered
records. The validation layer can report missing or invalid manifests, while the current
Workspace checkout retains its local `*.mmd` fallback during the repository
migration.

The schema is versioned at `diagrams/diagram-manifest.schema.json`; producers
must increment the schema version through a coordinated contract change rather
than adding renderer-specific fields ad hoc.