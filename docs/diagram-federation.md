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

## Transport boundary

The shared renderer (`src/integrations/mermaid/client.py`) sends diagrams to the
hosted `mermaid.ink` service as a compressed **pako** request-target
(`/{svg|img}/pako:<base64url(zlib(JSON({code})))>`), matching the mermaid live
editor serialization that `mermaid.ink` decodes with `pako.inflate`. Compression
keeps the request-target small, and the client measures its exact UTF-8 byte
length and rejects an oversized request **before** any network call, raising a
typed `MermaidTransportError` (a `MermaidRenderError` subclass) instead of
waiting for a provider HTTP 414.

**Provider evidence (dependency-grounded, not invented).** `mermaid.ink` is a
Node.js service. Node's HTTP parser bounds the combined request line (which
carries the request-target) plus request headers by `--max-http-header-size`,
whose default is **16384** bytes. The `mermaid.ink` project documents raising
this flag (`NODE_OPTIONS=--max-http-header-size=…`) to render very large
diagrams, which confirms the request-target is bounded by this Node ceiling. The
service does **not** publish a distinct numeric URI/path cap, so the boundary is
grounded in this Node parser limit rather than an invented provider number.

**Local policy (our conservative choice).** Under the 16384-byte Node ceiling we
reserve **2048** bytes of headroom for the request-line tokens (`GET`,
`HTTP/1.1`) and standard request headers (`Host`, `User-Agent`,
`Accept-Encoding`, `Connection`). The enforced maximum encoded request-target is
therefore **14336** bytes (`16384 − 2048`). This headroom and the resulting
14336-byte limit are a local policy decision, not a provider-published value.

The client constants (`NODE_MAX_HTTP_HEADER_BYTES`,
`REQUEST_HEADER_HEADROOM_BYTES`, `MAX_REQUEST_TARGET_BYTES`) are the single
source of truth; the offline federated guard
(`src/utils/mermaid_transport_guard.py`) reuses the same measurement across all
six repository manifests so every `.mmd` source is checked against this boundary
in deterministic CI without any live provider call.

## CI enforcement

The guard is wired into the Workspace pytest suite, which CI runs through
`tools/run_tests.py` (invoked by `.github/workflows/test.yml`). Two deterministic,
network-free tests carry the contract:

- `tests/test_mermaid_transport_ci_enforcement.py` measures every
  Workspace-owned source listed in `diagrams/diagram-manifest.json` with the
  shared client and asserts each encoded request-target stays within
  `MermaidClient.MAX_REQUEST_TARGET_BYTES`, and asserts the federated guard
  reports no findings for the checkout.
- `tests/test_mermaid_transport_guard.py` exercises the federated discovery,
  measurement, grouping, and diagnostics against synthetic six-repository
  workspaces, including the full clean-coverage case.

**Honest multi-repo scope.** The five sibling repositories are not nested inside
the Workspace checkout, and their unmerged feature branches are never present in
Workspace PR CI. Workspace CI therefore enforces the boundary only for the
Workspace-owned sources it can see; it does **not** validate, and must not claim
to validate, cross-repo or cross-branch diagram repairs. The transport boundary
is a per-source property that holds on every branch and on `main`, so each
repository's own CI (and parent QA on each PR branch) validates that repository's
diagrams independently. A federated run across all six repositories is a local or
release-time evidence step, not a Workspace PR CI dependency.

## Failure diagnostics and split remediation

`federated_transport_findings(workspace_root)` returns a tuple of
`TransportFinding` records (`repository`, `path`, `measured_bytes`,
`limit_bytes`, `remediation`). `format_findings(findings)` renders them for CI
logs and review evidence:

- Compliant run — a single, noise-free line:
  `Mermaid transport guard: no violations across all discovered sources.`
- Violations — a count header plus one line per source:
  `  [<repository>] <path> — <measured>/<limit> bytes — <remediation>`

**Remediation.** An oversized source must be split into bounded derived views so
each view's pako request-target drops below the boundary. Preserve parent/derived
lineage in the owning repository's `diagram-manifest.json` (`lineage.parent` and
`lineage.derived_views`) and keep relationship coverage across the split, exactly
as the architecture diagrams were repaired under this FR. Because pako compression
already keeps typical request-targets far under the limit, a transport violation
signals a genuinely large source rather than a formatting issue.

## Labeled dashboard fallback (runtime renderer failures)

The transport guard is a preflight for the *renderer*; it does not replace the
runtime fallback. When `tools/diagrams_dashboard.py` cannot render a source
(`MermaidRenderError`, which `MermaidTransportError` subclasses), it writes a
labeled fallback SVG card instead of failing the build. The card is marked with
`FALLBACK_MARKER` (`diagrams-dashboard:fallback`) and a `Fallback Preview:`
heading, embeds the error text and a source snapshot, and is surfaced in the
dashboard index with a `fallback` pill and expandable diagnostics. A
transport-boundary breach at runtime therefore degrades to the same labeled
fallback rather than crashing the dashboard. This behavior is covered by
`tests/test_diagrams_dashboard.py`.

## Optional live mermaid.ink probe (non-blocking evidence only)

Live rendering against the hosted `mermaid.ink` service is **evidence
collection, never a unit-test dependency**. The opt-in probe lives at
`tests/test_mermaid_live_probe.py`, carries the `live` marker, and is excluded
from CI by `tools/parallel_test_policy.json` (`excluded_markers` includes
`live`). It additionally self-skips unless `MERMAID_LIVE_PROBE=1` is set, so a
bare `pytest` run never touches the network. Run it manually to confirm the real
transport renders a bounded diagram:

```powershell
$env:MERMAID_LIVE_PROBE = "1"
C:\G\python.exe -m pytest -m live tests/test_mermaid_live_probe.py
```

`tools/diagrams_dashboard.py` (which prefers the local `mmdc` CLI and falls back
to `mermaid.ink` HTTP) is the broader manual evidence path; neither it nor the
probe gates CI.