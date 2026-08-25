import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


def test_direct_operational_commands_support_init_db_import_chain(tmp_path: Path) -> None:
    source_utils = Path(__file__).resolve().parents[1] / "src" / "utils"
    isolated_utils = tmp_path / "src" / "utils"
    shutil.copytree(source_utils, isolated_utils)

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["WORKSPACE_DB_KEY"] = f"direct-cli-test-{uuid.uuid4().hex}"

    start = subprocess.run(
        [sys.executable, str(isolated_utils / "perf_cli.py"), "start", "direct-cli-test"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert start.returncode == 0, start.stderr
    run_id = start.stdout.strip()
    assert run_id

    record = subprocess.run(
        [
            sys.executable,
            str(isolated_utils / "proof_cli.py"),
            "record",
            run_id,
            "direct-cli-test",
            "command_output",
            "direct operational command",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert record.returncode == 0, record.stderr
    assert record.stdout.strip()