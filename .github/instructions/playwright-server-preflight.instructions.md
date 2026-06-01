---
description: "Playwright server pre-flight protocol. MANDATORY before any mcp_playwright_browser_navigate or pytest -m playwright call. Covers kill-by-port, server start, health-check loop (hard-fail on timeout), and teardown in finally block."
applyTo: ".github/agents/*.agent.md"
---

# Playwright Server Pre-flight Protocol

**MANDATORY.** Execute this protocol immediately before every Playwright invocation — both
`mcp_playwright_browser_*` tool calls and `pytest -m playwright` runs. No exceptions.

---

## Step 0 — Read the server manifest

Identify the project under test from the FR scope, then read the manifest to get the server
configuration:

```powershell
$manifestRaw = Get-Content -LiteralPath "f:\⊕Workspace\src\config\playwright_servers.json" -Raw
$manifest    = $manifestRaw | ConvertFrom-Json
$config      = $manifest.projects."<ProjectName>"   # e.g. "❤Music", "⊕Workspace"
```

If `$config.type -eq "static_file"`: **skip Steps 1–3 and 5**. Navigate Playwright directly to
`file:///` + `$config.file_path`. No server process to manage.

---

## Step 1 — Kill existing process on the port

```powershell
$port     = $config.port
$existing = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
if ($existing) {
    Stop-Process -Id $existing.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    Write-Host "Pre-flight: killed stale process on :$port"
}
```

---

## Step 2 — Start server

Set required environment variables from `$config.env`, then launch the process in the
background:

```powershell
# Apply env vars
foreach ($key in $config.env.PSObject.Properties.Name) {
    [System.Environment]::SetEnvironmentVariable($key, $config.env.$key, "Process")
}

$args      = $config.cmd[1..($config.cmd.Count - 1)]
$proc      = Start-Process -FilePath $config.cmd[0] `
                 -ArgumentList $args `
                 -WorkingDirectory $config.cwd `
                 -WindowStyle Hidden `
                 -PassThru
$serverPid = $proc.Id
Write-Host "Pre-flight: started server PID $serverPid on :$($config.port)"
```

---

## Step 3 — Health-check loop (max 10 s) — HARD FAIL on timeout

```powershell
$healthUrl = $config.health_url
$deadline  = (Get-Date).AddSeconds($config.health_timeout_s)
$up        = $false

while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $up = $true; break }
    } catch { }
    Start-Sleep -Milliseconds 500
}

if (-not $up) {
    Stop-Process -Id $serverPid -Force -ErrorAction SilentlyContinue
    $msg = "Playwright pre-flight FAILED: $($config.server_label) on :$($config.port) " +
           "did not return HTTP 200 within $($config.health_timeout_s)s. " +
           "Check server logs. Aborting Playwright."
    Write-Host "ERROR: $msg"
    throw $msg   # Hard-fail — do NOT proceed to Playwright
}

Write-Host "Pre-flight: server healthy at $healthUrl"
```

**Hard fail rule:** if the health check times out, stop the process, throw an error, and report
the FR criterion as **QA FAIL**. Do not proceed to Playwright. Surface the error message and
any available server output in the QA report.

---

## Step 4 — Run Playwright (inside a try/finally)

Wrap the Playwright invocation so teardown always runs:

```powershell
try {
    $env:PYTHONUTF8        = "1"
    $env:PLAYWRIGHT_ENABLED = "1"
    C:\G\python.exe -m pytest <project>/tests/ -m playwright -v 2>&1
} finally {
    # Step 5 — Teardown
    Stop-Process -Id $serverPid -Force -ErrorAction SilentlyContinue
    Write-Host "Pre-flight teardown: killed server PID $serverPid"
}
```

For direct `mcp_playwright_browser_*` calls (no pytest), wrap the tool-call sequence the same
way: record `$serverPid`, call tools, then kill in the logical "finally" step after the last
browser call.

---

## Step 5 — Teardown

Always kill the server after Playwright exits, whether the tests pass or fail. The `finally`
block in Step 4 handles this. No zombie processes.

---

## Quick Reference

| Step | Action | Hard fail? |
|------|--------|-----------|
| 0 | Read `playwright_servers.json`; detect `static_file` | — |
| 1 | Kill existing process on port | No |
| 2 | Start server with env vars from manifest | No |
| 3 | Poll `health_url` until HTTP 200 (max `health_timeout_s`) | **YES — abort + report QA FAIL** |
| 4 | Run Playwright inside `try` block | — |
| 5 | Kill server in `finally` block (always) | No |

---

## Common Mistakes (what this protocol fixes)

- Spinning up Playwright against a stale or crashed server from a previous session
- Forgetting to set `PYTHONPATH` or DB key env vars before starting the server
- Leaving server processes running after a test failure (port conflicts next run)
- Skipping the health-check and getting false-negative "page not found" Playwright failures
