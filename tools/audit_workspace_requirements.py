"""Audit exact installed versions of the Workspace-declared packages."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, packages_distributions, version
from pathlib import Path

from packaging.requirements import Requirement


def _direct_pins(requirements_path: Path) -> list[str]:
    pins: list[str] = []
    import_packages = packages_distributions()
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        requirement = Requirement(line)
        try:
            installed_version = version(requirement.name)
        except PackageNotFoundError as error:
            import_name = requirement.name.partition("-")[0].replace("-", "_")
            fallback_distributions = import_packages.get(import_name, [])
            if len(fallback_distributions) > 1:
                wheel_distributions = [
                    name
                    for name in fallback_distributions
                    if name.endswith(("-wheels", "-binary"))
                ]
                fallback_distributions = wheel_distributions
            if len(fallback_distributions) != 1:
                raise RuntimeError(
                    f"Workspace requirement is not installed: {requirement.name}"
                ) from error
            installed_version = version(fallback_distributions[0])
        pins.append(f"{requirement.name}=={installed_version}")
    return pins


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("requirements", type=Path)
    args = parser.parse_args()

    try:
        pins = _direct_pins(args.requirements)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 2

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix="-workspace-audit.txt", delete=False
    ) as audit_file:
        audit_file.write("\n".join(pins) + "\n")
        audit_path = Path(audit_file.name)

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip_audit",
                "-r",
                str(audit_path),
                "--no-deps",
                "--disable-pip",
                "--format=columns",
                "--progress-spinner",
                "off",
            ],
            check=False,
        )
        return result.returncode
    finally:
        audit_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())