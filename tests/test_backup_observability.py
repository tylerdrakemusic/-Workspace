from __future__ import annotations

import json
from pathlib import Path

from src.utils import database_backup_observability as observability
from tools.run_database_backup import run_scheduled_backups


def test_failure_details_are_redacted_and_structured() -> None:
    error = FileNotFoundError(
        "missing F:/private/ΣCapital/src/data/sigmacapital.db with key SIGMACAPITAL_DB_KEY"
    )

    failure = observability.redact_failure(error)

    assert failure == {
        "error_type": "FileNotFoundError",
        "message": "backup source is unavailable",
    }
    assert "ΣCapital" not in json.dumps(failure)
    assert "SIGMACAPITAL_DB_KEY" not in json.dumps(failure)


def test_retention_preserves_latest_valid_recovery_point(tmp_path: Path) -> None:
    generations = tmp_path / "generations"
    generations.mkdir()
    for name in ("20260801", "20260802", "20260803", "20260804"):
        (generations / name).mkdir()
    for name in ("20260802", "20260803", "20260804"):
        (generations / name / "manifest.json").write_text("invalid", encoding="utf-8")

    removed = observability.enforce_retention(
        generations, retention=2, valid_generations={"20260801"}
    )

    assert removed == ["20260803", "20260802"]
    assert (generations / "20260801").is_dir()
    assert (generations / "20260804").is_dir()


def test_restore_drill_records_latest_twelve_evidence_entries(tmp_path: Path) -> None:
    evidence_path = tmp_path / "restore-drills.jsonl"
    for index in range(14):
        observability.record_restore_drill(
            evidence_path, generation=f"generation-{index}", status="passed"
        )

    records = observability.latest_restore_drills(evidence_path)

    assert len(records) == 12
    assert records[0]["generation"] == "generation-13"
    assert records[-1]["generation"] == "generation-2"


def test_recovery_objectives_report_declared_rpo_and_rto() -> None:
    report = observability.recovery_objectives_report()

    assert report == {"rpo_hours": 24, "rto_hours": 4, "status": "defined"}


def test_workspace_runbooks_document_the_operational_contract() -> None:
    runbook = Path(__file__).parents[1] / "docs" / "runbooks" / "database-backup.md"

    assert runbook.is_file()
    text = runbook.read_text(encoding="utf-8").lower()
    for marker in ("30 generations", "24 hours", "4 hours", "restore drill"):
        assert marker in text


def test_scheduled_failure_exposes_redacted_observation(tmp_path: Path) -> None:
    result = run_scheduled_backups(
        manifest_path=tmp_path / "missing-manifest.json",
        project_roots={"capital": tmp_path / "private"},
        volume_root=tmp_path / "missing-volume",
        volume_identity="trusted",
    )

    assert result.failure == {
        "error_type": "DestinationIdentityError",
        "message": "backup operation failed",
    }
    assert str(tmp_path) not in json.dumps(result.failure)