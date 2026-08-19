# FR-20260815 Shared Python Dependency Remediation

## Result

The authorized maintenance window was used to verify the Workspace-owned dependency fixes. No additional package upgrade was safe to make: every remaining pip-audit finding belongs to an external or unrelated package in the shared interpreter, and changing those packages would require cross-project behavior decisions.

- Audit date: 2026-08-18
- Audit command: `python tools/audit_workspace_requirements.py requirements.txt` (strict audit of exact installed versions for Workspace-declared packages)
- Baseline: 386 findings across 72 affected packages
- Current: 356 findings across 68 affected packages
- Change: 30 fewer findings across 4 fewer affected packages
- Broad shared-interpreter audit exit code: 1 because external residual findings remain; the scoped Workspace-declared audit is the CI gate.
- Workspace-declared residual findings: 0
- Workspace runtime dependency residual findings: 0
- External/unrelated residual packages: 68
- Separate Windows manifest resolution: unable to install `sqlcipher3-binary==0.6.0` into a temporary resolver environment; the shared interpreter exposes the compatible SQLCipher wheel under alternate distribution metadata. The scoped audit pins the installed version without dependency resolution, while fresh CI installation validates the declared requirement on Ubuntu.
- On this Windows interpreter, `pip-audit --no-deps --disable-pip` reports the substituted SQLCipher wheel as unauditable because its distribution name is not present on PyPI; this is recorded as a tooling/package-index limitation, not suppressed as a clean vulnerability result.

## Verified Direct Fixes

| Package | Verified version | Current findings |
|---|---:|---:|
| `mcp` | 1.28.1 | 0 |
| `python-dotenv` | 1.2.2 | 0 |
| `pytest` | 9.0.3 | 0 |
| `Pillow` | 12.3.0 | 0 |

`httpx` and the remaining Workspace runtime imports also passed the focused import check. No services were restarted.

`pytest-asyncio` was upgraded in the shared interpreter to preserve compatibility after the `pytest` upgrade, but it is not declared by this Workspace manifest and is therefore excluded from the Workspace direct-fix table and ownership classification.

## Residual Classification

The complete redacted package/version/finding list is in `FR-20260815-shared-python-dependency-remediation-classification.json`. Residual findings are classified `external/unrelated`; the highest-count packages are `aiohttp` (35), `gradio` (33), `mistune` (26), `keras` (21), `gitpython` (19), `nltk` (19), `tornado` (15), and `pypdf` (15).

No bulk `pip-audit --fix` was used. No findings were suppressed. No unrelated project manifests were changed.

## Compatibility Checks and Blockers

- Direct import check passed for `mcp`, `dotenv`, `pytest`, `PIL`, and `httpx`.
- `pip check` remains non-zero on pre-existing shared-interpreter conflicts, including `audiocraft`, `awscli`, `fastapi`/`starlette`, `gradio`/`Pillow`, Quantum packages, TensorFlow, and other external stacks.
- Those conflicts are outside Workspace ownership and cannot be resolved package-by-package without cross-project behavior decisions.
- A direct `pip-audit -r requirements.txt` run on Windows exits during temporary-environment installation because `sqlcipher3-binary==0.6.0` has no compatible index distribution for that platform. It does not produce a vulnerability result for the declared Workspace requirements; the installed-environment audit above is the canonical supported audit for this shared interpreter.
- Broader Workspace pytest suite passed: `763 passed, 13 skipped, 11 deselected`; two pre-existing deprecation warnings were emitted. Services remain stopped.

## Redaction

This report records package names, versions, counts, classifications, test results, and exit status only. Advisory descriptions, credentials, DB keys, financial data, health data, and filesystem paths are excluded.
