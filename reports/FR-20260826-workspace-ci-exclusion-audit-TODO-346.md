# FR-20260826-workspace-ci-exclusion-audit, TODO 346 baseline

This inventory records the six canonical repositories and the CI exclusion
surfaces that remediation addresses. Counts are collection observations from
the audit baseline; remediation regression tests may change later totals.

| Repository | Location | Classification | Reason | Count | Workflow impact | Substitute coverage |
| --- | --- | --- | ---: | --- | --- | --- |
| ∞Life | `pytest.ini`, dashboard tests | Conditional skip | Generated dashboard and browser resources are unavailable in ordinary CI. | 2 | Full pytest remains failure-blocking and reports skip reasons. | Non-browser dashboard logic tests. |
| ❤Music | `tests/`, `pytest.ini` | Conditional skip | Generated panels, local services, optional media, and credentials may be unavailable. | 31 static skip sites | Full pytest remains failure-blocking and reports skip reasons. | Unit and error-path coverage. |
| ⟨ψ⟩Quantum | `pytest.ini`, VQE tests | Explicit bounded exclusion | One LiH optimization is classified `ci_long_running`; it remains runnable outside canonical CI. | 1 | CI verifies the exact identity, reason, and count, then keeps other failures blocking. | Fast VQE coverage and explicit local rerun marker. |
| 👁AI-Manifest | `pytest.ini`, backup tests | Explicit marked exclusion and conditional skip | Playwright/live infrastructure is unavailable in ordinary CI; the backup contract is exported by workflow. | 25 deselected, 4 skip sites | CI reports collection and skip reasons; failures remain blocking. | Backup and provider contract tests. |
| ΣCapital | `pytest.ini`, integration tests | Explicit integration deselection | Four integration tests require live services or credentials unavailable in ordinary CI. | 4 | CI verifies exactly four identities separately; runnable failures remain blocking. | Unit and runtime validation coverage. |
| ⊕Workspace | `pytest.ini`, integration tests | Conditional skip and explicit integration collection | External API and local integration prerequisites may be unavailable. | 11 integration tests | CI collects integration tests and reports skip reasons; failures remain blocking. | Unit and contract coverage. |

No parent state transition or completion claim is made by this inventory.# FR-20260826-workspace-ci-exclusion-audit, TODO 346 baseline

## Scope and method

This is an inventory only. It covers the canonical roots `f:\∞Life`, `f:\❤Music`, `f:\⟨ψ⟩Quantum`, `f:\👁AI-Manifest`, `f:\ΣCapital`, and `f:\⊕Workspace`. The audit read each root's `.github/workflows` files, pytest configuration, root `conftest.py` where present, and tests. Collection was measured with the repository's configured pytest options and with `-o addopts=` to expose configuration-level deselection. Workflow-targeted collection was measured for workflows that name specific test files.

No project CI remediation was performed. No worktree or external repository content was counted. No PR or parent TODO completion is claimed.

## Baseline matrix

