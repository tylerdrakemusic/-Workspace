"""Unit tests for GDriveClient — FR-20260530-gdrive-integration.

TDD: written before implementation.  All tests must fail on first run due to
ImportError, then pass after implementation.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Allow import from the worktree src/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_SA_KEY = base64.b64encode(
    json.dumps(
        {
            "type": "service_account",
            "project_id": "test",
            "private_key_id": "abc",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n",
            "client_email": "test@test.iam.gserviceaccount.com",
            "client_id": "1234",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    ).encode()
).decode()


# ---------------------------------------------------------------------------
# test_gdrive_client_missing_env_var
# ---------------------------------------------------------------------------


def test_gdrive_client_missing_env_var():
    """GDriveClient() raises EnvironmentError when GDRIVE_SA_KEY is absent."""
    with patch.dict("os.environ", {}, clear=True):
        # Remove GDRIVE_SA_KEY if somehow set
        import os

        os.environ.pop("GDRIVE_SA_KEY", None)

        from integrations.gdrive import GDriveClient  # noqa: PLC0415

        with pytest.raises(EnvironmentError, match="GDRIVE_SA_KEY"):
            GDriveClient()


# ---------------------------------------------------------------------------
# test_gdrive_client_list_files_mocked — pagination + field extraction
# ---------------------------------------------------------------------------


def test_gdrive_client_list_files_mocked():
    """list_files() aggregates pages and returns expected dicts."""
    # Two pages: first has nextPageToken, second does not.
    page1 = {
        "files": [
            {
                "id": "file1",
                "name": "Song A.pdf",
                "mimeType": "application/pdf",
                "size": "12345",
                "modifiedTime": "2025-01-01T00:00:00.000Z",
                "parents": ["folder1"],
            }
        ],
        "nextPageToken": "tok_abc",
    }
    page2 = {
        "files": [
            {
                "id": "file2",
                "name": "Song B.pdf",
                "mimeType": "application/pdf",
                "size": "67890",
                "modifiedTime": "2025-02-01T00:00:00.000Z",
                "parents": ["folder2"],
            }
        ]
        # no nextPageToken → last page
    }

    mock_list = MagicMock()
    mock_list.execute.side_effect = [page1, page2]

    mock_files = MagicMock()
    mock_files.list.return_value = mock_list

    mock_service = MagicMock()
    mock_service.files.return_value = mock_files

    with patch.dict("os.environ", {"GDRIVE_SA_KEY": _FAKE_SA_KEY}):
        with patch("integrations.gdrive.client._load_credentials", return_value=MagicMock()):
            with patch(
                "integrations.gdrive.client.build_service",
                return_value=mock_service,
            ):
                from integrations.gdrive import GDriveClient  # noqa: PLC0415

                client = GDriveClient()
                results = client.list_files(mime_types=["application/pdf"])

    assert len(results) == 2
    assert results[0]["id"] == "file1"
    assert results[0]["name"] == "Song A.pdf"
    assert results[0]["parents"] == ["folder1"]
    assert results[1]["id"] == "file2"


# ---------------------------------------------------------------------------
# test_gdrive_client_pagination — nextPageToken forwarded correctly
# ---------------------------------------------------------------------------


def test_gdrive_client_pagination_token_forwarded():
    """Verify that the page token from page1 is passed to the second API call."""
    page1 = {
        "files": [{"id": "f1", "name": "A.pdf", "mimeType": "application/pdf", "size": "1", "modifiedTime": "2025-01-01T00:00:00.000Z", "parents": []}],
        "nextPageToken": "next_tok",
    }
    page2 = {"files": []}

    mock_list = MagicMock()
    mock_list.execute.side_effect = [page1, page2]

    mock_files = MagicMock()
    mock_files.list.return_value = mock_list

    mock_service = MagicMock()
    mock_service.files.return_value = mock_files

    with patch.dict("os.environ", {"GDRIVE_SA_KEY": _FAKE_SA_KEY}):
        with patch("integrations.gdrive.client._load_credentials", return_value=MagicMock()):
            with patch("integrations.gdrive.client.build_service", return_value=mock_service):
                from integrations.gdrive import GDriveClient  # noqa: PLC0415

                client = GDriveClient()
                client.list_files()

    # Second call to files().list() should include pageToken
    calls = mock_files.list.call_args_list
    assert len(calls) == 2
    _, kwargs2 = calls[1]
    assert kwargs2.get("pageToken") == "next_tok"
