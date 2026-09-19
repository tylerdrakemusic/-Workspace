from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import security_dashboard as security_dashboard


REPORT = Path(__file__).resolve().parents[1] / "reports" / (
    "FR-20260903-open-security-findings-child-521-validation.json"
)


EXPECTED_FINDING_IDS = {
    "61f40e7b898736aa",
    "27a7e8b46f6a08b6",
    "289ea33e609b5a82",
    "e3ec8bbeffdac930",
    "527253498b5b8615",
    "ec411ecdd431e6df",
    "3a0fe1b55ffb14fb",
    "78c30593b76dd5dc",
    "4f02f277527c02a4",
    "5b8259dea4d41729",
    "baed228ad8a155c1",
    "1f5191e7caedb97f",
    "cfe1bb624987949c",
    "ec6370c8c9728e97",
    "b4e172ab6f4fcdb8",
    "5836f32fa4152598",
}


def test_child_521_report_reconciles_every_baseline_finding() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    findings = report["findings"]
    assert {finding["vuln_id"] for finding in findings} == EXPECTED_FINDING_IDS
    assert all(finding["disposition"] in {"false_positive", "remediated"} for finding in findings)
    assert all(finding["evidence"] for finding in findings)
    assert report["central_finding_mutation"] is False


def test_child_521_join_evidence_is_blocked_until_all_children_are_current() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert report["child_state"] == "blocked"
    assert report["join"]["complete"] is False
    assert set(report["join"]["required_children"]) == {
        "517",
        "518",
        "519",
        "520",
        "521",
        "522",
    }
    assert report["join"]["blockers"]


def test_a04_ignores_deterministic_lease_fixture_values_but_keeps_real_secret_detection() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "tests"
        / "test_todo_execution_lifecycle.py"
    ).read_text(encoding="utf-8").splitlines()

    lease_fixture_lines = [
        line
        for line in source
        if 'lease_token="fixture-lease-' in line
    ]
    a04_pattern = next(
        pattern
        for owasp_id, _severity, _description, pattern in security_dashboard.SCAN_PATTERNS
        if owasp_id == "A04"
    )

    assert len(lease_fixture_lines) == 9
    assert all(
        not a04_pattern.search(line)
        or security_dashboard._is_false_positive(line)
        for line in lease_fixture_lines
    )
    fixture_value = "live-looking-" + "token-value"
    assert a04_pattern.search(f"api_token = {fixture_value!r}")
    assert not security_dashboard._is_false_positive(
        f"api_token = {fixture_value!r}"
    )


def test_security_scanner_classifies_deterministic_csrf_fixture_as_false_positive() -> None:
    assert security_dashboard._is_false_positive(
        'csrf_token = "playwright-test-csrf"'
    )


def test_dynamic_supervisor_urls_have_explicit_local_service_suppression() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "tools" / "portal_supervisor.py"
    ).read_text(encoding="utf-8").splitlines()

    local_supervisor_url_lines = [
        line
        for line in source
        if "SUPERVISOR_HOST" in line and "/api/" in line
    ]

    assert len(local_supervisor_url_lines) == 2
    assert all("# nosec A02" in line for line in local_supervisor_url_lines)