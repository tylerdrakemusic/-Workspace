# FR-20260830 Fetch/HTTP MCP Evaluation Plan

## Objective

Compare two current Fetch/HTTP MCP candidates with direct `httpx` and the existing Playwright capability.

## Evaluation boundaries

- Read-only evaluation only.
- Use a bounded public/synthetic corpus.
- Do not install packages or register MCP servers.
- Do not edit user-level `mcp.json` files.
- Do not automatically modify `MCP_REGISTRY.md`.
- Do not create a workspace-owned HTTP server.

## Comparison dimensions

- Request and response correctness.
- Support for the bounded corpus and representative HTTP behaviors.
- Failure handling, timeouts, and observability.
- Setup and operational overhead compared with direct `httpx` and Playwright.
- Reproducibility and evidence quality.

## Deliverables

- Candidate identification and version/source notes.
- A bounded, reproducible comparison matrix.
- Read-only execution results and limitations.
- A recommendation with evidence-backed caveats.