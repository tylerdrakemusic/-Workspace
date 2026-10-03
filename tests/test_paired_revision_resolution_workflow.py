from pathlib import Path
import os
import shutil
import subprocess


WORKFLOW_PATH = Path(__file__).parents[1] / ".github" / "workflows" / "test.yml"
PEER_REPOSITORY = "tylerdrakemusic/AI-Manifest"
PR_SHA = "1234567890abcdef1234567890abcdef12345678"
MAIN_SHA = "abcdef1234567890abcdef1234567890abcdef12"


def _extract_peer_setup_script() -> str:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        step_start = workflow.index("- name: Set up peer contract")
        run_start = workflow.index("run: |\n", step_start) + len("run: |\n")
        run_end = workflow.index("\n      - name:", run_start)
        return "\n".join(
                line[10:] if line.startswith("          ") else line
                for line in workflow[run_start:run_end].splitlines()
        )


def _bash_executable() -> str:
        bash_executable = shutil.which("bash") or "bash"
        if os.name == "nt":
                git_executable = shutil.which("git")
                if git_executable:
                        git_bash = Path(git_executable).parent.parent / "bin" / "bash.exe"
                        if git_bash.is_file():
                                bash_executable = str(git_bash)
        return bash_executable


def _run_peer_setup(
        tmp_path: Path,
        *,
        event_name: str,
        head_ref: str | None,
        pr_found: bool = True,
        pr_lookup_failures: int = 0,
        main_lookup_failures: int = 0,
        fetch_failures: int = 0,
        checkout_failures: int = 0,
) -> tuple[subprocess.CompletedProcess[str], list[str], str, bool]:
        calls_path = tmp_path / "git-calls.txt"
        fetched_sha_path = tmp_path / "fetched-sha.txt"
        checked_out_sha_path = tmp_path / "checked-out-sha.txt"
        summary_path = tmp_path / "summary.md"
        behavior_marker = tmp_path / "behavior-tests-ran.txt"
        environment = os.environ.copy()
        environment.update(
                {
                        "GITHUB_EVENT_NAME": event_name,
                        "GITHUB_STEP_SUMMARY": str(summary_path),
                        "PEER_REPOSITORY": PEER_REPOSITORY,
                        "GIT_CALLS_FILE": str(calls_path),
                        "FETCHED_SHA_FILE": str(fetched_sha_path),
                        "CHECKED_OUT_SHA_FILE": str(checked_out_sha_path),
                        "BEHAVIOR_MARKER": str(behavior_marker),
                        "PR_LOOKUP_REF": f"refs/heads/{head_ref}" if head_ref else "",
                        "PR_LOOKUP_SHA": PR_SHA,
                        "MAIN_LOOKUP_SHA": MAIN_SHA,
                        "PR_LOOKUP_FOUND": str(pr_found).lower(),
                        "PR_LOOKUP_FAILURES": str(pr_lookup_failures),
                        "MAIN_LOOKUP_FAILURES": str(main_lookup_failures),
                        "FETCH_FAILURES": str(fetch_failures),
                        "CHECKOUT_FAILURES": str(checkout_failures),
                }
        )
        if head_ref is not None:
                environment["GITHUB_HEAD_REF"] = head_ref
        else:
                environment.pop("GITHUB_HEAD_REF", None)

        git_stub = r"""
sleep() { :; }
git() {
    printf '%s\n' "$*" >> "$GIT_CALLS_FILE"
    if [[ "$1" == "init" ]]; then return 0; fi
    if [[ "$1" == "ls-remote" ]]; then
        ref="$3"
        if [[ -n "$PR_LOOKUP_REF" && "$ref" == "$PR_LOOKUP_REF" ]]; then
            count="$(grep -F -c -- "$ref" "$GIT_CALLS_FILE" || true)"
            if (( count <= PR_LOOKUP_FAILURES )); then return 128; fi
            if [[ "$PR_LOOKUP_FOUND" == "true" ]]; then
                printf '%s\t%s\n' "$PR_LOOKUP_SHA" "$ref"
            fi
            return 0
        fi
        if [[ "$ref" == "refs/heads/main" ]]; then
            count="$(grep -F -c -- "$ref" "$GIT_CALLS_FILE" || true)"
            if (( count <= MAIN_LOOKUP_FAILURES )); then return 128; fi
            printf '%s\t%s\n' "$MAIN_LOOKUP_SHA" "$ref"
            return 0
        fi
    fi
    if [[ "$1" == "-C" && "$3" == "fetch" ]]; then
        count="$(grep -F -c -- 'fetch --depth=1' "$GIT_CALLS_FILE" || true)"
        if (( count <= FETCH_FAILURES )); then return 128; fi
        printf '%s\n' "$6" > "$FETCHED_SHA_FILE"
        return 0
    fi
    if [[ "$1" == "-C" && "$3" == "checkout" ]]; then
        count="$(grep -F -c -- 'checkout --detach' "$GIT_CALLS_FILE" || true)"
        if (( count <= CHECKOUT_FAILURES )); then return 128; fi
        cat "$FETCHED_SHA_FILE" > "$CHECKED_OUT_SHA_FILE"
        return 0
    fi
    if [[ "$1" == "-C" && "$3" == "rev-parse" ]]; then
        cat "$CHECKED_OUT_SHA_FILE"
        return 0
    fi
    return 1
}
"""
        script = _extract_peer_setup_script()
        script += '\nprintf "ran\\n" > "$BEHAVIOR_MARKER"\n'
        result = subprocess.run(
                [_bash_executable(), "-c", f"{git_stub}\n{script}"],
                capture_output=True,
                text=True,
                env=environment,
                check=False,
        )
        calls = calls_path.read_text(encoding="utf-8").splitlines() if calls_path.exists() else []
        summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
        return result, calls, summary, behavior_marker.exists()


