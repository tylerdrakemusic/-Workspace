from __future__ import annotations

import base64
import json
import os
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


def test_download_attachment_writes_inside_governed_root_atomically(tmp_path: Path):
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

    destination = client.download_attachment("message-1", "attachment-1", tmp_path)

    assert destination == tmp_path / "report.pdf"
    assert destination.read_bytes() == b"hello"
    assert destination.resolve().is_relative_to(tmp_path.resolve())


def test_download_attachment_rejects_oversized_encoded_payload_before_decode(
    tmp_path: Path,
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
            client.download_attachment("message-1", "attachment-1", tmp_path)

    decoder.assert_not_called()


def test_download_attachment_rejects_decoded_payload_above_declared_size(
    tmp_path: Path,
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
        client.download_attachment("message-1", "attachment-1", tmp_path)


def test_download_attachment_requires_approval_for_decoded_size_override(
    tmp_path: Path,
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
        "message-1", "attachment-1", tmp_path, operator_approved=True
    )

    assert destination.read_bytes() == b"12345"


def test_download_attachment_requires_exact_operator_approval_for_oversized_override(
    tmp_path: Path,
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
            "message-1", "attachment-1", tmp_path, operator_approved=False
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


def test_cleanup_attachment_downloads_is_idempotent(tmp_path: Path):
    client, _ = _mock_client()
    old_file = tmp_path / "old.txt"
    fresh_file = tmp_path / "fresh.txt"
    old_file.write_text("old", encoding="utf-8")
    fresh_file.write_text("fresh", encoding="utf-8")
    old_time = (datetime.now(timezone.utc) - timedelta(days=31)).timestamp()
    os.utime(old_file, (old_time, old_time))

    assert client.cleanup_attachment_downloads(tmp_path) == 1
    assert client.cleanup_attachment_downloads(tmp_path) == 0
    assert not old_file.exists()
    assert fresh_file.exists()


def test_attachment_policy_and_capability_are_discoverable():
    from integrations.gmail import ServiceEmailPolicy, describe_capability

    policy = ServiceEmailPolicy.from_config()
    capability = describe_capability()

    assert policy.attachment_max_bytes == 25 * 1024 * 1024
    assert "attachments" in capability["actions"]
    assert capability["attachment_download"]["default_max_bytes"] == 25 * 1024 * 1024
    assert capability["attachment_download"]["operator_approval_for_oversized"] is True