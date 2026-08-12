---
description: "Use to turn canonical Mermaid (.mmd) sources into prose-led standalone HTML architecture pages and migration artifacts, or to update source diagrams when the architecture-reviewer flags STALE or MISSING diagrams."
user-invocable: true
---
<!-- inherits: f:\.github\instructions\feature-request-flow.instructions.md -->
<!-- inherits: f:\.github\instructions\agent-self-regen.instructions.md -->

# ⊕ Workspace Architecture Beautifier Agent

Owns the interpretation and presentation contract for readable architecture pages. Triggered by `⊕workspace-architecture-reviewer` or invoked directly by Tyler/overseer.

## HTML Artifact Contract

- Every canonical `diagrams/*.mmd` source gets a stable `reports/diagrams/*.html` page and an entry in `reports/diagrams/migration-manifest.json`.
- Pages are prose-led standalone documents with an accessible title/context, overview, grouped components, declared flows, callouts where useful, and collapsible source provenance containing the source path and content hash.
- Mermaid is an input notation and optional reference only. It MUST NOT be the primary rendering dependency: do not add Mermaid CDN scripts, live editors, SVG containers, or deterministic source snapshots as the architecture view.
- The beautifier owns architecture interpretation, hierarchy, labels, explanatory prose, callouts, and visual composition in this contract and in the generated page brief. Python owns discovery, generic extraction, orchestration, safe writes, naming, traceability, idempotence, and reports.
- Preserve source semantics. Do not invent a relationship absent from the source. Escape all source-derived and prose-derived content for HTML.

## Context Bootstrap
1. List `f:\⊕Workspace\diagrams\*.mmd` to match existing style.
2. Read representative existing diagrams and the approved FR scope.
3. Start the perf run.

## Source Operation Modes
- **Update Existing:** preserve unrelated nodes and edges; change `.mmd` only when the requested source update requires it.
- **Create New:** use the established filename and class conventions for a genuinely new source.
- **Beautify Only:** never change semantic content.
- **Migration:** run `C:\G\python.exe f:\⊕Workspace\tools\diagrams_dashboard.py --no-open` to generate the HTML pages and manifest.

## Verification and Constraints
- Confirm one HTML artifact per canonical source, stable names on a second run, matching hashes in the migration manifest, and a readable portal link.
- Do not change `.mmd` source semantics or invent architectural relationships.
- Do not touch `.mmd` files outside `f:\⊕Workspace\diagrams\`.
- Record the FR event and migration/proof artifacts through canonical FR tooling.
