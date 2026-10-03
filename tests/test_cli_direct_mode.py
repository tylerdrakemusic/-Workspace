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


def _prepare_isolated_proof_cli(tmp_path: Path) -> tuple[Path, dict[str, str], str]:
    source_utils = Path(__file__).resolve().parents[1] / "src" / "utils"
    isolated_utils = tmp_path / "src" / "utils"
    shutil.copytree(source_utils, isolated_utils)

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONUTF8"] = "1"
    environment["WORKSPACE_DB_KEY"] = f"proof-contention-test-{uuid.uuid4().hex}"

    start = subprocess.run(
        [sys.executable, str(isolated_utils / "perf_cli.py"), "start", "proof-contention-test"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert start.returncode == 0, start.stderr
    return isolated_utils, environment, start.stdout.strip()


def _start_proof_database_lock(
    tmp_path: Path, isolated_utils: Path, environment: dict[str, str]
) -> subprocess.Popen[str]:
    lock_script = """
import sys
sys.path.insert(0, sys.argv[1])
from init_db import get_connection
connection = get_connection()
connection.execute('BEGIN IMMEDIATE')
print('LOCKED', flush=True)
sys.stdin.readline()
connection.rollback()
connection.close()
"""
    process = subprocess.Popen(
        [sys.executable, "-c", lock_script, str(isolated_utils)],
        cwd=tmp_path,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stdout.readline().strip() == "LOCKED"
    return process


def _release_proof_database_lock(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        assert process.stdin is not None
        process.stdin.write("release\n")
        process.stdin.flush()
    process.communicate(timeout=10)


def _run_proof_report(isolated_utils: Path, environment: dict[str, str], run_id: str) -> str:
    report = subprocess.run(
        [sys.executable, str(isolated_utils / "proof_cli.py"), "report", run_id],
        cwd=isolated_utils.parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert report.returncode == 0, report.stderr
    return report.stdout


def test_proof_record_retries_contention_and_persists_once(tmp_path: Path) -> None:
    isolated_utils, environment, run_id = _prepare_isolated_proof_cli(tmp_path)
    lock_process = _start_proof_database_lock(tmp_path, isolated_utils, environment)
    record = None
    try:
        record = subprocess.Popen(
            [
                sys.executable,
                str(isolated_utils / "proof_cli.py"),
                "record",
                run_id,
                "proof-contention-test",
                "command_output",
                "contention recovery",
            ],
            cwd=tmp_path,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert record.stderr is not None
        retry_notice = record.stderr.readline()
        _release_proof_database_lock(lock_process)
        stdout, stderr = record.communicate(timeout=10)
    finally:
        _release_proof_database_lock(lock_process)

    assert retry_notice.startswith("Retrying proof record after transient database lock"), retry_notice
    assert record is not None
    assert record.returncode == 0, stderr
    assert stdout.strip()
    report = _run_proof_report(isolated_utils, environment, run_id)
    assert "Proofs: 1" in report
    assert report.count("contention recovery") == 1


def test_proof_record_reports_bounded_lock_exhaustion_without_success_output(
    tmp_path: Path,
) -> None:
    isolated_utils, environment, run_id = _prepare_isolated_proof_cli(tmp_path)
    lock_process = _start_proof_database_lock(tmp_path, isolated_utils, environment)
    try:
        record = subprocess.run(
            [
                sys.executable,
                str(isolated_utils / "proof_cli.py"),
                "record",
                run_id,
                "proof-contention-test",
                "command_output",
                "must not persist",
            ],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    finally:
        _release_proof_database_lock(lock_process)

    assert record.returncode != 0
    assert not record.stdout.strip()
    assert "Proof record retries exhausted after 3 attempts" in record.stderr
    report = _run_proof_report(isolated_utils, environment, run_id)
    assert "Proofs: 0" in report


def test_proof_record_retries_transient_connection_setup_failure(tmp_path: Path) -> None:
    isolated_utils, environment, run_id = _prepare_isolated_proof_cli(tmp_path)
    script = """
import sys
utils_dir, *cli_args = sys.argv[1:]
sys.path.insert(0, utils_dir)
import proof_cli
from sqlcipher3 import OperationalError
real_connect = proof_cli._connect
attempts = 0
def fail_setup_once():
    global attempts
    attempts += 1
    if attempts == 1:
        raise OperationalError('database is locked')
    return real_connect()
proof_cli._connect = fail_setup_once
sys.argv = ['proof_cli.py', *cli_args]
proof_cli.main()
"""
    record = subprocess.run(
        [sys.executable, "-c", script, str(isolated_utils), "record", run_id,
         "proof-contention-test", "command_output", "setup retry"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert record.returncode == 0, record.stderr
    assert record.stdout.strip()
    assert "Retrying proof record after transient database lock" in record.stderr
    report = _run_proof_report(isolated_utils, environment, run_id)
    assert "Proofs: 1" in report
    assert report.count("setup retry") == 1


def test_proof_record_recognizes_commit_that_succeeded_before_lock_error(
    tmp_path: Path,
) -> None:
    isolated_utils, environment, run_id = _prepare_isolated_proof_cli(tmp_path)
    script = """
import sys
utils_dir, *cli_args = sys.argv[1:]
sys.path.insert(0, utils_dir)
import proof_cli
from sqlcipher3 import OperationalError
real_connect = proof_cli._connect
raised_after_commit = False
class CommitErrorAfterSuccess:
    def __init__(self, connection):
        self.connection = connection
    def __getattr__(self, name):
        return getattr(self.connection, name)
    def commit(self):
        global raised_after_commit
        self.connection.commit()
        if not raised_after_commit:
            raised_after_commit = True
            raise OperationalError('database is locked')
proof_cli._connect = lambda: CommitErrorAfterSuccess(real_connect())
sys.argv = ['proof_cli.py', *cli_args]
proof_cli.main()
"""
    record = subprocess.run(
        [sys.executable, "-c", script, str(isolated_utils), "record", run_id,
         "proof-contention-test", "command_output", "commit ambiguity"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert record.returncode == 0, record.stderr
    assert record.stdout.strip()
    report = _run_proof_report(isolated_utils, environment, run_id)
    assert "Proofs: 1" in report
    assert report.count("commit ambiguity") == 1


def test_proof_record_retries_transient_commit_failure(tmp_path: Path) -> None:
    isolated_utils, environment, run_id = _prepare_isolated_proof_cli(tmp_path)
    script = """
import sys
utils_dir, *cli_args = sys.argv[1:]
sys.path.insert(0, utils_dir)
import proof_cli
from sqlcipher3 import OperationalError
real_connect = proof_cli._connect
commit_attempts = 0
class CommitErrorBeforeSuccess:
    def __init__(self, connection):
        self.connection = connection
    def __getattr__(self, name):
        return getattr(self.connection, name)
    def commit(self):
        global commit_attempts
        commit_attempts += 1
        if commit_attempts == 1:
            raise OperationalError('database is locked')
        return self.connection.commit()
proof_cli._connect = lambda: CommitErrorBeforeSuccess(real_connect())
sys.argv = ['proof_cli.py', *cli_args]
proof_cli.main()
"""
    record = subprocess.run(
        [sys.executable, "-c", script, str(isolated_utils), "record", run_id,
         "proof-contention-test", "command_output", "commit retry"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert record.returncode == 0, record.stderr
    assert record.stdout.strip()
    assert "Retrying proof record after transient database lock (1/3)" in record.stderr
    report = _run_proof_report(isolated_utils, environment, run_id)
    assert "Proofs: 1" in report
    assert report.count("commit retry") == 1


def test_proof_record_does_not_retry_unrelated_database_errors(tmp_path: Path) -> None:
    isolated_utils, environment, run_id = _prepare_isolated_proof_cli(tmp_path)
    script = """
import sys
utils_dir, *cli_args = sys.argv[1:]
sys.path.insert(0, utils_dir)
import proof_cli
from sqlcipher3 import OperationalError
def fail_setup():
    raise OperationalError('disk I/O error')
proof_cli._connect = fail_setup
sys.argv = ['proof_cli.py', *cli_args]
proof_cli.main()
"""
    record = subprocess.run(
        [sys.executable, "-c", script, str(isolated_utils), "record", run_id,
         "proof-contention-test", "command_output", "must not retry"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert record.returncode != 0
    assert "Retrying proof record after transient database lock" not in record.stderr
    assert "disk I/O error" in record.stderr
    report = _run_proof_report(isolated_utils, environment, run_id)
    assert "Proofs: 0" in report