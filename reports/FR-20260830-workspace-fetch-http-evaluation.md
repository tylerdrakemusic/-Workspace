# FR-20260830 Fetch/HTTP MCP Evaluation

Evaluation date: 2026-08-29. Recommendation: **DEFER**.

## Decision
Continue using direct httpx for bounded research retrieval and existing Playwright MCP for browser-only cases; revisit candidates after independently verifiable runtime security evidence.

## Candidates
| Candidate | License | Provenance | Capability | Security evidence |
|---|---|---|---|---|
| zcaceres/fetch-mcp | MIT | GitHub repository API snapshot: archived=false, updated_at=2026-08-27T08:58:21Z, pushed_at=2026-03-12T17:17:24Z | HTTP fetch and text-oriented retrieval; browser rendering not established by this evaluation | Public source metadata only; deployment and runtime policy were not installed or executed |
| jae-jae/fetcher-mcp | MIT | GitHub repository API snapshot: archived=false, updated_at=2026-08-28T18:58:32Z, pushed_at=2026-01-14T07:07:21Z | Playwright-backed web fetching; suitable for browser-rendered pages but operationally heavier | Public source metadata only; deployment and runtime policy were not installed or executed |

## Comparison Matrix
| Target class | httpx | Playwright MCP | fetch-mcp | fetcher-mcp |
|---|---|---|---|---|
| static_html | measured_ok | capable_existing | not_executed | not_executed |
| javascript_light_html | measured_ok | capable_existing | not_executed | not_executed |
| json_rest | measured_ok | capable_existing | not_executed | not_executed |
| github_public | measured_ok | capable_existing | not_executed | not_executed |
| browser_rendered | not_capable | capable_existing | not_executed | not_executed |

## Measured Synthetic httpx Results
The harness used five HTTPS synthetic targets, a five-second timeout, two redirect maximum, 64,000-byte response maximum, eight-request ceiling, and 100 ms minimum interval. Query strings and fragments are removed from recorded URLs.

```json
[
  {
    "url": "https://synthetic.example/static.html",
    "status": "ok",
    "status_code": 200,
    "content_type": "text/html",
    "bytes_read": 41,
    "elapsed_ms": 0.4756999987876043,
    "redirects": 0
  },
  {
    "url": "https://synthetic.example/javascript-light.html",
    "status": "ok",
    "status_code": 200,
    "content_type": "text/html",
    "bytes_read": 70,
    "elapsed_ms": 0.34130000858567655,
    "redirects": 0
  },
  {
    "url": "https://synthetic.example/api.json",
    "status": "ok",
    "status_code": 200,
    "content_type": "application/json",
    "bytes_read": 25,
    "elapsed_ms": 0.3083000046899542,
    "redirects": 0
  },
  {
    "url": "https://synthetic.example/github-public.json",
    "status": "ok",
    "status_code": 200,
    "content_type": "application/json",
    "bytes_read": 53,
    "elapsed_ms": 0.3237999917473644,
    "redirects": 0
  },
  {
    "url": "https://synthetic.example/browser-rendered.html",
    "status": "ok",
    "status_code": 200,
    "content_type": "text/html",
    "bytes_read": 60,
    "elapsed_ms": 0.3149999974993989,
    "redirects": 0
  }
]
```

## Evidence Dimensions
Each matrix row records status, fidelity, structured extraction, setup, maintenance, and ergonomics. Candidate runtime values are `not_executed` because installation and registration are explicitly out of scope; those rows are evidence of the decision boundary, not capability claims.

## Thresholds and Limitations
- `corpus_fidelity`: >= 0.90 measured or independently verified
- `safety`: HTTPS-only, bounded requests, timeout, redirect and response-size limits, redacted metadata, rate limiting
- `adopt`: Only if both thresholds pass and maintenance/security evidence is reproducible
- `candidate_evidence`: Candidate runtime evidence must be measured or independently verified; not_executed does not satisfy adoption
- Candidate MCP servers were not installed, registered, or invoked; candidate rows marked not_executed are capability hypotheses, not measurements.
- Synthetic fixtures measure the shared httpx harness only. Playwright capability is the existing installed baseline, not a new benchmark run.
- No authenticated, private, production, or unbounded target was contacted.

Candidate statuses marked `not_executed` are not runtime measurements. No package was installed, MCP server was registered, user-level `mcp.json` was edited, registry was changed, or workspace-owned HTTP server was created.
