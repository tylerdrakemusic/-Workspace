from __future__ import annotations

import base64
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


_FAKE_TOKEN = base64.b64encode(
    json.dumps(
        {
            "type": "authorized_user",
            "client_id": "fake.apps.googleusercontent.com",
            "client_secret": "not-a-real-secret",
            "refresh_token": "fake-refresh-token",
        }
    ).encode()
).decode()


def _mock_client():
    from integrations.gmail import GmailServiceClient

    service = MagicMock()
    with patch.dict(os.environ, {"GMAIL_SERVICE_TOKEN": _FAKE_TOKEN}):
        with patch("integrations.gmail.client._load_credentials", return_value=MagicMock()):
            with patch("integrations.gmail.client.build_service", return_value=service):
                client = GmailServiceClient()
    return client, service


@pytest.fixture
def canonical_attachment_root(tmp_path: Path):
    root = Path(__file__).resolve().parents[1] / "tmp" / "gmail-attachments" / tmp_path.name
    root.mkdir(parents=True, exist_ok=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def test_list_attachments_returns_governed_metadata_without_payload_data():
    client, service = _mock_client()
    message = service.users.return_value.messages.return_value
    message.get.return_value.execute.return_value = {
        "id": "message-1",
        "payload": {
            "parts": [
                {
                    "partId": "0",
                    "filename": "report.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "attachment-1", "size": 12},
                }
            ]
        },
    }

    attachments = client.list_attachments("message-1")

    assert attachments == [
        {
            "message_id": "message-1",
            "attachment_id": "attachment-1",
            "filename": "report.pdf",
            "mime_type": "application/pdf",
            "size": 12,
        }
    ]
    assert "data" not in attachments[0]


def test_download_attachment_writes_inside_governed_root_atomically(
    canonical_attachment_root: Path,
):
    client, service = _mock_client()
    message = service.users.return_value.messages.return_value
    message.get.return_value.execute.return_value = {
        "id": "message-1",
        "payload": {
            "parts": [
                {
                    "filename": "../report.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "attachment-1", "size": 5},
                }
            ]
        },
    }
    message.attachments.return_value.get.return_value.execute.return_value = {
        "data": base64.urlsafe_b64encode(b"hello").decode()
    }

    destination = client.download_attachment(
        "message-1", "attachment-1", canonical_attachment_root
    )

    assert destination == canonical_attachment_root / "report.pdf"
    assert destination.read_bytes() == b"hello"
    assert destination.resolve().is_relative_to(canonical_attachment_root.resolve())


def test_download_attachment_accepts_attachment_id_rotated_between_metadata_reads(
    canonical_attachment_root: Path,
):
    client, service = _mock_client()
    message = service.users.return_value.messages.return_value
    message.get.return_value.execute.side_effect = [
        {
            "id": "message-1",
            "payload": {
                "parts": [
                    {
                        "filename": "rotating-id.pdf",
                        "mimeType": "application/pdf",
                        "body": {"attachmentId": "attachment-listed", "size": 5},
                    }
                ]
            },
        },
        {
            "id": "message-1",
            "payload": {
                "parts": [
                    {
                        "filename": "rotating-id.pdf",
                        "mimeType": "application/pdf",
                        "body": {"attachmentId": "attachment-refreshed", "size": 5},
                    }
                ]
            },
        },
    ]
    message.attachments.return_value.get.return_value.execute.return_value = {
        "data": base64.urlsafe_b64encode(b"hello").decode()
    }

    listed = client.list_attachments("message-1")
    destination = client.download_attachment(
        "message-1",
        listed[0]["attachment_id"],
        canonical_attachment_root,
        filename="rotating-id.pdf",
    )

    assert destination.read_bytes() == b"hello"
    message.attachments.return_value.get.assert_called_once_with(
        userId="me", messageId="message-1", id="attachment-refreshed"
    )


def test_download_attachment_default_root_is_repository_canonical_across_cwds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    client, service = _mock_client()
    message = service.users.return_value.messages.return_value
    message.get.return_value.execute.return_value = {
        "id": "message-1",
        "payload": {
            "parts": [
                {
                    "filename": "cwd-independent.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "attachment-1", "size": 5},
                }
            ]
        },
    }
    message.attachments.return_value.get.return_value.execute.return_value = {
        "data": base64.urlsafe_b64encode(b"hello").decode()
    }
    canonical_root = Path(__file__).resolve().parents[1] / "tmp" / "gmail-attachments"
    canonical_destination = canonical_root / "cwd-independent.pdf"
    monkeypatch.chdir(tmp_path)

    try:
        destination = client.download_attachment("message-1", "attachment-1")

        assert destination == canonical_destination
        assert destination.resolve().is_relative_to(canonical_root.resolve())
        assert destination.read_bytes() == b"hello"
    finally:
        canonical_destination.unlink(missing_ok=True)
        (tmp_path / "tmp" / "gmail-attachments" / "cwd-independent.pdf").unlink(
            missing_ok=True
        )


def test_download_attachment_rejects_root_outside_repository_canonical_directory(
    tmp_path: Path,
):
    client, service = _mock_client()

    with pytest.raises(ValueError, match="canonical"):
        client.download_attachment("message-1", "attachment-1", tmp_path)

    service.users.return_value.messages.return_value.get.assert_not_called()


def test_download_attachment_rejects_oversized_encoded_payload_before_decode(
    canonical_attachment_root: Path,
):
    client, service = _mock_client()
    message = service.users.return_value.messages.return_value
    message.get.return_value.execute.return_value = {
        "id": "message-1",
        "payload": {
            "parts": [
                {
                    "filename": "payload.bin",
                    "mimeType": "application/octet-stream",
                    "body": {"attachmentId": "attachment-1", "size": 1},
                }
            ]
        },
    }
    encoded = base64.urlsafe_b64encode(b"x" * (32 * 1024 * 1024 + 1)).decode()
    message.attachments.return_value.get.return_value.execute.return_value = {
        "data": encoded
    }

    with patch("integrations.gmail.client.base64.urlsafe_b64decode") as decoder:
        with pytest.raises(ValueError, match="payload exceeds"):
            client.download_attachment(
                "message-1", "attachment-1", canonical_attachment_root
            )

    decoder.assert_not_called()


def test_download_attachment_rejects_decoded_payload_above_declared_size(
    canonical_attachment_root: Path,
):
    client, service = _mock_client()
    message = service.users.return_value.messages.return_value
    message.get.return_value.execute.return_value = {
        "id": "message-1",
        "payload": {
            "parts": [
                {
                    "filename": "payload.bin",
                    "mimeType": "application/octet-stream",
                    "body": {"attachmentId": "attachment-1", "size": 4},
                }
            ]
        },
    }
    message.attachments.return_value.get.return_value.execute.return_value = {
        "data": base64.urlsafe_b64encode(b"12345").decode()
    }

    with pytest.raises(PermissionError, match="operator_approved=True"):
        client.download_attachment(
            "message-1", "attachment-1", canonical_attachment_root
        )


def test_download_attachment_requires_approval_for_decoded_size_override(
    canonical_attachment_root: Path,
):
    client, service = _mock_client()
    message = service.users.return_value.messages.return_value
    message.get.return_value.execute.return_value = {
        "id": "message-1",
        "payload": {
            "parts": [
                {
                    "filename": "payload.bin",
                    "mimeType": "application/octet-stream",
                    "body": {"attachmentId": "attachment-1", "size": 4},
                }
            ]
        },
    }
    message.attachments.return_value.get.return_value.execute.return_value = {
        "data": base64.urlsafe_b64encode(b"12345").decode()
    }

    destination = client.download_attachment(
        "message-1", "attachment-1", canonical_attachment_root, operator_approved=True
    )

    assert destination.read_bytes() == b"12345"


def test_download_attachment_requires_exact_operator_approval_for_oversized_override(
    canonical_attachment_root: Path,
):
    client, service = _mock_client()
    message = service.users.return_value.messages.return_value
    message.get.return_value.execute.return_value = {
        "id": "message-1",
        "payload": {
            "parts": [
                {
                    "filename": "large.bin",
                    "mimeType": "application/octet-stream",
                    "body": {"attachmentId": "attachment-1", "size": 26 * 1024 * 1024},
                }
            ]
        },
    }

    with pytest.raises(PermissionError, match="operator_approved=True"):
        client.download_attachment(
            "message-1", "attachment-1", canonical_attachment_root, operator_approved=False
        )
    service.users.return_value.messages.return_value.get.assert_called_once()
    service.users.return_value.messages.return_value.attachments.return_value.get.assert_not_called()


def test_download_attachment_rejects_symlinked_destination_root(tmp_path: Path):
    client, service = _mock_client()
    outside = tmp_path / "outside"
    outside.mkdir()
    linked_root = tmp_path / "linked"
    try:
        linked_root.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable in this test environment")

    with pytest.raises(ValueError, match="containment"):
        client.download_attachment("message-1", "attachment-1", linked_root)
    service.users.return_value.messages.return_value.get.assert_not_called()


def test_cleanup_attachment_downloads_is_idempotent(canonical_attachment_root: Path):
    client, _ = _mock_client()
    old_file = canonical_attachment_root / "old.txt"
    fresh_file = canonical_attachment_root / "fresh.txt"
    old_file.write_text("old", encoding="utf-8")
    fresh_file.write_text("fresh", encoding="utf-8")
    old_time = (datetime.now(timezone.utc) - timedelta(days=31)).timestamp()
    os.utime(old_file, (old_time, old_time))

    assert client.cleanup_attachment_downloads(canonical_attachment_root) == 1
    assert client.cleanup_attachment_downloads(canonical_attachment_root) == 0
    assert not old_file.exists()
    assert fresh_file.exists()


def test_attachment_policy_and_capability_are_discoverable():
    from integrations.gmail import ServiceEmailPolicy, describe_capability

    policy = ServiceEmailPolicy.from_config()
    capability = describe_capability()

    assert policy.attachment_max_bytes == 25 * 1024 * 1024
    assert "attachments" in capability["actions"]
    assert capability["action_scopes"]["attachments"].endswith("gmail.readonly")
    assert capability["attachment_download"]["default_max_bytes"] == 25 * 1024 * 1024
    assert capability["attachment_download"]["operator_approval_for_oversized"] is True