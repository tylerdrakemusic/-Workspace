from __future__ import annotations

import json
from pathlib import Path


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