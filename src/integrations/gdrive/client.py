"""GDriveClient — Google Drive API client using a service account.

Auth:
    Reads ``GDRIVE_SA_KEY`` Windows environment variable, which must contain
    the base64-encoded contents of a service account JSON key file.

Usage::

    from integrations.gdrive import GDriveClient
    client = GDriveClient()
    files = client.list_files(mime_types=["application/pdf"])
"""
from __future__ import annotations

import base64
import json
import os
from typing import Optional

# ---------------------------------------------------------------------------
# Lazy import helper — allows test suite to mock build_service without
# requiring google-api-python-client to be installed.
# ---------------------------------------------------------------------------


def build_service(credentials):
    """Build and return the Drive v3 service resource.

    Separated into its own function so tests can patch
    ``integrations.gdrive.client.build_service`` easily.
    """
    from googleapiclient.discovery import build  # noqa: PLC0415

    return build("drive", "v3", credentials=credentials)


def _load_credentials():
    """Decode GDRIVE_SA_KEY env var and return google-auth Credentials."""
    raw = os.environ.get("GDRIVE_SA_KEY")
    if not raw:
        raise EnvironmentError(
            "GDRIVE_SA_KEY environment variable is not set. "
            "Set it to the base64-encoded contents of your Google service "
            "account JSON key file.  "
            "See ❤Music/AGENT_STARTUP.md for setup instructions."
        )

    try:
        key_bytes = base64.b64decode(raw)
        key_data = json.loads(key_bytes)
    except Exception as exc:
        raise EnvironmentError(
            f"GDRIVE_SA_KEY could not be decoded: {exc}"
        ) from exc

    from google.oauth2 import service_account  # noqa: PLC0415

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    credentials = service_account.Credentials.from_service_account_info(
        key_data, scopes=scopes
    )
    return credentials


class GDriveClient:
    """Thin wrapper around the Google Drive Files API v3.

    Authentication uses a service account whose JSON key is stored as the
    ``GDRIVE_SA_KEY`` environment variable (base64-encoded).  The key is
    decoded at construction time — it is **never** written to disk or logged.
    """

    _FIELDS = "nextPageToken, files(id, name, mimeType, size, modifiedTime, parents)"

    def __init__(self) -> None:
        credentials = _load_credentials()
        self._service = build_service(credentials)
        self._folder_cache: dict[str, str] = {}  # file_id → resolved path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_files(
        self,
        mime_types: Optional[list[str]] = None,
        page_size: int = 1000,
    ) -> list[dict]:
        """Return all files in Drive matching the given MIME types.

        Args:
            mime_types: Optional list of MIME types to filter by (OR logic).
                If ``None``, all files are returned.
            page_size: Number of files per API page (max 1000).

        Returns:
            List of dicts with keys: ``id``, ``name``, ``mimeType``,
            ``size``, ``modifiedTime``, ``parents``.
        """
        query_parts: list[str] = ["trashed = false"]
        if mime_types:
            mime_clauses = " or ".join(
                f"mimeType = '{m}'" for m in mime_types
            )
            query_parts.append(f"({mime_clauses})")
        q = " and ".join(query_parts)

        results: list[dict] = []
        page_token: Optional[str] = None

        while True:
            kwargs: dict = dict(
                q=q,
                pageSize=page_size,
                fields=self._FIELDS,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            if page_token:
                kwargs["pageToken"] = page_token

            response = self._service.files().list(**kwargs).execute()
            for f in response.get("files", []):
                results.append(
                    {
                        "id": f.get("id", ""),
                        "name": f.get("name", ""),
                        "mimeType": f.get("mimeType", ""),
                        "size": f.get("size", "0"),
                        "modifiedTime": f.get("modifiedTime", ""),
                        "parents": f.get("parents", []),
                    }
                )
            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return results

    def get_folder_path(self, file_id: str, parent_ids: list[str]) -> str:
        """Walk the parent chain and return a "/" separated path string.

        Results are cached to minimise API round-trips.

        Args:
            file_id: The ID of the file whose path we are building.
            parent_ids: The ``parents`` list from the file metadata.

        Returns:
            A path string like ``"My Drive/sheet_music/covers"`` or ``""``
            if the file has no parents.
        """
        if not parent_ids:
            return ""

        parent_id = parent_ids[0]
        if parent_id in self._folder_cache:
            return self._folder_cache[parent_id]

        path_parts: list[str] = []
        current_id: Optional[str] = parent_id

        while current_id:
            if current_id in self._folder_cache:
                path_parts.insert(0, self._folder_cache[current_id])
                break
            try:
                meta = (
                    self._service.files()
                    .get(
                        fileId=current_id,
                        fields="id, name, parents",
                        supportsAllDrives=True,
                    )
                    .execute()
                )
            except Exception:
                break
            path_parts.insert(0, meta.get("name", current_id))
            parents = meta.get("parents", [])
            current_id = parents[0] if parents else None

        resolved = "/".join(path_parts)
        self._folder_cache[parent_id] = resolved
        return resolved

    def download_file(self, file_id: str, dest_path) -> None:
        """Download a binary file (PDF, DOCX, etc.) to *dest_path*.

        Args:
            file_id: Drive file ID.
            dest_path: ``pathlib.Path`` or str destination path.
        """
        import io  # noqa: PLC0415

        from googleapiclient.http import MediaIoBaseDownload  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415

        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        request = self._service.files().get_media(
            fileId=file_id, supportsAllDrives=True
        )
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        dest.write_bytes(fh.getvalue())

    def export_file(
        self,
        file_id: str,
        dest_path,
        mime_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ) -> None:
        """Export a Google Workspace file (Docs, Sheets …) to *dest_path*.

        Args:
            file_id: Drive file ID.
            dest_path: Destination path.
            mime_type: Export MIME type.  Defaults to OOXML (.docx).
        """
        import io  # noqa: PLC0415

        from googleapiclient.http import MediaIoBaseDownload  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415

        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        request = self._service.files().export_media(
            fileId=file_id, mimeType=mime_type
        )
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        dest.write_bytes(fh.getvalue())
