"""Advisory local audio notification for the AUTO_REVIEWED FR milestone."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.integrations.elevenlabs import ElevenLabsClient


MILESTONE = "AUTO_REVIEWED"
AGENT = "⊕workspace-reviewer"
ARTIFACT_TYPE = "audio_notification"
ARTIFACT_LABEL = "ElevenLabs approval notification — AUTO_REVIEWED"
EVENT_MARKER = "ELEVENLABS_APPROVAL_NOTIFICATION"
CLAIM_SUMMARY = f"{EVENT_MARKER}: {MILESTONE} claimed"
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
_SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class NotificationResult:
	"""Outcome of one advisory notification attempt."""

	status: str
	path: Path | None = None


def _conn():
	from init_fr_db import get_connection, init_db

	init_db()
	return get_connection()


def _now() -> str:
	return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _record_event(conn, fr_id: str, summary: str) -> None:
	now = _now()
	_release_notification_claim(conn, fr_id)
	conn.execute(
		"INSERT INTO fr_events (fr_id, ts, agent, event_type, summary) VALUES (?,?,?,?,?)",
		(fr_id, now, AGENT, "notification", summary),
	)
	conn.execute("UPDATE feature_requests SET updated_at=? WHERE id=?", (now, fr_id))


def _claim_notification(conn, fr_id: str) -> tuple[str, Path | None]:
	conn.execute("BEGIN IMMEDIATE")
	fr = conn.execute(
		"SELECT title, state FROM feature_requests WHERE id=?", (fr_id,)
	).fetchone()
	if not fr or fr["state"] != MILESTONE:
		conn.rollback()
		return "ignored", None

	existing = conn.execute(
		"SELECT path_or_url FROM fr_artifacts WHERE fr_id=? AND artifact_type=? AND label=?",
		(fr_id, ARTIFACT_TYPE, ARTIFACT_LABEL),
	).fetchone()
	if existing:
		conn.rollback()
		return "duplicate", Path(existing["path_or_url"]) if existing["path_or_url"] else None

	claimed = conn.execute(
		"SELECT 1 FROM fr_events WHERE fr_id=? AND agent=? AND event_type=? AND summary=?",
		(fr_id, AGENT, "notification", CLAIM_SUMMARY),
	).fetchone()
	if claimed:
		conn.rollback()
		return "duplicate", None

	_record_event(conn, fr_id, CLAIM_SUMMARY)
	conn.commit()
	return "claimed", None


def _release_notification_claim(conn, fr_id: str) -> None:
	conn.execute(
		"DELETE FROM fr_events WHERE fr_id=? AND agent=? AND event_type=? AND summary=?",
		(fr_id, AGENT, "notification", CLAIM_SUMMARY),
	)


def notify_auto_reviewed(
	fr_id: str,
	*,
	output_dir: str | Path | None = None,
	client_factory: Callable[[], ElevenLabsClient] = ElevenLabsClient,
) -> NotificationResult:
	"""Create one local, fail-open audio notification for an AUTO_REVIEWED FR."""
	conn = _conn()
	status, existing_path = _claim_notification(conn, fr_id)
	if status != "claimed":
		return NotificationResult(status, existing_path)

	try:
		client = client_factory()
		text = f"Feature request {fr_id} passed automated review and awaits Tyler's approval."
		audio = client.text_to_speech(text, DEFAULT_VOICE_ID)
		root = Path(output_dir) if output_dir else Path(__file__).resolve().parents[2] / "proof"
		path = root / _SAFE_ID.sub("_", fr_id) / f"{_SAFE_ID.sub('_', fr_id)}_auto_reviewed.mp3"
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_bytes(audio)
	except TimeoutError:
		_release_notification_claim(conn, fr_id)
		_record_event(
			conn,
			fr_id,
			f"{EVENT_MARKER}: {MILESTONE} failed (advisory; FR state preserved)",
		)
		conn.commit()
		return NotificationResult("failed")
	except EnvironmentError:
		_release_notification_claim(conn, fr_id)
		_record_event(
			conn,
			fr_id,
			f"{EVENT_MARKER}: {MILESTONE} skipped (advisory; FR state preserved)",
		)
		conn.commit()
		return NotificationResult("skipped")
	except Exception:
		_release_notification_claim(conn, fr_id)
		_record_event(
			conn,
			fr_id,
			f"{EVENT_MARKER}: {MILESTONE} failed (advisory; FR state preserved)",
		)
		conn.commit()
		return NotificationResult("failed")

	now = _now()
	conn.execute(
		"INSERT INTO fr_artifacts (fr_id, ts, artifact_type, label, path_or_url) VALUES (?,?,?,?,?)",
		(fr_id, now, ARTIFACT_TYPE, ARTIFACT_LABEL, str(path)),
	)
	_record_event(conn, fr_id, f"{EVENT_MARKER}: {MILESTONE} created local artifact")
	conn.commit()
	return NotificationResult("created", path)


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("fr_id")
	args = parser.parse_args()
	result = notify_auto_reviewed(args.fr_id)
	print(f"{result.status}: {result.path or 'no artifact'}")


if __name__ == "__main__":
	main()