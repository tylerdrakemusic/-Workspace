# ⊕ Security Dashboard Launcher
# Runs a fresh security scan then opens the regenerated dashboard.
# Double-click this file (or run from PowerShell) — no manual steps required.

$ErrorActionPreference = "Stop"
$Python = "C:\G\python.exe"
$ScanScript = "f:\⊕Workspace\src\utils\security_scan.py"
$Dashboard  = "f:\⊕Workspace\reports\security_dashboard.html"

Write-Host "⊕ Running security scan..." -ForegroundColor Cyan
& $Python $ScanScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "Scan failed (exit $LASTEXITCODE). Opening last known dashboard." -ForegroundColor Yellow
}

Write-Host "⊕ Opening dashboard..." -ForegroundColor Cyan
Start-Process $Dashboard