def test_checkout_uses_read_only_permissions_without_persisting_credentials() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    checkout_start = workflow.index("      - uses: actions/checkout@v4")
    next_step = workflow.index("\n\n      - name:", checkout_start)
    checkout_step = workflow[checkout_start:next_step]

    assert "    permissions:\n      contents: read\n" in workflow[:checkout_start]
    assert "persist-credentials: false" in checkout_step


def test_peer_contract_selects_pr_branch_or_explicit_main_fallback() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "tylerdrakemusic/AI-Manifest" in workflow
    assert "GITHUB_EVENT_NAME" in workflow
    assert "GITHUB_HEAD_REF" in workflow
    assert '"${GITHUB_HEAD_REF:-}"' in workflow
    assert '"refs/heads/${GITHUB_HEAD_REF}"' in workflow
    assert "refs/heads/main" in workflow
    assert "main (fallback: no matching peer branch" in workflow


def test_peer_setup_retries_fail_before_test_behavior_steps() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    peer_step = workflow.index("- name: Set up peer contract")
    python_step = workflow.index("- name: Set up Python")
    install_step = workflow.index("- name: Install dependencies")
    pytest_step = workflow.index("- name: Run pytest")
    peer_setup = workflow[peer_step:python_step]

    assert "git ls-remote" in peer_setup
    assert "fetch --depth=1" in peer_setup
    assert peer_setup.count("for attempt in 1 2 3") == 3
    assert 'sleep "$attempt"' in peer_setup
    assert "exit 1" in peer_setup
    assert peer_step < python_step < install_step < pytest_step


def test_peer_setup_checks_out_exact_sha_and_reports_provenance() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    peer_step = workflow.index("- name: Set up peer contract")
    python_step = workflow.index("- name: Set up Python")
    peer_setup = workflow[peer_step:python_step]

    assert '"$peer_sha"' in peer_setup
    assert "checkout --detach FETCH_HEAD" in peer_setup
    assert "rev-parse HEAD" in peer_setup
    assert "GITHUB_STEP_SUMMARY" in peer_setup
    assert "Peer repository" in peer_setup
    assert "Selected ref" in peer_setup
    assert "Checked-out SHA" in peer_setup


def test_existing_ci_lanes_and_pytest_command_remain_unchanged() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "push:" in workflow
    assert "pull_request:" in workflow
    assert "- name: Audit dependencies" in workflow
    assert "- name: Upload JUnit report" in workflow
    assert "python tools/run_tests.py --parallel --junitxml=tmp/pytest-junit.xml" in workflow


