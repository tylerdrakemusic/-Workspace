# start_icecast.ps1 — Start Icecast2 via WSL for TJD Radio (port 18000)
# Refs: BFX-20260531-radio-stuck-starting

$IcecastPort  = 18000
$IcecastConf  = "/mnt/f/`u{2764}Music/output/radio_phase_alpha/icecast_phase_alpha.xml"

# Check if port 18000 is already listening — skip if already up.
$portInUse = netstat -ano 2>$null | Select-String ":$IcecastPort\s"
if ($portInUse) {
    Write-Host "Icecast already listening on port $IcecastPort — skipping start." -ForegroundColor Cyan
    exit 0
}

# Check WSL is available.
$wslExe = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wslExe) {
    Write-Warning "WSL not found — cannot start Icecast2. Install WSL or start Icecast manually."
    exit 0
}

Write-Host "Starting Icecast2 on port $IcecastPort via WSL..." -ForegroundColor Yellow
try {
    wsl -- bash -c "icecast2 -c $IcecastConf -b" 2>&1
    Write-Host "Icecast2 start command issued." -ForegroundColor Green
} catch {
    Write-Warning "Failed to start Icecast2 via WSL: $_"
    exit 0
}
