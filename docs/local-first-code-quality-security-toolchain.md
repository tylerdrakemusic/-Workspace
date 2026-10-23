# Local-First Code Quality and Security Toolchain

**Research:** FR-20261020-new-fr-aidlc-all-projects, child TODO 1013
**Date:** 2026-10-21
**Status:** Recommendation only. No scanners installed, invoked, or configured by this research.

## Recommendation

Adopt one shared workflow and report contract with small language-specific adapters. Keep the existing project test commands as the required merge gate. Introduce code-quality and security scanners in advisory mode first; do not auto-fix, write findings to production databases, or add a paid service by default.

For Python, pilot Ruff for lint/format checks, gradual mypy type checking, Bandit for source-level security patterns, and pip-audit for known dependency advisories. Workspace already declares Bandit and pip-audit; its CI runs a custom `audit_workspace_requirements.py` that audits exact installed package versions. Preserve and assess that implementation before duplicating it. Ruff and mypy are candidates, not adopted dependencies.

For the `∞Life/workout` npm project, use its existing `package-lock.json` as the audit input and consider ESLint only if the JavaScript source warrants it. `npm audit` contacts the configured registry and sends dependency names and versions, so enabling it for private-project data needs a privacy review and explicit approval under this FR's hosted-scanning rule.

For local secret detection, pilot a pinned Gitleaks binary on changed Git history and tracked files, with redacted output and a reviewed baseline. Gitleaks supports local Git/directory scans and JSON/SARIF reports, but its maintainers describe it as feature-complete with future releases limited to security fixes. Treat that maintenance posture as a pilot risk and compare its successor before standardizing. `detect-secrets` offers baselines and staged-file hooks, but its upstream repository's latest release is old; do not select it without confirming current maintenance. [Gitleaks](https://github.com/gitleaks/gitleaks), [detect-secrets](https://github.com/Yelp/detect-secrets)

Do not use Safety CLI or hosted Semgrep/GitHub scanning as the default private-repository path. Safety's current CLI documentation describes authenticated scans whose results are sent to Safety Platform. Semgrep's local `scan` can run without an account, but registry-backed `--config auto` uses the project URL and may send usage metrics; authenticated `ci` sends findings to Semgrep's service. GitHub CodeQL/secret-scanning features for private repositories require GitHub Advanced Security products. Any hosted scan of private source or dependency inventory requires explicit per-service approval; paid services also require separate budget approval. [Safety CLI](https://docs.safetycli.com/safety-docs/safety-cli/introduction-to-safety-cli-vulnerability-scanning.md), [Semgrep CLI](https://docs.semgrep.dev/cli-usage/), [GitHub Advanced Security](https://docs.github.com/en/get-started/learning-about-github/about-github-advanced-security)

## Current Fit

- All six delivery paths use Python and pytest; the project CI implementations differ in Python version, runner OS, peer-repository setup, package validation, and pytest execution. The shared layer should standardize reporting and policy, not replace project-specific CI commands.
- Workspace already lists `pip-audit`, Bandit, Safety, and Radon. CI runs `pip-audit` through `tools/audit_workspace_requirements.py`, which converts installed direct requirements to exact versions and audits those versions. No equivalent scanner step was found in the other project workflows.
- Most Python dependency declarations are range-based `requirements.txt` files rather than committed lockfiles. The Quantum repo has `pyproject.toml`; the `∞Life/workout` npm project has `package-lock.json`. Audit the actual CI-resolved environment where no lock exists, and record that the result covers known advisories, not malicious packages or source-code flaws.
- Workspace's `agent_feedback` records findings about agent/instruction/prompt/skill/reference artifacts and only supports trivial/substantive severity plus feedback workflow statuses. `tech_debt` is limited to complexity, monolith, coupling, and filesystem categories. Neither is a general scanner-results store.
- Workspace also has `vulnerabilities` and `scan_run_log` tables, currently consumed by the security dashboard's custom OWASP-pattern scanner. The schema can represent basic path/line findings and Bandit/Safety run exit codes, but lacks general scanner identity/version, rule/fingerprint, dependency coordinates, advisory ID, configuration revision, and suppression provenance. Do not write new tool findings into these tables or migrate them in this research child; assess a follow-up ingestion contract first.

