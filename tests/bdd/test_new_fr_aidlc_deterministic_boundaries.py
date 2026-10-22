from __future__ import annotations

import argparse
import importlib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from pytest_bdd import given, scenarios, then, when


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOTS = (
    PROJECT_ROOT,
    PROJECT_ROOT.parent / "life",
    PROJECT_ROOT.parent / "music",
    PROJECT_ROOT.parent / "quantum",
    PROJECT_ROOT.parent / "ai-manifest",
    PROJECT_ROOT.parent / "capital",
)
HOOK_CONFIG = PROJECT_ROOT / ".github" / "hooks" / "quantum-model-selector.json"
HOOK_SCRIPT = PROJECT_ROOT / ".github" / "hooks" / "scripts" / "quantum_model_select.py"
CLI_CONTRACTS = (
    ("fr_cli.py", "canonical FR ledger interface"),
    ("proof_cli.py", "does not change FR state"),
    ("perf_cli.py", "Record FR linkage through fr_cli.py"),
    ("feedback_cli.py", "does not edit source"),
    ("complexity_router.py", "persist routing evidence with fr_cli.py record-event"),
)
sys.path.insert(0, str(PROJECT_ROOT / "src" / "utils"))

import complexity_router  # noqa: E402
import fr_cli  # noqa: E402

scenarios("new-fr-aidlc-deterministic-boundaries.feature")


@given(
    "the five shared workflow CLI entry points are selected",
    target_fixture="workflow_cli_contracts",
)
def select_workflow_cli_contracts() -> tuple[tuple[str, str], ...]:
    return CLI_CONTRACTS


@when(
    "each entry point is invoked with --help",
    target_fixture="workflow_cli_help_results",
)
def invoke_workflow_cli_help(
    workflow_cli_contracts: tuple[tuple[str, str], ...],
) -> tuple[tuple[str, str, int, str], ...]:
    results = []
    for script, contract in workflow_cli_contracts:
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "src" / "utils" / script), "--help"],
            capture_output=True,
            check=False,
            cwd=PROJECT_ROOT,
            encoding="utf-8",
        )
        results.append((script, contract, result.returncode, result.stdout))
    return tuple(results)


@then("each exits successfully and exposes its stable handoff contract")
def verify_workflow_cli_help_contracts(
    workflow_cli_help_results: tuple[tuple[str, str, int, str], ...],
) -> None:
    assert len(workflow_cli_help_results) == len(CLI_CONTRACTS)
    for script, contract, returncode, output in workflow_cli_help_results:
        assert returncode == 0, script
        assert contract in " ".join(output.split()), script


def _frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return "" if end < 0 else text[3:end]


@given("agent definitions across all six project paths are loaded", target_fixture="agent_registry")
def agent_definitions_across_projects() -> list[Path]:
    paths = [
        agent_path
        for project_root in PROJECT_ROOTS
        for agent_path in sorted((project_root / ".github" / "agents").glob("*.agent.md"))
    ]
    assert paths
    return paths


@when("the host resolves representative complexity tiers", target_fixture="selected_tiers")
def resolve_representative_tiers() -> tuple[str, ...]:
    return (
        complexity_router.assess_tier(
            files_changed=1,
            has_new_schema=False,
            has_new_agents=False,
            project_count=1,
            is_security_sensitive=False,
        ),
        complexity_router.assess_tier(
            files_changed=5,
            has_new_schema=False,
            has_new_agents=False,
            project_count=2,
            is_security_sensitive=False,
        ),
        complexity_router.assess_tier(
            files_changed=20,
            has_new_schema=False,
            has_new_agents=True,
            project_count=6,
            is_security_sensitive=True,
        ),
    )


@then("agent frontmatter has no model pin and all role tiers remain available")
def verify_host_model_selection(agent_registry: list[Path], selected_tiers: tuple[str, ...]) -> None:
    for path in agent_registry:
        frontmatter = _frontmatter(path.read_text(encoding="utf-8"))
        assert not re.search(r"^model\s*:", frontmatter, re.MULTILINE), path
    assert selected_tiers == ("light", "standard", "heavy")


@given("the session and subagent hook configuration is inspected")
def inspect_selector_hook() -> None:
    assert HOOK_CONFIG.parent.is_dir()


@when("the obsolete model selector registration and script are checked")
def check_selector_paths() -> None:
    assert not HOOK_CONFIG.exists()
    assert not HOOK_SCRIPT.exists()


@then("neither the registration nor selector script is present")
def selector_is_absent() -> None:
    assert not HOOK_CONFIG.exists()
    assert not HOOK_SCRIPT.exists()


@given("one local FR is soaking and an unrelated FR is branched", target_fixture="soaking_ledger")
def independent_fr_states(tmp_path: Path) -> Path:
    database_path = tmp_path / "fr-states.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE feature_requests (id TEXT PRIMARY KEY, state TEXT, updated_at TEXT)"
        )
        connection.executemany(
            "INSERT INTO feature_requests (id, state) VALUES (?, ?)",
            (("FR-SOAKING", "SOAKING"), ("FR-IMPLEMENT", "BRANCHED")),
        )
    return database_path


@when("the canonical FR CLI advances the branched FR to implementation")
def start_implementation_without_waiting_for_unrelated_soak(soaking_ledger: Path) -> None:
    def open_test_ledger() -> sqlite3.Connection:
        connection = sqlite3.connect(soaking_ledger)
        connection.row_factory = sqlite3.Row
        return connection

    with patch.object(fr_cli, "_conn", side_effect=open_test_ledger), patch.object(
        sys, "argv", ["fr_cli.py", "update-state", "FR-IMPLEMENT", "IN_PROGRESS"]
    ):
        fr_cli.main()


