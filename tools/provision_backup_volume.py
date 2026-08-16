from __future__ import annotations

import argparse
from pathlib import Path

from src.utils.database_backup import LocalVolumeDestination


def provision_volume(volume_root: Path, volume_identity: str) -> Path:
    """Create a trusted marker without replacing an existing marker."""
    LocalVolumeDestination(volume_root, volume_identity, provision=True)
    return volume_root / ".backup-volume-identity"


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision a trusted backup volume marker.")
    parser.add_argument("--volume-root", type=Path, default=Path(r"E:\WorkspaceBackup"))
    parser.add_argument("--volume-identity", required=True)
    args = parser.parse_args()
    print(provision_volume(args.volume_root, args.volume_identity))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())