| Repository | Location | Classification | Reason | Count | Workflow impact | Substitute coverage |
| --- | --- | --- | ---: | --- | --- |
| ∞Life | `pytest.ini:addopts`; `tests/test_dashboard_playwright.py` | Conditional skip, environment/generated-artifact dependent | Two tests use `skipif` when dashboard HTML is absent. The file is marked Playwright, but the workflow only sets `PLAYWRIGHT_ENABLED=0`; no xfail or collection filter was found. | 2 conditional tests; 210 items collected | `.github/workflows/test.yml` runs the full 210-item suite and remains failure-blocking. | Non-browser tests cover the dashboard logic; generated HTML and browser behavior have no CI substitute in this workflow. |
| ∞Life | `.github/workflows/test.yml` | No workflow exclusion or non-blocking step found | Push and pull request triggers target `main`; pytest runs without `continue-on-error`, path filters, explicit deselection, or an allow-failure wrapper. | 0 workflow exclusions | Full pytest invocation. | None needed for the workflow gate. |
| ❤Music | `tests/`; `pytest.ini`; `.github/workflows/test.yml` | Conditional skips and runtime skips | 14 `skipif` occurrences and 17 `pytest.skip` occurrences cover missing generated panels, unavailable DB/audio assets, absent keys, and local server startup failures. No xfail or pytest collection filter was found. | 858 items collected; 31 static skip sites | The main test workflow runs all 858 collected items; runtime skips can reduce executed coverage without a CI summary of reasons. | Unit and error-path tests cover many unavailable-service branches; generated panels, local servers, keyed DB access, and optional media remain uncovered when absent. |
| ❤Music | `.github/workflows/deploy-hyperthreat-studio.yml` | Explicit workflow target filter | The deploy test job runs only `tests/test_hyperthreat_studio_app.py`, not the repository suite. | 6 targeted items | The deploy gate validates 6 tests. Its path-filtered push trigger runs only for selected deployment files; manual dispatch is available. | The general `test.yml` suite is the substitute for repository-wide coverage, but it is not a dependency of this deploy workflow. |
| ⟨ψ⟩Quantum | `pytest.ini:addopts` | Configured deselection | `-m "not slow"` excludes tests marked `slow` by default. The config documents explicit local re-selection with `-m slow`. | 13 deselected of 173; 160 selected | `.github/workflows/test.yml` inherits the filter, so 13 slow items do not run in CI. | Fast tests cover the normal suite; no dedicated slow-test CI job was found in the canonical workflows. |
| ⟨ψ⟩Quantum | `tests/test_benchmark_dashboard_playwright.py`; `tests/test_bfx_orion_portal_server.py` | Conditional skips | Three `skipif` sites guard generated dashboard or unavailable Workspace-dependent infrastructure. The Playwright module is opt-in by marker. | 3 conditional sites | Full workflow collection reports 173 items with 13 config-deselected; conditional skips occur at execution when prerequisites are absent. | Non-browser tests cover benchmark and server logic; generated dashboard and external Workspace server paths lack an always-on substitute. |
| 👁AI-Manifest | `pytest.ini:addopts`; `tests/`; root `conftest.py` | Configured integration deselection plus runtime skips and collection blocker | `-m "not integration"` is configured, although no integration marker was found in the scanned tests. Four runtime skips cover missing SDK, generated portal, and absent ElevenLabs key. Collection fails in `tests/test_database_backup.py` unless `WORKSPACE_ROOT` or `WORKSPACE_BACKUP_ENGINE_PATH` is configured. | 252 items collected; 4 runtime skip sites; 1 collection error | `.github/workflows/test.yml` invokes the full suite, so the missing Workspace contract blocks collection before a reliable pass/fail result. | Local contract tests and provider error-path tests exist; the backup contract requires the workflow's Workspace checkout/environment to be made explicit before coverage is trustworthy. |
| ΣCapital | `pytest.ini:addopts`; `tests/` | Configured integration deselection and runtime skips | `-m "not integration"` excludes integration tests. Six runtime skip sites and one `skipif` cover missing keys, simulated UI prerequisites, and unavailable external services. | 704 collected; 4 deselected; 2 skipped; 700 selected | `.github/workflows/test.yml` does not run the configured suite. It names 3 files and collects 15 tests, leaving 689 of the 704-item baseline outside this workflow's gate. | The 15 named regression tests cover backup, inventory, and runtime validation only; the remaining unit, API, trade, risk, and UI coverage has no workflow substitute in this file. |
| ⊕Workspace | `pytest.ini:addopts`; `tests/` | Configured integration deselection, optional dependency skips, and runtime skips | `-m "not integration"` excludes integration tests. Two `importorskip` sites and 18 `pytest.skip` sites cover missing optional packages, generated portals, local services, private cross-project checkouts, and absent keys. | 939 collected; 11 deselected; 928 selected; 20 static skip sites | `.github/workflows/test.yml` inherits the integration filter and runs the full configured suite; no xfail or `continue-on-error` was found. | Unit and contract tests cover most service error paths; browser, generated-artifact, private-checkout, and external API paths remain conditional. |

## Cross-cutting findings

- No `xfail` usage was found in the scanned test/config surfaces for any of the six repositories.
- No `continue-on-error` setting was found in the canonical workflow files.
- No pytest `--deselect`, `--ignore`, `collect_ignore`, or `collect_ignore_glob` setting was found in the canonical configurations. The observed collection filters are marker expressions in Quantum, AI-Manifest, ΣCapital, and ⊕Workspace.
- Workflow-level equivalent suppression is present in the Music deploy workflow's explicit six-test target and ΣCapital's explicit three-file target. Music also has a path-filtered deployment trigger.
- Playwright is consistently opt-in or prerequisite-gated. The workflow environment sets `PLAYWRIGHT_ENABLED=0` in ∞Life, ❤Music, ⟨ψ⟩Quantum, and ⊕Workspace, but the scanned roots do not all implement the marker hook in the same place; this should be normalized during remediation, not in this inventory child.
- The primary unambiguous blocking issue is the 👁AI-Manifest collection error. The primary silent-coverage risks are ΣCapital's 15-test workflow target, the configured marker deselections, and runtime skips whose counts are not surfaced by the workflows.

## Validation record

Configured collection observations:

| Repository | Configured collection result | Unfiltered collection result |
| --- | --- | --- |
| ∞Life | 210 items | 210 items |
| ❤Music | 858 items | 858 items |
| ⟨ψ⟩Quantum | 160 selected, 13 deselected | 173 items |
| 👁AI-Manifest | 252 items with 1 collection error | 252 items with the same collection error |
| ΣCapital | 700 selected, 4 deselected, 2 skipped | 704 items |
| ⊕Workspace | 928 selected, 11 deselected | 939 items |

Workflow-targeted collection: Music deploy `test_hyperthreat_studio_app.py` collected 6 items; ΣCapital's three named files collected 15 items.

The companion contract test is `tests/test_ci_exclusion_inventory.py`. This artifact is a baseline for the six remediation children and does not modify their CI behavior.