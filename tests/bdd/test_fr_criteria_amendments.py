from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

from pytest_bdd import given, scenarios, then, when

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))

import fr_cli  # noqa: E402

scenarios("fr_criteria_amendments.feature")


def _criteria_hash(criteria: dict[str, object]) -> str:
    canonical = json.dumps(criteria, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@given(
    "an active FR with current G/W/T criteria",
    target_fixture="amendment_case",
)
def active_fr_with_approved_criteria_amendment(tmp_path: Path) -> dict[str, object]:
    database_path = tmp_path / "fr.db"
    old_criteria: dict[str, object] = {
        "acceptance_criteria": [
            {"given": "the current scope", "when": "the workflow runs", "then": "the result is recorded"}
        ],
        "parent_join": {"required_todos": ["todo-1"]},
    }
    proposed_criteria = {
        "acceptance_criteria": [
            {"given": "the revised scope", "when": "the workflow runs", "then": "the revised result is recorded"}
        ]
    }
    current_hash = _criteria_hash(old_criteria)
    approval_rationale = "Tyler approved the clarified acceptance outcome"
    approval_summary = (
        f"SCOPE_AMENDMENT_APPROVED: version=1 hash={current_hash} | {approval_rationale}"
    )
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE feature_requests (
                id TEXT PRIMARY KEY, state TEXT, branch TEXT, prs TEXT,
                acceptance_criteria TEXT, criteria_version INTEGER,
                criteria_hash TEXT, updated_at TEXT
            );
            CREATE TABLE fr_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, fr_id TEXT, ts TEXT,
                agent TEXT, event_type TEXT, summary TEXT, details TEXT,
                next_action TEXT
            );
            CREATE TABLE fr_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, fr_id TEXT, ts TEXT,
                artifact_type TEXT, label TEXT, path_or_url TEXT,
                criteria_version INTEGER, criteria_hash TEXT
            );
            CREATE TABLE fr_criteria_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, fr_id TEXT, version INTEGER,
                content TEXT, content_hash TEXT, created_at TEXT,
                approver TEXT, event_id INTEGER, rationale TEXT
            );
            """
        )
        connection.execute(
            "INSERT INTO feature_requests "
            "(id, state, branch, prs, acceptance_criteria, criteria_version, criteria_hash, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "FR-TEST-001",
                "ARCHITECTURE_REVIEW",
                "feature/FR-TEST-001",
                "https://example.test/pull/1",
                json.dumps(old_criteria, ensure_ascii=False),
                1,
                current_hash,
                "2026-10-22T00:00:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO fr_events (fr_id, ts, agent, event_type, summary) VALUES (?, ?, ?, ?, ?)",
            (
                "FR-TEST-001",
                "2026-10-22T00:01:00Z",
                "⊕workspace-intake",
                "decision",
                "SCOPE_APPROVED: behavior-changing | initial scope approved",
            ),
        )
        connection.execute(
            "INSERT INTO fr_events (fr_id, ts, agent, event_type, summary) VALUES (?, ?, ?, ?, ?)",
            (
                "FR-TEST-001",
                "2026-10-22T00:01:15Z",
                "⊕workspace-architecture-reviewer",
                "finding",
                "ARCHITECTURE_REVIEW:PASS",
            ),
        )
        connection.execute(
            "INSERT INTO fr_events (fr_id, ts, agent, event_type, summary) VALUES (?, ?, ?, ?, ?)",
            (
                "FR-TEST-001",
                "2026-10-22T00:01:30Z",
                "Tyler",
                "decision",
                approval_summary,
            ),
        )
        connection.execute(
            "INSERT INTO fr_artifacts "
            "(fr_id, ts, artifact_type, label, path_or_url) VALUES (?, ?, ?, ?, ?)",
            ("FR-TEST-001", "2026-10-22T00:01:20Z", "old-proof", "Old proof", "proof://old"),
        )

    return {
        "database_path": database_path,
        "current_hash": current_hash,
        "old_criteria": old_criteria,
        "proposed_criteria": proposed_criteria,
        "rationale": approval_rationale,
        "exit_code": None,
    }


@when(
    "intake records scope-amendment approval and the CLI receives the full proposed criteria, rationale, and matching expected version"
)
def amend_criteria_through_cli(amendment_case: dict[str, object]) -> None:
    database_path = amendment_case["database_path"]

    def open_test_ledger() -> sqlite3.Connection:
        connection = sqlite3.connect(str(database_path))
        connection.row_factory = sqlite3.Row
        return connection

    arguments = [
        "fr_cli.py",
        "amend-acceptance-criteria",
        "FR-TEST-001",
        json.dumps(amendment_case["proposed_criteria"], ensure_ascii=False),
        "--expected-version",
        "1",
        "--expected-hash",
        str(amendment_case["current_hash"]),
        "--rationale",
        str(amendment_case["rationale"]),
    ]
    with patch.object(fr_cli, "_conn", side_effect=open_test_ledger), patch.object(
        fr_cli, "_now", return_value="2026-10-22T00:02:00Z"
    ), patch.object(sys, "argv", arguments):
        try:
            fr_cli.main()
        except SystemExit as exc:
            amendment_case["exit_code"] = int(exc.code)
        else:
            amendment_case["exit_code"] = 0


@then("it atomically stores a new immutable criteria version and makes it current")
def verify_criteria_amendment_snapshot(
    amendment_case: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    assert amendment_case["exit_code"] == 0
    database_path = amendment_case["database_path"]
    updated_criteria = {
        **amendment_case["old_criteria"],
        "acceptance_criteria": amendment_case["proposed_criteria"]["acceptance_criteria"],
    }
    expected_hash = _criteria_hash(updated_criteria)

    with sqlite3.connect(str(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        current = connection.execute(
            "SELECT state, branch, prs, acceptance_criteria, criteria_version, criteria_hash "
            "FROM feature_requests WHERE id=?",
            ("FR-TEST-001",),
        ).fetchone()
        snapshots = connection.execute(
            "SELECT version, content, content_hash, created_at, approver, event_id, rationale "
            "FROM fr_criteria_history WHERE fr_id=? ORDER BY version",
            ("FR-TEST-001",),
        ).fetchall()

    assert current["state"] == "TRIAGED"
    assert current["branch"] == "feature/FR-TEST-001"
    assert current["prs"] == "https://example.test/pull/1"
    assert json.loads(current["acceptance_criteria"]) == updated_criteria
    assert current["criteria_version"] == 2
    assert current["criteria_hash"] == expected_hash
    assert len(snapshots) == 1
    assert snapshots[0]["version"] == 1
    assert json.loads(snapshots[0]["content"]) == amendment_case["old_criteria"]
    assert snapshots[0]["content_hash"] == amendment_case["current_hash"]
    assert snapshots[0]["created_at"] == "2026-10-22T00:02:00Z"
    assert snapshots[0]["approver"] == "Tyler"
    assert snapshots[0]["event_id"] == 3
    assert snapshots[0]["rationale"] == amendment_case["rationale"]

    assert _run_cli(amendment_case, ["criteria-history", "FR-TEST-001"]) == 0
    readback = capsys.readouterr().out
    assert "Current criteria version: 2" in readback
    assert "Criteria history (1):" in readback
    assert "version=1" in readback
    assert amendment_case["rationale"] in readback


def _run_cli(amendment_case: dict[str, object], arguments: list[str]) -> int:
    database_path = amendment_case["database_path"]

    def open_test_ledger() -> sqlite3.Connection:
        connection = sqlite3.connect(str(database_path))
        connection.row_factory = sqlite3.Row
        return connection

    with patch.object(fr_cli, "_conn", side_effect=open_test_ledger), patch.object(
        sys, "argv", ["fr_cli.py", *arguments]
    ):
        try:
            fr_cli.main()
        except SystemExit as exc:
            return int(exc.code)
    return 0


def _amendment_arguments(
    amendment_case: dict[str, object],
    *,
    criteria_json: str | None = None,
    expected_version: int = 1,
    expected_hash: str | None = None,
    rationale: str | None = None,
) -> list[str]:
    return [
        "amend-acceptance-criteria",
        "FR-TEST-001",
        criteria_json or json.dumps(amendment_case["proposed_criteria"], ensure_ascii=False),
        "--expected-version",
        str(expected_version),
        "--expected-hash",
        expected_hash or str(amendment_case["current_hash"]),
        "--rationale",
        rationale or str(amendment_case["rationale"]),
    ]


def _record_criteria_artifact(
    case: dict[str, object],
    artifact_type: str,
    label: str,
    *,
    version: int,
    criteria_hash: str,
) -> int:
    return _run_cli(
        case,
        [
            "record-artifact",
            "FR-TEST-001",
            artifact_type,
            label,
            "--criteria-version",
            str(version),
            "--criteria-hash",
            criteria_hash,
        ],
    )


def _new_amendment_case(
    tmp_path: Path, name: str, state: str = "ARCHITECTURE_REVIEW"
) -> dict[str, object]:
    case_root = tmp_path / name
    case_root.mkdir(parents=True)
    case = active_fr_with_approved_criteria_amendment(case_root)
    with sqlite3.connect(str(case["database_path"])) as connection:
        connection.execute(
            "UPDATE feature_requests SET state=? WHERE id=?",
            (state, "FR-TEST-001"),
        )
    return case


def _ledger_snapshot(case: dict[str, object]) -> tuple[object, ...]:
    with sqlite3.connect(str(case["database_path"])) as connection:
        current = connection.execute(
            "SELECT state, branch, prs, acceptance_criteria, criteria_version, criteria_hash "
            "FROM feature_requests WHERE id=?",
            ("FR-TEST-001",),
        ).fetchone()
        history_count = connection.execute(
            "SELECT COUNT(*) FROM fr_criteria_history WHERE fr_id=?",
            ("FR-TEST-001",),
        ).fetchone()[0]
        event_count = connection.execute(
            "SELECT COUNT(*) FROM fr_events WHERE fr_id=?", ("FR-TEST-001",)
        ).fetchone()[0]
        artifact_count = connection.execute(
            "SELECT COUNT(*) FROM fr_artifacts WHERE fr_id=?", ("FR-TEST-001",)
        ).fetchone()[0]
    return (*current, history_count, event_count, artifact_count)


@given(
    "missing approval, malformed criteria, a stale expected version, or an inactive/terminal FR",
    target_fixture="rejected_amendment_cases",
)
def invalid_amendment_cases(tmp_path: Path) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    missing_approval = _new_amendment_case(tmp_path, "missing-approval")
    with sqlite3.connect(str(missing_approval["database_path"])) as connection:
        connection.execute(
            "DELETE FROM fr_events WHERE fr_id=? AND summary LIKE 'SCOPE_AMENDMENT_APPROVED:%'",
            ("FR-TEST-001",),
        )
    missing_approval["arguments"] = _amendment_arguments(missing_approval)
    cases.append(missing_approval)

    malformed = _new_amendment_case(tmp_path, "malformed")
    malformed["arguments"] = _amendment_arguments(
        malformed,
        criteria_json=json.dumps(
            {"acceptance_criteria": [{"given": "", "when": "action", "then": "result"}]}
        ),
    )
    cases.append(malformed)

    stale = _new_amendment_case(tmp_path, "stale-version")
    stale["arguments"] = _amendment_arguments(stale, expected_version=2)
    cases.append(stale)

    stale_hash = _new_amendment_case(tmp_path, "stale-hash")
    stale_hash["arguments"] = _amendment_arguments(stale_hash, expected_hash="0" * 64)
    cases.append(stale_hash)

    mismatched_rationale = _new_amendment_case(tmp_path, "mismatched-rationale")
    mismatched_rationale["arguments"] = _amendment_arguments(
        mismatched_rationale, rationale="a different approval rationale"
    )
    cases.append(mismatched_rationale)

    malformed_json = _new_amendment_case(tmp_path, "malformed-json")
    malformed_json["arguments"] = _amendment_arguments(
        malformed_json, criteria_json="not valid JSON"
    )
    cases.append(malformed_json)

    for state in ("INACTIVE", "CLOSED", "ARCHIVED", "MERGED", "SOAKING", "SIGNED_OFF"):
        terminal = _new_amendment_case(tmp_path, f"terminal-{state}", state)
        terminal["arguments"] = _amendment_arguments(terminal)
        cases.append(terminal)
    return cases


@when("an amendment is attempted")
def attempt_invalid_amendments(rejected_amendment_cases: list[dict[str, object]]) -> None:
    for case in rejected_amendment_cases:
        before = _ledger_snapshot(case)
        case["before"] = before
        case["exit_code"] = _run_cli(case, case["arguments"])
        case["after"] = _ledger_snapshot(case)


@then("it is rejected and neither the current criteria nor version history changes")
def verify_invalid_amendments_are_atomic(
    rejected_amendment_cases: list[dict[str, object]],
) -> None:
    for case in rejected_amendment_cases:
        assert case["exit_code"] != 0
        assert case["after"] == case["before"]


@given(
    "a successful amendment at any active pre-merge state",
    target_fixture="active_amendment_cases",
)
def active_premerge_amendment_cases(tmp_path: Path) -> list[dict[str, object]]:
    states = (
        "OPEN", "TRIAGED", "BRANCHED", "IN_PROGRESS", "FUNCTIONAL_QA",
        "ARCHITECTURE_REVIEW", "REVIEW_REQUESTED", "AUTO_REVIEWED",
        "BRANCH_CHECKED_OUT", "CHANGES_REQUESTED", "TYLER_APPROVED",
    )
    return [
        _new_amendment_case(tmp_path, f"active-{state}", state)
        for state in states
    ]


@when("it is committed")
def commit_amendments_and_check_reapproval(
    active_amendment_cases: list[dict[str, object]],
) -> None:
    for case in active_amendment_cases:
        with sqlite3.connect(str(case["database_path"])) as connection:
            case["events_before"] = connection.execute(
                "SELECT id, ts, agent, event_type, summary FROM fr_events "
                "WHERE fr_id=? ORDER BY id",
                ("FR-TEST-001",),
            ).fetchall()
            case["artifacts_before"] = connection.execute(
                "SELECT ts, artifact_type, label, path_or_url FROM fr_artifacts "
                "WHERE fr_id=? ORDER BY id",
                ("FR-TEST-001",),
            ).fetchall()
        case["amend_exit"] = _run_cli(case, _amendment_arguments(case))
        with sqlite3.connect(str(case["database_path"])) as connection:
            current = connection.execute(
                "SELECT state, branch, prs, acceptance_criteria, criteria_version "
                "FROM feature_requests WHERE id=?",
                ("FR-TEST-001",),
            ).fetchone()
            case["state_after_amendment"] = current[0]
            case["branch_after_amendment"] = current[1]
            case["prs_after_amendment"] = current[2]
            case["criteria_after_amendment"] = current[3]
            case["version_after_amendment"] = current[4]
            case["history_before_reapproval"] = connection.execute(
                "SELECT version, content, content_hash, approver, event_id, rationale "
                "FROM fr_criteria_history WHERE fr_id=?",
                ("FR-TEST-001",),
            ).fetchall()
        case["stale_scope_exit"] = _run_cli(
            case, ["update-state", "FR-TEST-001", "BRANCHED"]
        )
        case["state_after_stale_scope"] = _ledger_snapshot(case)[0]
        case["fresh_scope_exit"] = _run_cli(
            case,
            [
                "record-event",
                "FR-TEST-001",
                "⊕workspace-intake",
                "decision",
                "SCOPE_APPROVED: behavior-changing | scope approved for revised criteria",
            ],
        )
        case["rebranch_exit"] = _run_cli(
            case, ["update-state", "FR-TEST-001", "BRANCHED"]
        )
        with sqlite3.connect(str(case["database_path"])) as connection:
            case["events_after"] = connection.execute(
                "SELECT id, ts, agent, event_type, summary FROM fr_events "
                "WHERE fr_id=? ORDER BY id",
                ("FR-TEST-001",),
            ).fetchall()
            case["artifacts_after"] = connection.execute(
                "SELECT ts, artifact_type, label, path_or_url FROM fr_artifacts "
                "WHERE fr_id=? ORDER BY id",
                ("FR-TEST-001",),
            ).fetchall()
            case["final_state"] = connection.execute(
                "SELECT state FROM feature_requests WHERE id=?", ("FR-TEST-001",)
            ).fetchone()[0]


@then(
    "the FR returns to TRIAGED; its branch, PR, old events, artifacts, and previous criteria remain recorded; and fresh scope approval is required before BRANCHED"
)
def verify_active_amendments_preserve_history_and_require_reapproval(
    active_amendment_cases: list[dict[str, object]],
) -> None:
    for case in active_amendment_cases:
        assert case["amend_exit"] == 0
        assert case["state_after_amendment"] == "TRIAGED"
        assert case["branch_after_amendment"] == "feature/FR-TEST-001"
        assert case["prs_after_amendment"] == "https://example.test/pull/1"
        assert json.loads(case["criteria_after_amendment"])["acceptance_criteria"] == case[
            "proposed_criteria"
        ]["acceptance_criteria"]
        assert case["version_after_amendment"] == 2
        assert len(case["history_before_reapproval"]) == 1
        assert json.loads(case["history_before_reapproval"][0][1]) == case["old_criteria"]
        assert case["stale_scope_exit"] != 0
        assert case["state_after_stale_scope"] == "TRIAGED"
        assert case["fresh_scope_exit"] == 0
        assert case["rebranch_exit"] == 0
        assert case["final_state"] == "BRANCHED"
        assert case["events_after"][: len(case["events_before"])] == case["events_before"]
        assert case["artifacts_after"] == case["artifacts_before"]


@given(
    "an FR is CLOSED, ARCHIVED, MERGED, SOAKING, or SIGNED_OFF",
    target_fixture="terminal_amendment_cases",
)
def terminal_amendment_cases(tmp_path: Path) -> list[dict[str, object]]:
    states = ("CLOSED", "ARCHIVED", "MERGED", "SOAKING", "SIGNED_OFF")
    return [
        _new_amendment_case(tmp_path, f"refused-{state}", state)
        for state in states
    ]


@when("amendment is attempted")
def attempt_terminal_amendments(
    terminal_amendment_cases: list[dict[str, object]],
) -> None:
    for case in terminal_amendment_cases:
        case["before"] = _ledger_snapshot(case)
        case["exit_code"] = _run_cli(case, _amendment_arguments(case))
        case["after"] = _ledger_snapshot(case)


@then("the operation is refused without mutation")
def verify_terminal_amendments_are_refused(
    terminal_amendment_cases: list[dict[str, object]],
) -> None:
    for case in terminal_amendment_cases:
        assert case["exit_code"] != 0
        assert case["after"] == case["before"]


@given("a new current criteria version", target_fixture="versioned_amendment_case")
def successfully_amended_fr(tmp_path: Path) -> dict[str, object]:
    case = active_fr_with_approved_criteria_amendment(tmp_path)
    assert _run_cli(case, _amendment_arguments(case)) == 0
    assert _run_cli(
        case,
        [
            "record-event",
            "FR-TEST-001",
            "⊕workspace-intake",
            "decision",
            "SCOPE_APPROVED: behavior-changing | fresh approval for version 2",
        ],
    ) == 0
    with sqlite3.connect(str(case["database_path"])) as connection:
        current = connection.execute(
            "SELECT criteria_version, criteria_hash FROM feature_requests WHERE id=?",
            ("FR-TEST-001",),
        ).fetchone()
    case["current_version"] = current[0]
    case["current_hash"] = current[1]
    case["old_hash"] = _criteria_hash(case["old_criteria"])
    return case


@when("a downstream gate is checked")
def check_current_criteria_gate(versioned_amendment_case: dict[str, object]) -> None:
    case = versioned_amendment_case
    database_path = case["database_path"]
    with sqlite3.connect(str(database_path)) as connection:
        connection.execute(
            "INSERT INTO fr_events (fr_id, ts, agent, event_type, summary) VALUES (?, ?, ?, ?, ?)",
            (
                "FR-TEST-001",
                "2026-10-22T00:03:00Z",
                "⊕workspace-intake",
                "decision",
                "SCOPE_APPROVED: behavior-changing | scope re-approved after criteria amendment",
            ),
        )
    case["branched_exit"] = _run_cli(case, ["update-state", "FR-TEST-001", "BRANCHED"])
    case["in_progress_exit"] = _run_cli(case, ["update-state", "FR-TEST-001", "IN_PROGRESS"])
    with sqlite3.connect(str(database_path)) as connection:
        connection.executemany(
            "INSERT INTO fr_artifacts "
            "(fr_id, ts, artifact_type, label, criteria_version, criteria_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    "FR-TEST-001",
                    "2026-10-22T00:04:00Z",
                    artifact_type,
                    label,
                    1,
                    case["old_hash"],
                )
                for artifact_type, label in (
                    ("implementation-evidence", "IMPLEMENTATION:PASS"),
                    ("functional-qa-evidence", "FUNCTIONAL_QA:PASS"),
                )
            ],
        )
    case["stale_artifact_exit"] = _record_criteria_artifact(
        case,
        "implementation-evidence",
        "IMPLEMENTATION:PASS",
        version=1,
        criteria_hash=str(case["old_hash"]),
    )
    case["stale_qa_exit"] = _run_cli(case, ["update-state", "FR-TEST-001", "FUNCTIONAL_QA"])
    case["current_implementation_exit"] = _record_criteria_artifact(
        case,
        "implementation-evidence",
        "IMPLEMENTATION:PASS",
        version=case["current_version"],
        criteria_hash=str(case["current_hash"]),
    )
    case["current_qa_record_exit"] = _record_criteria_artifact(
        case,
        "functional-qa-evidence",
        "FUNCTIONAL_QA:PASS",
        version=case["current_version"],
        criteria_hash=str(case["current_hash"]),
    )
    case["current_qa_exit"] = _run_cli(case, ["update-state", "FR-TEST-001", "FUNCTIONAL_QA"])
    case["architecture_state_exit"] = _run_cli(
        case, ["update-state", "FR-TEST-001", "ARCHITECTURE_REVIEW"]
    )
    case["stale_architecture_exit"] = _run_cli(
        case, ["update-state", "FR-TEST-001", "REVIEW_REQUESTED"]
    )
    case["current_architecture_record_exit"] = _record_criteria_artifact(
        case,
        "architecture-review-evidence",
        "ARCHITECTURE_REVIEW:PASS",
        version=case["current_version"],
        criteria_hash=str(case["current_hash"]),
    )
    case["current_architecture_exit"] = _run_cli(
        case, ["update-state", "FR-TEST-001", "REVIEW_REQUESTED"]
    )
    case["stale_automated_review_exit"] = _run_cli(
        case, ["update-state", "FR-TEST-001", "AUTO_REVIEWED"]
    )
    case["current_automated_review_record_exit"] = _record_criteria_artifact(
        case,
        "automated-review-evidence",
        "AUTO_REVIEW:PASS",
        version=case["current_version"],
        criteria_hash=str(case["current_hash"]),
    )
    case["current_automated_review_exit"] = _run_cli(
        case, ["update-state", "FR-TEST-001", "AUTO_REVIEWED"]
    )


@then(
    "evidence tied only to an earlier criteria version cannot pass it; current-version evidence is required for implementation/QA, architecture review, and automated review"
)
def verify_current_criteria_evidence_gates(
    versioned_amendment_case: dict[str, object],
) -> None:
    case = versioned_amendment_case
    assert case["branched_exit"] == 0
    assert case["in_progress_exit"] == 0
    assert case["stale_artifact_exit"] != 0
    assert case["stale_qa_exit"] != 0
    assert case["current_implementation_exit"] == 0
    assert case["current_qa_record_exit"] == 0
    assert case["current_qa_exit"] == 0
    assert case["current_architecture_record_exit"] == 0
    assert case["architecture_state_exit"] == 0
    assert case["stale_architecture_exit"] != 0
    assert case["current_architecture_exit"] == 0
    assert case["stale_automated_review_exit"] != 0
    assert case["current_automated_review_record_exit"] == 0
    assert case["current_automated_review_exit"] == 0


@given("a new FR or a correction to existing criteria", target_fixture="intake_repair_case")
def triaged_fr_for_intake_and_repair(tmp_path: Path) -> dict[str, object]:
    case = active_fr_with_approved_criteria_amendment(tmp_path)
    case["intake_criteria"] = {
        "acceptance_criteria": [
            {"given": "an approved intake scope", "when": "the FR is registered", "then": "the GWT criteria are stored"}
        ]
    }
    case["repair_criteria"] = {
        "acceptance_criteria": [
            {"given": "a corrected intake scope", "when": "the FR is repaired", "then": "the corrected GWT criteria are stored"}
        ]
    }
    with sqlite3.connect(str(case["database_path"])) as connection:
        connection.execute(
            "UPDATE feature_requests SET state='TRIAGED', acceptance_criteria=NULL, "
            "criteria_version=0, criteria_hash=NULL WHERE id=?",
            ("FR-TEST-001",),
        )
    return case


@when("existing intake or repair commands are used")
def use_intake_and_repair_commands(intake_repair_case: dict[str, object]) -> None:
    case = intake_repair_case
    case["intake_exit"] = _run_cli(
        case,
        [
            "set-acceptance-criteria",
            "FR-TEST-001",
            json.dumps(case["intake_criteria"], ensure_ascii=False),
            "--source",
            "intake",
        ],
    )
    with sqlite3.connect(str(case["database_path"])) as connection:
        connection.execute(
            "UPDATE feature_requests SET state='ARCHITECTURE_REVIEW' WHERE id=?",
            ("FR-TEST-001",),
        )
    case["repair_exit"] = _run_cli(
        case,
        [
            "set-acceptance-criteria",
            "FR-TEST-001",
            json.dumps(case["repair_criteria"], ensure_ascii=False),
        ],
    )


@then("their current behavior and guards remain unchanged")
def verify_intake_and_repair_compatibility(intake_repair_case: dict[str, object]) -> None:
    case = intake_repair_case
    expected_hash = _criteria_hash(case["repair_criteria"])
    with sqlite3.connect(str(case["database_path"])) as connection:
        connection.row_factory = sqlite3.Row
        fr = connection.execute(
            "SELECT state, acceptance_criteria, criteria_version, criteria_hash "
            "FROM feature_requests WHERE id=?",
            ("FR-TEST-001",),
        ).fetchone()
        history_count = connection.execute(
            "SELECT COUNT(*) FROM fr_criteria_history WHERE fr_id=?",
            ("FR-TEST-001",),
        ).fetchone()[0]
        setter_events = connection.execute(
            "SELECT agent, event_type, summary FROM fr_events "
            "WHERE fr_id=? ORDER BY id DESC LIMIT 2",
            ("FR-TEST-001",),
        ).fetchall()

    assert case["intake_exit"] == 0
    assert case["repair_exit"] == 0
    assert fr["state"] == "ARCHITECTURE_REVIEW"
    assert json.loads(fr["acceptance_criteria"]) == case["repair_criteria"]
    assert fr["criteria_version"] == 1
    assert fr["criteria_hash"] == expected_hash
    assert history_count == 0
    assert tuple(setter_events[0]) == (
        "⊕workspace-ci",
        "metadata-repair",
        "Acceptance criteria repaired through canonical fr_cli.py command",
    )
    assert tuple(setter_events[1]) == (
        "⊕workspace-intake",
        "note",
        "Initial acceptance criteria recorded after scope approval; BRANCHED remains a separate state transition",
    )