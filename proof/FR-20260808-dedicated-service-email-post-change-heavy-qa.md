# FR-20260808-dedicated-service-email Post-Change Heavy QA

Date: 2026-08-08
Agent: ⊕workspace-qa-heavy
Worktree: `f:\⊕Workspace\.worktrees\FR-20260808-dedicated-service-email`
Decision: PASS

## Scope Validated

- Updated operator-gated outbound policy for the Gmail dedicated service-email capability.
- OAuth bootstrap helper remains local-only, human-run, secret-free in stdout/repo writes, and scoped to existing Gmail readonly + send scopes.
- No live Gmail credentials were used. Before pytest runs, these env vars were cleared in-process: `GMAIL_SERVICE_TOKEN`, `GMAIL_SERVICE_ADDRESS`, `GMAIL_OAUTH_CLIENT_ID`, `GMAIL_OAUTH_CLIENT_SECRET`.
- No live Gmail access or mail sending was performed; all Gmail/OAuth seams in the focused tests are mocked.

## Diff Scope Checked

`git diff --name-only` showed only:

- `AGENT_STARTUP.md`
- `src/config/service_email_capability.json`
- `src/config/service_email_policy.json`
- `src/integrations/gmail/__init__.py`
- `src/integrations/gmail/client.py`
- `tests/test_gmail_service_email.py`

Diff stat: 6 files changed, 235 insertions, 42 deletions.

## Acceptance Checks

- Draft creation is local/no Gmail call: covered by `test_create_draft_returns_typed_draft_without_api_call`.
- Outbound default remains disabled: covered by `test_default_policy_has_secure_defaults`, `service_email_policy.json`, and `test_send_message_blocked_by_default_policy`.
- False/missing/non-True approval cannot send: covered by `test_send_message_without_approval_does_not_send`, `test_send_draft_without_approval_raises_and_makes_no_api_call`, `test_send_draft_rejects_false_approval`, and `test_send_draft_rejects_non_true_truthy_approval`.
- Explicit `True` approval sends through the mocked Gmail API: covered by `test_send_message_with_approval_calls_api_once` and `test_send_draft_with_approval_sends_once`.
- Recipient and header validation still hold: covered by `test_guard_outbound_rejects_invalid_recipient`, `test_guard_outbound_rejects_header_injection`, `test_create_draft_rejects_invalid_recipient`, and `test_create_draft_rejects_header_injection`.
- `connectivity_test` requires explicit operator approval: covered by `test_connectivity_test_requires_runtime_recipient`, `test_connectivity_test_without_approval_does_not_send`, and `test_connectivity_test_read_write_roundtrip`.
- Inbound read remains functional: covered by `test_list_messages_applies_content_policy` and the connectivity read-back path.
- OAuth bootstrap remains secret-free and correctly scoped: covered by `tests/test_gmail_oauth_bootstrap.py`, including scope equality with `ALL_SCOPES`, lazy Google imports, no token stdout disclosure, and mocked env/clipboard emission.

## Commands Run

```powershell
Set-Location 'F:\⊕Workspace'
$env:PYTHONUTF8='1'
& 'C:\G\python.exe' 'src\utils\fr_cli.py' get 'FR-20260808-dedicated-service-email'
```

Result: ledger read from authoritative main workspace registry. State before QA: `BRANCH_CHECKED_OUT`; PR: `https://github.com/tylerdrakemusic/-Workspace/pull/266`.

```powershell
Set-Location 'F:\⊕Workspace\.worktrees\FR-20260808-dedicated-service-email'
$env:PYTHONUTF8='1'
Remove-Item Env:\GMAIL_SERVICE_TOKEN -ErrorAction SilentlyContinue
Remove-Item Env:\GMAIL_SERVICE_ADDRESS -ErrorAction SilentlyContinue
Remove-Item Env:\GMAIL_OAUTH_CLIENT_ID -ErrorAction SilentlyContinue
Remove-Item Env:\GMAIL_OAUTH_CLIENT_SECRET -ErrorAction SilentlyContinue
& 'C:\G\python.exe' -m pytest tests\test_gmail_service_email.py tests\test_gmail_oauth_bootstrap.py -q
```

Result: `51 passed in 0.30s`.

```powershell
Set-Location 'F:\⊕Workspace\.worktrees\FR-20260808-dedicated-service-email'
$env:PYTHONUTF8='1'
Remove-Item Env:\GMAIL_SERVICE_TOKEN -ErrorAction SilentlyContinue
Remove-Item Env:\GMAIL_SERVICE_ADDRESS -ErrorAction SilentlyContinue
Remove-Item Env:\GMAIL_OAUTH_CLIENT_ID -ErrorAction SilentlyContinue
Remove-Item Env:\GMAIL_OAUTH_CLIENT_SECRET -ErrorAction SilentlyContinue
& 'C:\G\python.exe' -m pytest -m "not integration and not playwright" -q
```

Result: `2 failed, 610 passed, 12 skipped, 17 deselected`. The two failures were pre-existing/unrelated portal iframe assertions in `tests/test_portal_icon.py`:

- `test_portal_html_has_music_server_iframes`
- `test_portal_html_has_fr_and_brief_servers`

```powershell
Set-Location 'F:\⊕Workspace\.worktrees\FR-20260808-dedicated-service-email'
$env:PYTHONUTF8='1'
Remove-Item Env:\GMAIL_SERVICE_TOKEN -ErrorAction SilentlyContinue
Remove-Item Env:\GMAIL_SERVICE_ADDRESS -ErrorAction SilentlyContinue
Remove-Item Env:\GMAIL_OAUTH_CLIENT_ID -ErrorAction SilentlyContinue
Remove-Item Env:\GMAIL_OAUTH_CLIENT_SECRET -ErrorAction SilentlyContinue
& 'C:\G\python.exe' -m pytest -m "not integration and not playwright" --deselect tests/test_portal_icon.py::test_portal_html_has_music_server_iframes --deselect tests/test_portal_icon.py::test_portal_html_has_fr_and_brief_servers -q
```

Result: `610 passed, 12 skipped, 19 deselected in 46.85s`.

```powershell
Set-Location 'F:\⊕Workspace\.worktrees\FR-20260808-dedicated-service-email'
$env:PYTHONUTF8='1'
& 'C:\G\python.exe' -m ruff check src\integrations\gmail tests\test_gmail_service_email.py tests\test_gmail_oauth_bootstrap.py tools\gmail_oauth_bootstrap.py
```

Result: `All checks passed!`

```powershell
Set-Location 'F:\⊕Workspace\.worktrees\FR-20260808-dedicated-service-email'
$env:PYTHONUTF8='1'
& 'C:\G\python.exe' -m bandit -q -r src\integrations\gmail tools\gmail_oauth_bootstrap.py
```

Result: no Bandit findings. Bandit emitted warnings about explanatory `# nosec ...` comment text tokens, but returned no security failures.

## Residual Risk

- Broader regression still contains the known unrelated portal iframe failures. They are outside this FR diff and were already recorded as pre-existing in earlier FR notes.
- Live Gmail delivery was intentionally not tested in this QA pass per operator instruction. The approved-send path was verified only through mocks.