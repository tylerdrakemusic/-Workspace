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

# ── 3. Start FR Ledger Panel server (port 7474) if not already running ───────
$FrServerScript = "f:\⊕Workspace\src\utils\fr_server.py"
$FrPort         = 7474
$existingFr = Get-NetTCPConnection -LocalPort $FrPort -State Listen -ErrorAction SilentlyContinue
if ($existingFr) {
    Write-Host "✔ FR Ledger server already running on :$FrPort" -ForegroundColor Green
} else {
    Write-Host "▶ Starting FR Ledger server on :$FrPort ..." -ForegroundColor Cyan
    Start-Process -FilePath $Python `
        -ArgumentList "`"$FrServerScript`"", "--port", $FrPort `
        -WindowStyle Hidden
    Start-Sleep -Milliseconds 600
    $check = Get-NetTCPConnection -LocalPort $FrPort -State Listen -ErrorAction SilentlyContinue
    if ($check) {
        Write-Host "✔ FR Ledger server started" -ForegroundColor Green
    } else {
        Write-Host "⚠ FR Ledger server may still be starting (check port $FrPort)" -ForegroundColor Yellow
    }
}

# ── 4. Start Guitar Trainer server (port 5055) ───────────────────────────────
$GuitarTrainerScript = "f:\⊕Workspace\tools\start_guitar_trainer.ps1"
$GuitarTrainerPort   = 5055
$existingGt = Get-NetTCPConnection -LocalPort $GuitarTrainerPort -State Listen -ErrorAction SilentlyContinue
if ($existingGt) {
    Write-Host "✔ Guitar Trainer server already running on :$GuitarTrainerPort" -ForegroundColor Green
} else {
    Write-Host "▶ Starting Guitar Trainer server on :$GuitarTrainerPort ..." -ForegroundColor Cyan
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", "`"$GuitarTrainerScript`"" `
        -WindowStyle Hidden
    Start-Sleep -Milliseconds 800
    $checkGt = Get-NetTCPConnection -LocalPort $GuitarTrainerPort -State Listen -ErrorAction SilentlyContinue
    if ($checkGt) {
        Write-Host "✔ Guitar Trainer server started" -ForegroundColor Green
    } else {
        Write-Host "⚠ Guitar Trainer server may still be starting (check port $GuitarTrainerPort)" -ForegroundColor Yellow
    }
}

# ── 5. Start Executive Audio Brief server (port 8200) ─────────────────────────
$BriefScript = "f:\👁AI-Manifest\tools\executive_audio_brief.py"
$BriefPort   = 8200
$existingBrief = Get-NetTCPConnection -LocalPort $BriefPort -State Listen -ErrorAction SilentlyContinue
if ($existingBrief) {
    Write-Host "✔ Executive Brief server already running on :$BriefPort" -ForegroundColor Green
} else {
    Write-Host "▶ Starting Executive Brief server on :$BriefPort ..." -ForegroundColor Cyan
    Start-Process -FilePath $Python `
        -ArgumentList "`"$BriefScript`"", "--serve", "--port", $BriefPort, "--text-only" `
        -WorkingDirectory "f:\👁AI-Manifest" `
        -WindowStyle Hidden
    Start-Sleep -Milliseconds 1500
    $checkBrief = Get-NetTCPConnection -LocalPort $BriefPort -State Listen -ErrorAction SilentlyContinue
    if ($checkBrief) {
        Write-Host "✔ Executive Brief server started" -ForegroundColor Green
    } else {
        Write-Host "⚠ Executive Brief server may still be starting (check port $BriefPort)" -ForegroundColor Yellow
    }
}

# ── 6. Open Portal ────────────────────────────────────────────────────────────
Write-Host "▶ Opening portal ..." -ForegroundColor Cyan
Start-Process $PortalFile
