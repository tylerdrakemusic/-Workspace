# Mermaid Diagram Discovery Contract

This generated report records how the Workspace discovers Mermaid diagrams. It
is discovery evidence, not an architecture inventory and not a second source
of diagram truth.

## Six local manifests

The producer contract is one `diagrams/diagram-manifest.json` in each of the
six local repositories: `⊕Workspace`, `∞Life`, `❤Music`, `⟨ψ⟩Quantum`,
`👁AI-Manifest`, and `ΣCapital`. Each manifest owns its repository's diagram
paths, kinds, renderer and fallback risk, split declaration, and lineage. The
manifest schema and its records remain authoritative.

## Workspace-owned cross-project sources

Workspace-owned cross-project diagrams live in the Workspace repository and
are listed by the Workspace manifest. A source that depicts more than one
project does not move ownership to those projects. Ownership follows the
manifest containing the source path.

## Generated aggregate discovery

The federation discovery code reads the six local manifests from sibling
repository roots, excludes nested worktrees, resolves existing source paths,
and retains each source's owning repository. Dashboard and gallery consumers
use this generated aggregate rather than maintaining a hard-coded source
table.

## Validation dimensions

Generated discovery reports and their producer manifests are checked across
these dimensions:

- **structure**: the report contract, schema version, required fields, and
  six-repository manifest set are present;
- **nodes/edges**: diagram budgets and relationship checks inspect Mermaid
  structure without making the report a fixed measurement ledger;
- **renderer/fallback risk**: manifest risk declarations and renderer probes
  identify rendering and fallback concerns;
- **split**: category budgets and manifest declarations identify sources that
  need a split;
- **lineage**: parent and derived-view declarations preserve canonical origin;
- **duplicate/orphan**: discovery reconciles manifest records and existing
  files to expose duplicate ownership or unowned sources.

Architecture sources and manifests are the producer contract. Regenerating
this report is the consumer-side evidence step; architecture changes do not
require hand-editing this generated report.
