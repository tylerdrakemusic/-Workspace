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