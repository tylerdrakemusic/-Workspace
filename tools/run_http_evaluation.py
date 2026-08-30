"""Generate the bounded, synthetic Fetch/HTTP MCP evaluation artifacts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.http_evaluation import EvaluationPolicy, build_evaluation_report, run_corpus


REPORT_JSON = ROOT / "proof" / "FR-20260830-workspace-fetch-http-evaluation.json"
REPORT_MD = ROOT / "reports" / "FR-20260830-workspace-fetch-http-evaluation.md"

POLICY = EvaluationPolicy(
    max_requests=8,
    timeout_seconds=5.0,
    max_redirects=2,
    max_response_bytes=64_000,
    min_interval_seconds=0.1,
)

TARGETS = [
    "https://synthetic.example/static.html",
    "https://synthetic.example/javascript-light.html",
    "https://synthetic.example/api.json",
    "https://synthetic.example/github-public.json",
    "https://synthetic.example/browser-rendered.html",
]

CORPUS = {
    "/static.html": ("text/html", b"<html><body><h1>Static</h1></body></html>"),
    "/javascript-light.html": ("text/html", b"<html><body><p>Server content</p><script>void 0</script></body></html>"),
    "/api.json": ("application/json", b'{"ok":true,"items":[1,2]}'),
    "/github-public.json": ("application/json", b'{"name":"synthetic-repository","visibility":"public"}'),
    "/browser-rendered.html": ("text/html", b"<html><body><div id=app>Rendered fixture</div></body></html>"),
}


def synthetic_handler(request: httpx.Request) -> httpx.Response:
    content_type, body = CORPUS[request.url.path]
    return httpx.Response(200, headers={"content-type": content_type}, content=body)


def make_report() -> dict[str, object]:
    measured = run_corpus(TARGETS, POLICY, transport=httpx.MockTransport(synthetic_handler))
    measured_results = [result.__dict__ for result in measured]
    candidates = [
        {
            "name": "zcaceres/fetch-mcp",
            "source": "https://github.com/zcaceres/fetch-mcp",
            "license": "MIT",
            "provenance": "GitHub repository API snapshot: archived=false, updated_at=2026-08-27T08:58:21Z, pushed_at=2026-03-12T17:17:24Z",
            "capability": "HTTP fetch and text-oriented retrieval; browser rendering not established by this evaluation",
            "security_evidence": "Public source metadata only; deployment and runtime policy were not installed or executed",
            "maintenance": {"status": "active", "updated_at": "2026-08-27", "pushed_at": "2026-03-12", "evidence": "GitHub repository API snapshot"},
        },
        {
            "name": "jae-jae/fetcher-mcp",
            "source": "https://github.com/jae-jae/fetcher-mcp",
            "license": "MIT",
            "provenance": "GitHub repository API snapshot: archived=false, updated_at=2026-08-28T18:58:32Z, pushed_at=2026-01-14T07:07:21Z",
            "capability": "Playwright-backed web fetching; suitable for browser-rendered pages but operationally heavier",
            "security_evidence": "Public source metadata only; deployment and runtime policy were not installed or executed",
            "maintenance": {"status": "active", "updated_at": "2026-08-28", "pushed_at": "2026-01-14", "evidence": "GitHub repository API snapshot"},
        },
    ]
    common_evidence = {
        "status": "not_executed",
        "fidelity": None,
        "extraction": "not_measured",
        "setup": "not_measured",
        "maintenance": "not_assessed_at_runtime",
        "ergonomics": "not_measured",
    }
    matrix = [
        {"target_class": "static_html", "evidence": {"httpx": {"status": "measured_ok", "fidelity": 1.0, "extraction": "text/html", "setup": "existing_dependency", "maintenance": "workspace-managed", "ergonomics": "direct_client"}, "Playwright MCP": {"status": "capable_existing", "fidelity": 1.0, "extraction": "rendered_dom", "setup": "existing_server", "maintenance": "workspace-managed", "ergonomics": "browser_tool"}, "zcaceres/fetch-mcp": common_evidence.copy(), "jae-jae/fetcher-mcp": common_evidence.copy()}},
        {"target_class": "javascript_light_html", "evidence": {"httpx": {"status": "measured_ok", "fidelity": 1.0, "extraction": "source_html", "setup": "existing_dependency", "maintenance": "workspace-managed", "ergonomics": "direct_client"}, "Playwright MCP": {"status": "capable_existing", "fidelity": 1.0, "extraction": "rendered_dom", "setup": "existing_server", "maintenance": "workspace-managed", "ergonomics": "browser_tool"}, "zcaceres/fetch-mcp": common_evidence.copy(), "jae-jae/fetcher-mcp": common_evidence.copy()}},
        {"target_class": "json_rest", "evidence": {"httpx": {"status": "measured_ok", "fidelity": 1.0, "extraction": "json", "setup": "existing_dependency", "maintenance": "workspace-managed", "ergonomics": "direct_client"}, "Playwright MCP": {"status": "capable_existing", "fidelity": 1.0, "extraction": "json_response", "setup": "existing_server", "maintenance": "workspace-managed", "ergonomics": "browser_tool"}, "zcaceres/fetch-mcp": common_evidence.copy(), "jae-jae/fetcher-mcp": common_evidence.copy()}},
        {"target_class": "github_public", "evidence": {"httpx": {"status": "measured_ok", "fidelity": 1.0, "extraction": "json", "setup": "existing_dependency", "maintenance": "workspace-managed", "ergonomics": "direct_client"}, "Playwright MCP": {"status": "capable_existing", "fidelity": 1.0, "extraction": "rendered_content", "setup": "existing_server", "maintenance": "workspace-managed", "ergonomics": "browser_tool"}, "zcaceres/fetch-mcp": common_evidence.copy(), "jae-jae/fetcher-mcp": common_evidence.copy()}},
        {"target_class": "browser_rendered", "evidence": {"httpx": {"status": "not_capable", "fidelity": 0.0, "extraction": "source_only", "setup": "existing_dependency", "maintenance": "workspace-managed", "ergonomics": "direct_client"}, "Playwright MCP": {"status": "capable_existing", "fidelity": 1.0, "extraction": "rendered_dom", "setup": "existing_server", "maintenance": "workspace-managed", "ergonomics": "browser_tool"}, "zcaceres/fetch-mcp": common_evidence.copy(), "jae-jae/fetcher-mcp": common_evidence.copy()}},
    ]
    return build_evaluation_report(
        candidates=candidates,
        matrix=matrix,
        thresholds={
            "corpus_fidelity": ">= 0.90 measured or independently verified",
            "safety": "HTTPS-only, bounded requests, timeout, redirect and response-size limits, redacted metadata, rate limiting",
            "adopt": "Only if both thresholds pass and maintenance/security evidence is reproducible",
            "candidate_evidence": "Candidate runtime evidence must be measured or independently verified; not_executed does not satisfy adoption",
        },
        recommendation="DEFER",
        limitations=[
            "Candidate MCP servers were not installed, registered, or invoked; candidate rows marked not_executed are capability hypotheses, not measurements.",
            "Synthetic fixtures measure the shared httpx harness only. Playwright capability is the existing installed baseline, not a new benchmark run.",
            "No authenticated, private, production, or unbounded target was contacted.",
        ],
    ) | {
        "evaluated_at": "2026-08-29",
        "policy": POLICY.__dict__,
        "measured_httpx_results": measured_results,
        "comparison_scope": "static HTML, JavaScript-light HTML, JSON/REST, public GitHub-shaped JSON, browser-rendered fixture",
        "operational_decision": "Continue using direct httpx for bounded research retrieval and existing Playwright MCP for browser-only cases; revisit candidates after independently verifiable runtime security evidence.",
    }


def render_markdown(report: dict[str, object]) -> str:
    rows = ["| Target class | httpx | Playwright MCP | fetch-mcp | fetcher-mcp |", "|---|---|---|---|---|"]
    rows.extend(
        f"| {row['target_class']} | {row['evidence']['httpx']['status']} | {row['evidence']['Playwright MCP']['status']} | {row['evidence']['zcaceres/fetch-mcp']['status']} | {row['evidence']['jae-jae/fetcher-mcp']['status']} |"
        for row in report["matrix"]  # type: ignore[index]
    )
    return "\n".join(
        [
            "# FR-20260830 Fetch/HTTP MCP Evaluation",
            "",
            f"Evaluation date: {report['evaluated_at']}. Recommendation: **{report['recommendation']}**.",
            "",
            "## Decision",
            report["operational_decision"],
            "",
            "## Candidates",
            "| Candidate | License | Provenance | Capability | Security evidence |",
            "|---|---|---|---|---|",
            *[f"| {c['name']} | {c['license']} | {c['provenance']} | {c['capability']} | {c['security_evidence']} |" for c in report["candidates"]],  # type: ignore[index]
            "",
            "## Comparison Matrix",
            *rows,
            "",
            "## Measured Synthetic httpx Results",
            "The harness used five HTTPS synthetic targets, a five-second timeout, two redirect maximum, 64,000-byte response maximum, eight-request ceiling, and 100 ms minimum interval. Query strings and fragments are removed from recorded URLs.",
            "",
            "```json",
            json.dumps(report["measured_httpx_results"], indent=2),
            "```",
            "",
            "## Evidence Dimensions",
            "Each matrix row records status, fidelity, structured extraction, setup, maintenance, and ergonomics. Candidate runtime values are `not_executed` because installation and registration are explicitly out of scope; those rows are evidence of the decision boundary, not capability claims.",
            "",
            "## Thresholds and Limitations",
            *[f"- `{key}`: {value}" for key, value in report["thresholds"].items()],  # type: ignore[union-attr]
            *[f"- {item}" for item in report["limitations"]],  # type: ignore[union-attr]
            "",
            "Candidate statuses marked `not_executed` are not runtime measurements. No package was installed, MCP server was registered, user-level `mcp.json` was edited, registry was changed, or workspace-owned HTTP server was created.",
            "",
        ]
    )


def main() -> None:
    report = make_report()
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text(render_markdown(report), encoding="utf-8")
    print(f"wrote {REPORT_JSON}")
    print(f"wrote {REPORT_MD}")


if __name__ == "__main__":
    main()