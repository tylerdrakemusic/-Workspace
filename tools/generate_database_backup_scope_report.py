from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.database_backup_scope import load_manifest, render_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the database backup scope report.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(manifest), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()