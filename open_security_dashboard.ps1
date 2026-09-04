# ⊕ Security Dashboard Launcher
# Generates the DB-backed dashboard, then opens it.
# Double-click this file (or run from PowerShell) — no manual steps required.

$ErrorActionPreference = "Stop"
$Python = "C:\G\python.exe"
$DashboardScript = "f:\⊕Workspace\tools\security_dashboard.py"
$Dashboard  = "f:\⊕Workspace\reports\security_dashboard.html"

Write-Host "⊕ Generating security dashboard..." -ForegroundColor Cyan
& $Python $DashboardScript --no-open
if ($LASTEXITCODE -ne 0) {
    Write-Host "Dashboard generation failed (exit $LASTEXITCODE). Opening last known dashboard." -ForegroundColor Yellow
}

Write-Host "⊕ Opening dashboard..." -ForegroundColor Cyan
Start-Process $Dashboard
