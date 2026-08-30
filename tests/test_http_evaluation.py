from __future__ import annotations

from collections.abc import Iterator

import pytest
import httpx
from tools.run_http_evaluation import render_markdown

from src.utils.http_evaluation import (
    EvaluationPolicy,
    build_evaluation_report,
    run_corpus,
    validate_target,
)


def test_evaluation_policy_rejects_non_https_targets() -> None:
    policy = EvaluationPolicy(
        max_requests=8,
        timeout_seconds=5.0,
        max_redirects=2,
        max_response_bytes=64_000,
        min_interval_seconds=0.1,
    )

    assert validate_target("https://example.com/", policy) == "https://example.com/"
    with pytest.raises(ValueError, match="HTTPS"):
        validate_target("http://example.com/", policy)


def test_corpus_runner_bounds_requests_and_redacts_query_metadata() -> None:
    policy = EvaluationPolicy(
        max_requests=1,
        timeout_seconds=5.0,
        max_redirects=0,
        max_response_bytes=4,
        min_interval_seconds=0,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"12345")

    results = run_corpus(
        ["https://example.com/public?token=must-not-appear", "https://example.com/second"],
        policy,
        transport=httpx.MockTransport(handler),
    )

    assert len(results) == 1
    assert results[0].status == "response_too_large"
    assert results[0].url == "https://example.com/public"
    assert "token" not in results[0].url


def test_corpus_runner_rejects_https_to_http_redirect_without_contacting_target() -> None:
    policy = EvaluationPolicy(1, 5.0, 2, 64_000, 0)
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://example.com/insecure"})

    results = run_corpus(
        ["https://example.com/start"],
        policy,
        transport=httpx.MockTransport(handler),
    )

    assert results[0].status == "insecure_redirect"
    assert requested_urls == ["https://example.com/start"]


def test_corpus_runner_stops_streaming_after_response_limit() -> None:
    policy = EvaluationPolicy(1, 5.0, 0, 4, 0)
    reads = 0

    class BoundedProbeStream(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            nonlocal reads
            for chunk in (b"1234", b"5678", b"9"):
                reads += 1
                yield chunk

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=BoundedProbeStream())

    results = run_corpus(
        ["https://example.com/large"],
        policy,
        transport=httpx.MockTransport(handler),
    )

    assert results[0].status == "response_too_large"
    assert results[0].bytes_read == 5
    assert reads == 2


def test_report_contract_requires_provenance_matrix_thresholds_and_decision() -> None:
    report = build_evaluation_report(
        candidates=[
            {"name": "candidate-a", "source": "https://github.com/example/a", "license": "MIT", "maintenance": {"status": "active"}},
            {"name": "candidate-b", "source": "https://github.com/example/b", "license": "MIT", "maintenance": {"status": "active"}},
        ],
        matrix=[
            {
                "target_class": "json_rest",
                "evidence": {
                    "candidate-a": {"status": "measured_ok", "fidelity": 1.0, "extraction": "json", "setup": "existing", "maintenance": "active", "ergonomics": "direct"},
                    "candidate-b": {"status": "measured_ok", "fidelity": 1.0, "extraction": "json", "setup": "existing", "maintenance": "active", "ergonomics": "direct"},
                },
            }
        ],
        thresholds={"minimum_fidelity": 0.9},
        recommendation="DEFER",
    )

    assert {"candidates", "matrix", "thresholds", "recommendation", "limitations"} <= report.keys()
    assert report["recommendation"] in {"ADOPT", "DEFER", "REJECT"}


def test_report_contract_requires_maintenance_and_comparison_evidence() -> None:
    with pytest.raises(ValueError, match="maintenance"):
        build_evaluation_report(
            candidates=[
                {"name": "candidate-a", "source": "https://github.com/example/a", "license": "MIT"},
                {"name": "candidate-b", "source": "https://github.com/example/b", "license": "MIT"},
            ],
            matrix=[
                {
                    "target_class": "json_rest",
                    "evidence": {
                        "candidate-a": {"status": "not_executed", "fidelity": None, "extraction": "not_measured", "setup": "not_measured", "maintenance": "not_assessed_at_runtime", "ergonomics": "not_measured"},
                        "candidate-b": {"status": "not_executed", "fidelity": None, "extraction": "not_measured", "setup": "not_measured", "maintenance": "not_assessed_at_runtime", "ergonomics": "not_measured"},
                    },
                }
            ],
            thresholds={"minimum_fidelity": 0.9},
            recommendation="DEFER",
        )


def test_rendered_report_uses_not_executed_candidate_status() -> None:
    from tools.run_http_evaluation import make_report

    rendered = render_markdown(make_report())

    assert "expected" not in rendered
    assert "marked `not_executed`" in rendered