def test_pull_request_with_empty_head_ref_fails_peer_setup() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    step_start = workflow.index("- name: Set up peer contract")
    run_start = workflow.index("run: |\n", step_start) + len("run: |\n")
    run_end = workflow.index("\n      - name:", run_start)
    script = "\n".join(
        line[10:] if line.startswith("          ") else line
        for line in workflow[run_start:run_end].splitlines()
    )
    git_stub = """
git() {
  if [[ "$1" == "ls-remote" ]]; then
    printf '0123456789abcdef0123456789abcdef01234567\\trefs/heads/main\\n'
    return 0
  fi
  return 1
}
"""
    environment = os.environ.copy()
    environment.update(
        {
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_HEAD_REF": "",
            "PEER_REPOSITORY": "tylerdrakemusic/AI-Manifest",
        }
    )
    bash_executable = shutil.which("bash") or "bash"
    if os.name == "nt":
        git_executable = shutil.which("git")
        if git_executable:
            git_bash = Path(git_executable).parent.parent / "bin" / "bash.exe"
            if git_bash.is_file():
                bash_executable = str(git_bash)

    result = subprocess.run(
        [bash_executable, "-c", f"{git_stub}\n{script}"],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode != 0
    assert "GITHUB_HEAD_REF is empty for a pull request" in result.stderr


def test_pr_setup_fetches_exact_branch_sha_and_reports_provenance(tmp_path: Path) -> None:
    branch = "feature/paired-revision"
    result, calls, summary, behavior_ran = _run_peer_setup(
        tmp_path,
        event_name="pull_request",
        head_ref=branch,
    )

    assert result.returncode == 0, result.stderr
    assert f"ls-remote https://github.com/{PEER_REPOSITORY}.git refs/heads/{branch}" in calls
    assert (
        f"-C ai-manifest-contract fetch --depth=1 "
        f"https://github.com/{PEER_REPOSITORY}.git {PR_SHA}"
    ) in calls
    assert "-C ai-manifest-contract checkout --detach FETCH_HEAD" in calls
    assert "-C ai-manifest-contract rev-parse HEAD" in calls
    assert "Peer repository: tylerdrakemusic/AI-Manifest" in summary
    assert f"Selected ref: {branch}" in summary
    assert f"Checked-out SHA: {PR_SHA}" in summary
    assert not any(call.endswith("refs/heads/main") for call in calls)
    assert behavior_ran


def test_missing_pr_branch_uses_main_and_reports_fallback(tmp_path: Path) -> None:
    branch = "feature/peer-branch-absent"
    result, calls, summary, behavior_ran = _run_peer_setup(
        tmp_path,
        event_name="pull_request",
        head_ref=branch,
        pr_found=False,
    )

    assert result.returncode == 0, result.stderr
    assert f"ls-remote https://github.com/{PEER_REPOSITORY}.git refs/heads/{branch}" in calls
    assert f"ls-remote https://github.com/{PEER_REPOSITORY}.git refs/heads/main" in calls
    assert (
        f"-C ai-manifest-contract fetch --depth=1 "
        f"https://github.com/{PEER_REPOSITORY}.git {MAIN_SHA}"
    ) in calls
    assert f"Selected ref: main (fallback: no matching peer branch for {branch})" in summary
    assert f"Checked-out SHA: {MAIN_SHA}" in summary
    assert behavior_ran


def test_non_pr_setup_uses_main_and_reports_provenance(tmp_path: Path) -> None:
    result, calls, summary, behavior_ran = _run_peer_setup(
        tmp_path,
        event_name="push",
        head_ref=None,
    )

    assert result.returncode == 0, result.stderr
    assert calls.count(f"ls-remote https://github.com/{PEER_REPOSITORY}.git refs/heads/main") == 1
    assert not any("feature/" in call for call in calls)
    assert f"Peer repository: {PEER_REPOSITORY}" in summary
    assert "Selected ref: main" in summary
    assert f"Checked-out SHA: {MAIN_SHA}" in summary
    assert behavior_ran


def test_exhausted_pr_lookup_stops_after_three_attempts_before_behavior_tests(
    tmp_path: Path,
) -> None:
    branch = "feature/lookup-unavailable"
    result, calls, summary, behavior_ran = _run_peer_setup(
        tmp_path,
        event_name="pull_request",
        head_ref=branch,
        pr_lookup_failures=3,
    )

    assert result.returncode != 0
    assert result.stderr.strip().endswith("Peer branch lookup failed after 3 attempts")
    assert sum("ls-remote" in call for call in calls) == 3
    assert not any(call.endswith("refs/heads/main") for call in calls)
    assert not any(" fetch " in f" {call} " for call in calls)
    assert not summary
    assert not behavior_ran


def test_exhausted_checkout_stops_after_three_attempts_before_behavior_tests(
    tmp_path: Path,
) -> None:
    result, calls, summary, behavior_ran = _run_peer_setup(
        tmp_path,
        event_name="pull_request",
        head_ref="feature/checkout-unavailable",
        checkout_failures=3,
    )

    assert result.returncode != 0
    assert result.stderr.strip().endswith("Peer checkout failed after 3 attempts")
    assert sum(" fetch " in f" {call} " for call in calls) == 3
    assert sum(" checkout " in f" {call} " for call in calls) == 3
    assert not summary
    assert not behavior_ran