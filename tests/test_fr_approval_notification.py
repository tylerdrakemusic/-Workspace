from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.utils import fr_approval_notification


@pytest.fixture
def ledger(monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE feature_requests (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            state TEXT NOT NULL,
            updated_at TEXT
        );
        CREATE TABLE fr_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fr_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            agent TEXT NOT NULL,
            event_type TEXT NOT NULL,
            summary TEXT NOT NULL,
            details TEXT,
            next_action TEXT
        );
        CREATE TABLE fr_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fr_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            artifact_type TEXT NOT NULL,
            label TEXT NOT NULL,
            path_or_url TEXT
        );
        INSERT INTO feature_requests (id, title, state, updated_at)
        VALUES ('FR-TEST-001', 'Governed approval notification', 'AUTO_REVIEWED', '2026-08-13');
        """
    )
    monkeypatch.setattr(fr_approval_notification, "_conn", lambda: conn, raising=False)
    yield conn
    conn.close()


class FakeClient:
    calls: list[str] = []

    def __init__(self) -> None:
        self.calls = []

    def text_to_speech(self, text: str, voice_id: str) -> bytes:
        self.calls.append(text)
        return b"fake-mp3"


def test_success_creates_local_artifact_and_governed_records(
    ledger: sqlite3.Connection, tmp_path: Path
) -> None:
    client = FakeClient()

    result = fr_approval_notification.notify_auto_reviewed(
        "FR-TEST-001",
        output_dir=tmp_path,
        client_factory=lambda: client,
    )

    assert result.status == "created"
    assert result.path is not None and result.path.read_bytes() == b"fake-mp3"
    assert ledger.execute("SELECT COUNT(*) FROM fr_artifacts").fetchone()[0] == 1
    assert ledger.execute("SELECT COUNT(*) FROM fr_events").fetchone()[0] == 1
    assert "AUTO_REVIEWED" in ledger.execute(
        "SELECT summary FROM fr_events"
    ).fetchone()[0]


def test_missing_credentials_is_advisory_and_preserves_state(
    ledger: sqlite3.Connection, tmp_path: Path
) -> None:
    def missing_credentials() -> object:
        raise EnvironmentError("missing credentials")

    result = fr_approval_notification.notify_auto_reviewed(
        "FR-TEST-001",
        output_dir=tmp_path,
        client_factory=missing_credentials,
    )

    assert result.status == "skipped"
    assert ledger.execute(
        "SELECT state FROM feature_requests WHERE id='FR-TEST-001'"
    ).fetchone()[0] == "AUTO_REVIEWED"
    assert ledger.execute("SELECT COUNT(*) FROM fr_artifacts").fetchone()[0] == 0


def test_synthesis_failure_is_advisory_and_does_not_create_artifact(
    ledger: sqlite3.Connection, tmp_path: Path
) -> None:
    class FailingClient:
        def text_to_speech(self, text: str, voice_id: str) -> bytes:
            raise TimeoutError("ElevenLabs timed out")

    result = fr_approval_notification.notify_auto_reviewed(
        "FR-TEST-001",
        output_dir=tmp_path,
        client_factory=FailingClient,
    )

    assert result.status == "failed"
    assert result.path is None
    assert not list(tmp_path.rglob("*.mp3"))
    assert ledger.execute(
        "SELECT state FROM feature_requests WHERE id='FR-TEST-001'"
    ).fetchone()[0] == "AUTO_REVIEWED"


def test_repeated_milestone_processing_does_not_duplicate_artifact(
    ledger: sqlite3.Connection, tmp_path: Path
) -> None:
    client = FakeClient()

    first = fr_approval_notification.notify_auto_reviewed(
        "FR-TEST-001", output_dir=tmp_path, client_factory=lambda: client
    )
    second = fr_approval_notification.notify_auto_reviewed(
        "FR-TEST-001", output_dir=tmp_path, client_factory=lambda: client
    )

    assert first.status == "created"
    assert second.status == "duplicate"
    assert second.path == first.path
    assert len(client.calls) == 1
    assert ledger.execute("SELECT COUNT(*) FROM fr_artifacts").fetchone()[0] == 1


def test_non_auto_reviewed_state_is_unchanged_and_not_synthesized(
    ledger: sqlite3.Connection, tmp_path: Path
) -> None:
    ledger.execute(
        "UPDATE feature_requests SET state='REVIEW_REQUESTED' WHERE id='FR-TEST-001'"
    )
    ledger.commit()
    client = FakeClient()

    result = fr_approval_notification.notify_auto_reviewed(
        "FR-TEST-001", output_dir=tmp_path, client_factory=lambda: client
    )

    assert result.status == "ignored"
    assert client.calls == []
    assert ledger.execute(
        "SELECT state FROM feature_requests WHERE id='FR-TEST-001'"
    ).fetchone()[0] == "REVIEW_REQUESTED"