## Tool Matrix

| Area | Candidate and coverage | Setup/runtime | CI and privacy | False-positive handling |
|---|---|---|---|---|
| Python lint/format | Ruff combines common lint, import, modernization, and formatting tasks. It is not a complete security scanner. | Single cross-platform Python tool; designed for fast repeated local checks. | Can run locally and in existing pytest workflows; no source-hosting service required for direct CLI use. | Start with explicit conservative rule groups; do not enable all rules or auto-apply unsafe fixes. Review per-file exceptions. [Ruff](https://docs.astral.sh/ruff/), [rule selection](https://docs.astral.sh/ruff/linter/#rule-selection) |
| Python types | Mypy checks annotated Python incrementally and supports gradual adoption. | Local Python tool; runtime scales with checked modules and import graph. | Fits current Python projects and CI. No hosted service required. | Start with selected shared modules, baseline existing errors, and tighten per module; avoid a workspace-wide strict gate before measuring noise. [Mypy: existing code](https://mypy.readthedocs.io/en/stable/existing_code.html) |
| Python source security | Bandit parses Python ASTs and applies security plugins; already declared in Workspace. | Local CLI, relatively narrow setup. | Can run offline on source and integrate with current CI. | Triage context-specific findings; require rule-specific suppression with rationale. It does not replace review or dependency auditing. [Bandit](https://bandit.readthedocs.io/en/latest/) |
| Python dependencies | pip-audit checks known vulnerability advisories for Python environments/requirements and supports JSON, Markdown, and CycloneDX output. | Local process, but advisory lookup is network-backed; dependency resolution can dominate runtime if requirements are not pinned. | Workspace already uses it against installed exact package versions. It checks dependency advisories, not source or malicious packages. [pip-audit](https://github.com/pypa/pip-audit) |
| Secrets | Gitleaks scans local Git history, directories, and files; supports baselines, redaction, JSON and SARIF. | Standalone pinned binary; no Python/Node runtime dependency. | Keep invocation local or in self-hosted CI. Do not enable validity checks or hosted actions for private repos without approval. | Redact output; baseline only reviewed pre-existing findings; suppress by fingerprint with a reason, never a broad path allowlist. Maintenance is security-fixes-only per upstream. [Gitleaks](https://github.com/gitleaks/gitleaks) |
| JavaScript dependencies | `npm audit` checks the lockfile's dependency tree against the configured registry. | No extra scanner package when npm is already used; requires network access. | Sends package names and versions to the configured registry. Treat private dependency inventory as an external disclosure and require service approval before enabling for private repos. [npm audit](https://docs.npmjs.com/cli/v10/commands/npm-audit) |
| Broader SAST | Semgrep `scan` can run locally with explicit rules; registry-backed `auto` and authenticated `ci` have additional network/metrics or findings-upload behavior. | Additional CLI and rule management; runtime depends on rules and target size. | Optional pilot only with reviewed, pinned local rule packs and metrics disabled. Never run authenticated hosted scans over private source without per-service approval. | Start in advisory mode; baseline by rule/fingerprint and review each exception. [Semgrep CLI](https://docs.semgrep.dev/cli-usage/) |
| Hosted GitHub analysis | CodeQL and GitHub secret scanning can provide central alerts; public-repo availability differs from private-repo licensing. | Low workflow setup, but hosted execution and alert lifecycle are GitHub-managed. | Private-repo use requires GitHub Advanced Security products; not part of the no-spend baseline. [GitHub Advanced Security](https://docs.github.com/en/get-started/learning-about-github/about-github-advanced-security) |
| Existing Safety CLI | Workspace already declares `safety`; the current product documentation describes authenticated scanning and Safety Platform result uploads. | Requires account/auth and network. | Hosted data path and plan terms need review; do not assume the existing package declaration authorizes scanning private project inventories. | Keep out of the default scanner path until account, data flow, licensing, and cost are explicitly approved. [Safety CLI](https://docs.safetycli.com/safety-docs/safety-cli/introduction-to-safety-cli-vulnerability-scanning.md), [result handling](https://docs.safetycli.com/safety-docs/safety-cli/scanning-for-vulnerable-and-malicious-packages/viewing-scan-results.md) |

## Shared Workflow Contract

1. Invoke one repo-local runner from the existing test workflow; select adapters by project language and existing dependency/lock inputs. Do not add cross-repository runtime imports.
2. Run fast local checks first: Ruff and targeted mypy, followed by pytest. Run Bandit, local secret scanning, and dependency audits as separate named steps so a failure identifies its source.
3. Emit a concise summary plus per-tool JSON/SARIF artifacts where supported. Include repository, commit SHA, tool/version, configuration revision, scan scope, elapsed time, finding counts, and whether results are local-only or hosted. Redact secret values from all output.
4. Treat scanner findings as advisory during rollout. Do not auto-upgrade dependencies or change FR/TODO state from a scanner result. Route findings for human review; record an exception against a specific rule/fingerprint with rationale, owner, and review date.
5. Measure runtime and false-positive rate on representative repositories before making any scanner a required merge gate. Existing tests and repository-specific safeguards remain the only required gates until a separately approved change promotes a scanner.
6. Do not persist general scanner findings to `agent_feedback` or `tech_debt`. Revisit the existing `vulnerabilities` and `scan_run_log` contracts in a separate approved schema/ingestion task if durable cross-run tracking is needed.

## Rollout

1. Pilot the shared report format and fast Python checks in Workspace only; keep output advisory and record duration/findings without uploading source.
2. Add language adapters and validate the local-only report contract in staged project groups. Use each repo's established runner, Python version, and OS constraints; retain normal pytest as the merge gate.
3. Test local secret scanning against synthetic fixtures and existing reviewed baselines. Never include live health, financial, API, or customer credentials in fixtures or reports.
4. Evaluate a local Semgrep rule pack only after documenting rule provenance, metrics configuration, runtime, and privacy behavior. Evaluate hosted GitHub, Semgrep, Safety, or other services separately with explicit per-service and budget approval where applicable.
5. Consider hard-gating only after an approved policy change, demonstrated low-noise baseline, documented false-positive process, and measured CI runtime impact.

## Sources

- [Ruff documentation](https://docs.astral.sh/ruff/) and [linter/rule selection](https://docs.astral.sh/ruff/linter/)
- [mypy gradual adoption for existing code](https://mypy.readthedocs.io/en/stable/existing_code.html)
- [Bandit documentation](https://bandit.readthedocs.io/en/latest/)
- [PyPA pip-audit source and security model](https://github.com/pypa/pip-audit)
- [Gitleaks documentation and maintenance notice](https://github.com/gitleaks/gitleaks)
- [Yelp detect-secrets documentation](https://github.com/Yelp/detect-secrets)
- [Semgrep CLI documentation](https://docs.semgrep.dev/cli-usage/)
- [npm audit documentation](https://docs.npmjs.com/cli/v10/commands/npm-audit)
- [GitHub Advanced Security availability](https://docs.github.com/en/get-started/learning-about-github/about-github-advanced-security)
- [GitHub CodeQL overview](https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql)
- [GitHub secret scanning](https://docs.github.com/en/code-security/concepts/secret-security/secret-scanning)
- [Safety CLI](https://docs.safetycli.com/safety-docs/safety-cli/introduction-to-safety-cli-vulnerability-scanning.md)
