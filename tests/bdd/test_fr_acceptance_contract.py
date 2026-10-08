import argparse
import importlib.util
import json
import sqlite3
import sys
import types
from pathlib import Path
from unittest.mock import patch

from pytest_bdd import given, scenarios, then, when

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FR_CLI_PATH = PROJECT_ROOT / "src" / "utils" / "fr_cli.py"


def _reject_database_bootstrap() -> None:
	raise AssertionError("the acceptance-criteria scenario must not open a production database")


def _load_fr_cli() -> types.ModuleType:
	database_module = types.ModuleType("init_fr_db")
	database_module.get_connection = _reject_database_bootstrap
	database_module.init_db = _reject_database_bootstrap
	spec = importlib.util.spec_from_file_location("isolated_fr_cli", FR_CLI_PATH)
	if spec is None or spec.loader is None:
		raise RuntimeError(f"could not load FR CLI from {FR_CLI_PATH}")
	module = importlib.util.module_from_spec(spec)
	with patch.dict(sys.modules, {"init_fr_db": database_module}):
		spec.loader.exec_module(module)
	return module


fr_cli = _load_fr_cli()

scenarios("fr_acceptance_contract.feature")


@given("an open FR has an agreed behavior scenario", target_fixture="fr_contract")
def registered_fr_with_agreed_behavior_scenario(
	tmp_path: Path,
) -> tuple[Path, dict[str, object]]:
	database_path = tmp_path / "fr.db"
	connection = sqlite3.connect(str(database_path))
	connection.executescript(
		"""
		CREATE TABLE feature_requests (
			id TEXT PRIMARY KEY,
			acceptance_criteria TEXT,
			updated_at TEXT,
			state TEXT
		);
		CREATE TABLE fr_events (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			fr_id TEXT NOT NULL,
			ts TEXT NOT NULL,
			agent TEXT NOT NULL,
			event_type TEXT NOT NULL,
			summary TEXT NOT NULL
		);
		INSERT INTO feature_requests (id, state)
		VALUES ('FR-TEST-001', 'OPEN');
		"""
	)
	connection.commit()
	connection.close()
	criteria: dict[str, object] = {
		"acceptance_criteria": [
			{
				"given": "a user has an active session",
				"when": "the user saves a changed preference",
				"then": "the preference is available on the next visit",
			}
		]
	}
	return database_path, criteria


@when("the scenario is recorded as acceptance criteria through the FR CLI")
def record_scenario_through_fr_cli(
	fr_contract: tuple[Path, dict[str, object]],
) -> None:
	database_path, criteria = fr_contract

	def open_test_ledger() -> sqlite3.Connection:
		connection = sqlite3.connect(str(database_path))
		connection.row_factory = sqlite3.Row
		return connection

	with patch.object(fr_cli, "_conn", side_effect=open_test_ledger):
		fr_cli.cmd_set_acceptance_criteria(
			argparse.Namespace(
				fr_id="FR-TEST-001",
				criteria_json=json.dumps(criteria),
			)
		)


@then("the ledger preserves its Given When Then values")
def ledger_preserves_gwt_values(
	fr_contract: tuple[Path, dict[str, object]],
) -> None:
	database_path, criteria = fr_contract
	connection = sqlite3.connect(str(database_path))
	connection.row_factory = sqlite3.Row
	row = connection.execute(
		"SELECT acceptance_criteria, state FROM feature_requests WHERE id=?",
		("FR-TEST-001",),
	).fetchone()
	connection.close()

	assert json.loads(row["acceptance_criteria"]) == criteria
	assert row["state"] == "OPEN"