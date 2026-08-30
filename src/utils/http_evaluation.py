"""Bounded, read-only helpers for the Fetch/HTTP MCP evaluation."""
from __future__ import annotations

from dataclasses import dataclass
import time
from urllib.parse import urljoin, urlparse
from collections.abc import Callable, Iterable

import httpx


@dataclass(frozen=True)
class EvaluationPolicy:
    """Limits applied to every evaluation request."""

    max_requests: int
    timeout_seconds: float
    max_redirects: int
    max_response_bytes: int
    min_interval_seconds: float


@dataclass(frozen=True)
class ProbeResult:
    """Redacted result for one bounded request."""

    url: str
    status: str
    status_code: int | None
    content_type: str | None
    bytes_read: int
    elapsed_ms: float
    redirects: int


def _redact_url(target: str) -> str:
    parsed = urlparse(target)
    return parsed._replace(query="", fragment="").geturl()


def run_corpus(
    targets: Iterable[str],
    policy: EvaluationPolicy,
    *,
    transport: httpx.BaseTransport | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> list[ProbeResult]:
    """Run a bounded GET corpus through httpx and return redacted results."""
    results: list[ProbeResult] = []
    with httpx.Client(
        transport=transport,
        follow_redirects=False,
        max_redirects=policy.max_redirects,
        timeout=policy.timeout_seconds,
    ) as client:
        for index, target in enumerate(targets):
            if index >= policy.max_requests:
                break
            validate_target(target, policy)
            if index:
                sleeper(policy.min_interval_seconds)
            started = time.perf_counter()
            redacted_url = _redact_url(target)
            current_url = target
            redirects = 0
            try:
                while True:
                    with client.stream("GET", current_url) as response:
                        location = response.headers.get("location")
                        if response.is_redirect and location:
                            next_url = urljoin(current_url, location)
                            if urlparse(next_url).scheme.lower() != "https":
                                results.append(
                                    ProbeResult(
                                        url=redacted_url,
                                        status="insecure_redirect",
                                        status_code=response.status_code,
                                        content_type=None,
                                        bytes_read=0,
                                        elapsed_ms=(time.perf_counter() - started) * 1000,
                                        redirects=redirects,
                                    )
                                )
                                break
                            if redirects >= policy.max_redirects:
                                raise httpx.TooManyRedirects(
                                    "redirect limit exceeded", request=response.request
                                )
                            redirects += 1
                            current_url = next_url
                            continue

                        body_size = 0
                        for chunk in response.iter_bytes():
                            body_size += len(chunk)
                            if body_size >= policy.max_response_bytes + 1:
                                body_size = policy.max_response_bytes + 1
                                break
                    status = "response_too_large" if body_size > policy.max_response_bytes else "ok"
                    results.append(
                        ProbeResult(
                            url=redacted_url,
                            status=status,
                            status_code=response.status_code,
                            content_type=response.headers.get("content-type"),
                            bytes_read=body_size,
                            elapsed_ms=(time.perf_counter() - started) * 1000,
                            redirects=redirects,
                        )
                    )
                    break
            except httpx.TooManyRedirects:
                results.append(
                    ProbeResult(
                        redacted_url,
                        "redirect_limit",
                        None,
                        None,
                        0,
                        (time.perf_counter() - started) * 1000,
                        redirects,
                    )
                )
            except httpx.HTTPError:
                results.append(ProbeResult(redacted_url, "request_failed", None, None, 0, 0, 0))
    return results


def build_evaluation_report(
    *,
    candidates: list[dict[str, object]],
    matrix: list[dict[str, object]],
    thresholds: dict[str, object],
    recommendation: str,
    limitations: list[str] | None = None,
) -> dict[str, object]:
    """Build the stable evidence shape consumed by the evaluation report."""
    if len(candidates) != 2:
        raise ValueError("evaluation requires exactly two candidates")
    if recommendation not in {"ADOPT", "DEFER", "REJECT"}:
        raise ValueError("recommendation must be ADOPT, DEFER, or REJECT")
    for candidate in candidates:
        source = candidate.get("source")
        if not isinstance(source, str) or urlparse(source).scheme.lower() != "https":
            raise ValueError("candidate sources must use HTTPS")
        maintenance = candidate.get("maintenance")
        if not isinstance(maintenance, dict) or not maintenance.get("status"):
            raise ValueError("candidate maintenance evidence is required")
    for row in matrix:
        evidence = row.get("evidence")
        if not isinstance(evidence, dict) or not evidence:
            raise ValueError("comparison evidence is required")
        for tool_name, tool_evidence in evidence.items():
            if not isinstance(tool_evidence, dict):
                raise ValueError(f"comparison evidence for {tool_name} must be an object")
            required_fields = {"status", "fidelity", "extraction", "setup", "maintenance", "ergonomics"}
            if not required_fields <= tool_evidence.keys():
                raise ValueError(f"comparison evidence for {tool_name} is incomplete")
    return {
        "candidates": candidates,
        "matrix": matrix,
        "thresholds": thresholds,
        "recommendation": recommendation,
        "limitations": limitations or [],
    }


def validate_target(target: str, policy: EvaluationPolicy) -> str:
    """Validate a public HTTPS target and return its normalized input."""
    if not target or urlparse(target).scheme.lower() != "https":
        raise ValueError("evaluation targets must use HTTPS")
    parsed = urlparse(target)
    if not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("evaluation targets must be public URLs without credentials")
    if policy.max_requests < 1 or policy.timeout_seconds <= 0:
        raise ValueError("evaluation request limits must be positive")
    if policy.max_redirects < 0 or policy.max_response_bytes < 1:
        raise ValueError("evaluation response limits must be non-negative and bounded")
    if policy.min_interval_seconds < 0:
        raise ValueError("evaluation rate limit must be non-negative")
    return target