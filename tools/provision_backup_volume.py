from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.database_backup import LocalVolumeDestination


def provision_volume(
    volume_root: Path, volume_identity: str, replace_existing: bool = False
) -> Path:
    """Create a trusted marker without replacing an existing marker."""
    LocalVolumeDestination(
        volume_root,
        volume_identity,
        provision=True,
        replace_existing=replace_existing,
    )
    return volume_root / ".backup-volume-identity"


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision a trusted backup volume marker.")
    parser.add_argument("--volume-root", type=Path, default=Path(r"E:\WorkspaceBackup"))
    parser.add_argument("--volume-identity", required=True)
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="replace a non-empty marker only with explicit operator authorization",
    )
    args = parser.parse_args()
    print(provision_volume(args.volume_root, args.volume_identity, args.replace_existing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())