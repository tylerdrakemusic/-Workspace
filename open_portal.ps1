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

# ── 6. Start ∞Life Biomarker Dashboard server (port 8300) ────────────────────
$BioScript = "f:\∞Life\src\dashboard\gen_biomarker_dashboard.py"
$BioPort   = 8300
$existingBio = Get-NetTCPConnection -LocalPort $BioPort -State Listen -ErrorAction SilentlyContinue
if ($existingBio) {
    Write-Host "✔ Biomarker Dashboard server already running on :$BioPort" -ForegroundColor Green
} else {
    Write-Host "▶ Starting Biomarker Dashboard server on :$BioPort ..." -ForegroundColor Cyan
    Start-Process -FilePath $Python `
        -ArgumentList "`"$BioScript`"", "--serve", "--port", $BioPort `
        -WorkingDirectory "f:\∞Life" `
        -WindowStyle Hidden
    Start-Sleep -Milliseconds 1500
    $checkBio = Get-NetTCPConnection -LocalPort $BioPort -State Listen -ErrorAction SilentlyContinue
    if ($checkBio) {
        Write-Host "✔ Biomarker Dashboard server started" -ForegroundColor Green
    } else {
        Write-Host "⚠ Biomarker Dashboard server may still be starting (check port $BioPort)" -ForegroundColor Yellow
    }
}

# ── 7. Serve Portal via HTTP (required for live iframe panels) ───────────────
# Browsers block http:// iframes in file:// pages (mixed content policy).
# Serving via HTTP on :8080 lets all live panels load correctly.
$PortalPort    = 8080
$PortalDir     = "f:\⊕Workspace\reports"
$PortalUrl     = "http://localhost:$PortalPort/portal.html"
$existingPortal = Get-NetTCPConnection -LocalPort $PortalPort -State Listen -ErrorAction SilentlyContinue
if ($existingPortal) {
    Write-Host "✔ Portal HTTP server already running on :$PortalPort" -ForegroundColor Green
} else {
    Write-Host "▶ Starting Portal HTTP server on :$PortalPort ..." -ForegroundColor Cyan
    Start-Process -FilePath $Python `
        -ArgumentList "-m", "http.server", $PortalPort, "--directory", "`"$PortalDir`"" `
        -WindowStyle Hidden
    Start-Sleep -Milliseconds 800
    $checkPortal = Get-NetTCPConnection -LocalPort $PortalPort -State Listen -ErrorAction SilentlyContinue
    if ($checkPortal) {
        Write-Host "✔ Portal HTTP server started" -ForegroundColor Green
    } else {
        Write-Host "⚠ Portal HTTP server may still be starting (check port $PortalPort)" -ForegroundColor Yellow
    }
}

# ── 8. Create / refresh desktop shortcut with portal icon ────────────────────
# WScript.Shell has three Unicode bugs we work around:
#   1. Shortcut filename  → create ASCII temp name, rename via Move-Item
#   2. IconLocation path  → stage ICO to %LOCALAPPDATA%\WorkspacePortal\ (ASCII)
#   3. Arguments path     → stage a PS1 launcher to the same ASCII directory;
#                           written with UTF-8 BOM so PowerShell 5.1 reads ⊕ OK
$SrcIco     = "f:\⊕Workspace\src\data\portal_icon.ico"
$PortalHtml = "f:\⊕Workspace\reports\portal.html"
$StagingDir = Join-Path $env:LOCALAPPDATA "WorkspacePortal"
$StagedIco  = Join-Path $StagingDir "portal_icon.ico"
$StagedPs1  = Join-Path $StagingDir "open_portal.ps1"
$Desktop    = [Environment]::GetFolderPath("Desktop")
$TmpLnk     = Join-Path $Desktop "_workspace_portal_tmp.lnk"
$FinalLnk   = Join-Path $Desktop "⊕ Workspace Portal.lnk"
try {
    if (-not (Test-Path $StagingDir)) { New-Item -ItemType Directory -Path $StagingDir -Force | Out-Null }
    Copy-Item -Path $SrcIco -Destination $StagedIco -Force
    # UTF-8 BOM so PowerShell 5.1 reads the ⊕ path in the script correctly
    [System.IO.File]::WriteAllText($StagedPs1, "Start-Process `"$PortalHtml`"`n",
        [System.Text.UTF8Encoding]::new($true))
    if (Test-Path $TmpLnk)  { Remove-Item $TmpLnk  -Force }
    if (Test-Path $FinalLnk){ Remove-Item $FinalLnk -Force }
    $WScript  = New-Object -ComObject WScript.Shell
    $Shortcut = $WScript.CreateShortcut($TmpLnk)
    $Shortcut.TargetPath       = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    $Shortcut.Arguments        = "-WindowStyle Hidden -NonInteractive -File `"$StagedPs1`""
    $Shortcut.WindowStyle      = 7
    $Shortcut.WorkingDirectory = "f:\⊕Workspace\reports"
    $Shortcut.IconLocation     = "$StagedIco,0"
    $Shortcut.Description      = "⊕ Workspace Portal — unified project dashboard"
    $Shortcut.Save()
    Move-Item -Path $TmpLnk -Destination $FinalLnk -Force
    # Flush Windows icon cache so the new icon appears immediately
    $sig = '[DllImport("shell32.dll")] public static extern void SHChangeNotify(int wEventId, int uFlags, IntPtr dwItem1, IntPtr dwItem2);'
    $type = Add-Type -MemberDefinition $sig -Name "Shell32" -Namespace "Win32" -PassThru -ErrorAction SilentlyContinue
    if ($type) { $type::SHChangeNotify(0x08000000, 0x0000, [IntPtr]::Zero, [IntPtr]::Zero) }
    Write-Host "✔ Desktop shortcut refreshed: $FinalLnk" -ForegroundColor Green
} catch {
    Write-Host "⚠ Could not create desktop shortcut: $_" -ForegroundColor Yellow
}

# ── 8. Open Portal ────────────────────────────────────────────────────────────
Write-Host "▶ Opening portal at $PortalUrl ..." -ForegroundColor Cyan
Start-Process $PortalUrl