@then("the implementation FR advances and the unrelated FR stays soaking")
def verify_unrelated_soak_does_not_block(soaking_ledger: Path) -> None:
    with sqlite3.connect(soaking_ledger) as connection:
        states = dict(connection.execute("SELECT id, state FROM feature_requests"))
    assert states == {"FR-SOAKING": "SOAKING", "FR-IMPLEMENT": "IN_PROGRESS"}


@given("a local FR ledger has an architecture-reviewed FR in automated review", target_fixture="merge_ledger")
def automated_review_ledger(tmp_path: Path) -> Path:
    database_path = tmp_path / "fr.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE feature_requests (
                id TEXT PRIMARY KEY, title TEXT, type TEXT, risk TEXT, projects TEXT,
                state TEXT, branch TEXT, prs TEXT, owner TEXT, opened_at TEXT,
                updated_at TEXT, merged_at TEXT, signed_off_at TEXT, closed_at TEXT,
                final_state TEXT, cycle_timer_run_id TEXT, acceptance_criteria TEXT,
                ai_credits_estimated REAL, usd_cost_estimated REAL, cost_status TEXT,
                cost_source TEXT, cost_reconciliation_status TEXT, cost_finalized_at TEXT
            );
            CREATE TABLE fr_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, fr_id TEXT NOT NULL, ts TEXT NOT NULL,
                agent TEXT NOT NULL, event_type TEXT NOT NULL, summary TEXT NOT NULL,
                details TEXT, next_action TEXT
            );
            CREATE TABLE fr_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, fr_id TEXT NOT NULL, ts TEXT NOT NULL,
                artifact_type TEXT NOT NULL, label TEXT NOT NULL, path_or_url TEXT
            );
            INSERT INTO feature_requests (id, title, state)
            VALUES ('FR-TEST-001', 'Test FR', 'AUTO_REVIEWED');
            INSERT INTO fr_events (fr_id, ts, agent, event_type, summary)
            VALUES ('FR-TEST-001', '2026-10-21T00:00:00Z', 'test', 'finding', 'ARCHITECTURE_REVIEW:PASS');
            """
        )
    return database_path


@when("the canonical FR CLI requests a merge", target_fixture="merge_result")
def request_merge(merge_ledger: Path) -> tuple[int, str]:
    def open_test_ledger() -> sqlite3.Connection:
        connection = sqlite3.connect(merge_ledger)
        connection.row_factory = sqlite3.Row
        return connection

    with patch.object(fr_cli, "_conn", side_effect=open_test_ledger), patch.object(
        sys, "argv", ["fr_cli.py", "update-state", "FR-TEST-001", "MERGED"]
    ):
        try:
            fr_cli.main()
        except SystemExit as error:
            return int(error.code), "blocked"
    return 0, "merged"


@then("the ledger rejects the merge and preserves the automated-review state")
def merge_is_blocked(merge_ledger: Path, merge_result: tuple[int, str]) -> None:
    exit_code, outcome = merge_result
    with sqlite3.connect(merge_ledger) as connection:
        state = connection.execute(
            "SELECT state FROM feature_requests WHERE id='FR-TEST-001'"
        ).fetchone()[0]
    assert exit_code != 0
    assert outcome == "blocked"
    assert state == "AUTO_REVIEWED"


@given(
    "an architecture-reviewed FR is Tyler-approved with pending cost",
    target_fixture="pending_cost_ledger",
)
def approved_fr_with_pending_cost(tmp_path: Path) -> Path:
    database_path = tmp_path / "pending-cost-fr.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE feature_requests (
                id TEXT PRIMARY KEY,
                state TEXT,
                branch TEXT,
                projects TEXT,
                acceptance_criteria TEXT,
                updated_at TEXT,
                cost_status TEXT,
                cost_source TEXT,
                cost_reconciliation_status TEXT
            );
            CREATE TABLE fr_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fr_id TEXT,
                ts TEXT,
                agent TEXT,
                event_type TEXT,
                summary TEXT
            );
            INSERT INTO feature_requests (id, state, cost_status)
            VALUES ('FR-PENDING-COST', 'TYLER_APPROVED', 'pending');
            INSERT INTO fr_events (fr_id, ts, agent, event_type, summary)
            VALUES (
                'FR-PENDING-COST',
                '2026-10-21T00:00:00Z',
                'test',
                'note',
                'ARCHITECTURE_REVIEW:PASS'
            );
            """
        )
    return database_path


@when(
    "the canonical FR CLI requests a merge for the pending-cost FR",
    target_fixture="pending_cost_merge_result",
)
def request_merge_with_pending_cost(pending_cost_ledger: Path) -> tuple[int, str]:
    def open_test_ledger() -> sqlite3.Connection:
        connection = sqlite3.connect(pending_cost_ledger)
        connection.row_factory = sqlite3.Row
        return connection

    with patch.object(fr_cli, "_conn", side_effect=open_test_ledger), patch.object(
        sys,
        "argv",
        ["fr_cli.py", "update-state", "FR-PENDING-COST", "MERGED"],
    ):
        try:
            fr_cli.main()
        except SystemExit as error:
            return int(error.code), "blocked"
    return 0, "merged"


@then("the merge is rejected and the FR remains Tyler-approved")
def pending_cost_merge_is_blocked(
    pending_cost_ledger: Path,
    pending_cost_merge_result: tuple[int, str],
) -> None:
    exit_code, outcome = pending_cost_merge_result
    with sqlite3.connect(pending_cost_ledger) as connection:
        state = connection.execute(
            "SELECT state FROM feature_requests WHERE id='FR-PENDING-COST'"
        ).fetchone()[0]

    assert exit_code != 0
    assert outcome == "blocked"
    assert state == "TYLER_APPROVED"