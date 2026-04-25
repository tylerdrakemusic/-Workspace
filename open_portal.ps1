# ∞Life Portal Launcher
# Regenerates the Biomarker Dashboard, starts the ∞Life HTTP server on port 9999,
# then opens the workspace portal. Double-click from desktop — no manual steps.

$ErrorActionPreference = "SilentlyContinue"
$Python      = "C:\G\python.exe"
$DashScript  = "f:\∞Life\src\dashboard\gen_biomarker_dashboard.py"
$PortalFile  = "f:\⊕Workspace\reports\portal.html"
$ServeDir    = "f:\∞Life\tmp"
$Port        = 9999
$env:PYTHONUTF8 = "1"

# ── 1. Check if server already running on port 9999 ──────────────────────────
$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "✔ HTTP server already running on :$Port" -ForegroundColor Green
} else {
    Write-Host "▶ Starting ∞Life HTTP server on :$Port ..." -ForegroundColor Cyan
    Start-Process -FilePath $Python `
        -ArgumentList "-m", "http.server", $Port, "--directory", "`"$ServeDir`"" `
        -WindowStyle Hidden
    Start-Sleep -Milliseconds 800
    Write-Host "✔ Server started" -ForegroundColor Green
}

# ── 2. Regenerate Biomarker Dashboard ────────────────────────────────────────
Write-Host "▶ Regenerating Biomarker Dashboard ..." -ForegroundColor Cyan
& $Python $DashScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠ Dashboard regen failed (exit $LASTEXITCODE) — using last known file." -ForegroundColor Yellow
} else {
    Write-Host "✔ Dashboard ready" -ForegroundColor Green
}

# ── 3. Open Portal ────────────────────────────────────────────────────────────
Write-Host "▶ Opening portal ..." -ForegroundColor Cyan
Start-Process $PortalFile
