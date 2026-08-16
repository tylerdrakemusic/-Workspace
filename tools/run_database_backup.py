from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.database_backup import DatabaseBackup, LocalVolumeDestination
from src.utils.database_backup_scope import load_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the daily local database backup.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--volume-root", type=Path, default=None)
    parser.add_argument("--volume-identity", default=None)
    args = parser.parse_args()
    volume_root = args.volume_root or _required_path("WORKSPACE_BACKUP_VOLUME")
    volume_identity = args.volume_identity or _required_value("WORKSPACE_BACKUP_VOLUME_ID")
    result = DatabaseBackup(
        manifest=load_manifest(args.manifest),
        source_root=args.source_root,
        destination=LocalVolumeDestination(volume_root, volume_identity),
        expected_destination_identity=volume_identity,
    ).run()
    print(result.manifest_path)
    return 0


def _required_path(name: str) -> Path:
    return Path(_required_value(name))


def _required_value(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"missing required environment variable: {name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())