# Portal Launcher - config-driven, reads portal_servers.json
# When invoked via portal:// custom protocol handler, pass -NoOpen to skip
# re-opening the browser (the portal is already open in the tab that triggered it).
param([switch]$NoOpen)

$TOOLS_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$CONFIG    = Join-Path $TOOLS_DIR "portal_servers.json"
$BRAVE     = "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
$PORTAL    = $TOOLS_DIR.Replace("tools","reports") + "\portal.html"
$PORTAL_MIN_REGEN_AGE_SECONDS = 30

# Always refresh portal + static mirrors on protocol launch so file:// opens
# pick up the latest Quantum/Band Management outputs.
$PORTAL_GEN = Join-Path $TOOLS_DIR "dashboard_portal.py"
if (Test-Path $PORTAL_GEN) {
    $shouldRegen = $true
    if (Test-Path $PORTAL) {
        $age = (Get-Date) - (Get-Item $PORTAL).LastWriteTime
        if ($age.TotalSeconds -lt $PORTAL_MIN_REGEN_AGE_SECONDS) {
            $shouldRegen = $false
        }
    }
    if ($shouldRegen) {
    $prevPyUtf8 = $env:PYTHONUTF8
    $prevPyIo = $env:PYTHONIOENCODING
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    try {
        Start-Process -FilePath "C:\G\python.exe" -ArgumentList @($PORTAL_GEN, "--regen", "--no-open") -WindowStyle Hidden
        # Regenerate security dashboard in parallel so it reflects current DB state on every open
        $SECURITY_SCAN = Join-Path (Split-Path -Parent $TOOLS_DIR) "src\utils\security_scan.py"
        if (Test-Path $SECURITY_SCAN) {
            Start-Process -FilePath "C:\G\python.exe" -ArgumentList @($SECURITY_SCAN) -WindowStyle Hidden
        }
    }
    finally {
        $env:PYTHONUTF8 = $prevPyUtf8
        $env:PYTHONIOENCODING = $prevPyIo
    }
    Write-Host "  Portal mirrors refreshing in background." -ForegroundColor DarkGray
    }
}

if (-not (Test-Path $CONFIG)) { Write-Host "ERROR: Config not found: $CONFIG" -ForegroundColor Red; exit 1 }
$cfg = Get-Content $CONFIG -Raw | ConvertFrom-Json
$servers = $cfg.servers | Where-Object { $_.enabled -eq $true }

$listeningPorts = @{}
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    $listeningPorts[[int]$_.LocalPort] = $true
}

function Start-Server { param($s)
    if ($listeningPorts.ContainsKey([int]$s.port)) { Write-Host "  [$($s.name)] :$($s.port) already listening - skipping" -ForegroundColor Cyan; return }
    Write-Host "  [$($s.name)] Starting on port $($s.port)..." -ForegroundColor Yellow
    $parts = $s.cmd -split ' ', 2
    $commandTail = if ($parts.Count -gt 1) { $parts[1] } else { "" }
    Start-Process -FilePath $parts[0] -ArgumentList $commandTail -WindowStyle Hidden
}

function Wait-PortListening {
    param(
        [int]$Port,
        [int]$TimeoutSeconds = 20
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($listening) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

Write-Host "Portal Launcher ($($servers.Count) services)" -ForegroundColor Magenta
foreach ($s in $servers) { Start-Server $s }

$portalUri = "file:///" + ($PORTAL -replace "\\", "/")
if (-not $NoOpen) {
    # Wait only for the three iframes visible on first load — browsers don't retry
    # connection-refused, so these must be up before the portal renders.
    # Trade Approval Gate is the default first pane, so port 7475 must bind
    # before the local file:// portal shell opens.
    $tradeReady = Wait-PortListening -Port 7475 -TimeoutSeconds 10
    Write-Host ("  [Trade Approval Gate] :7475 " + $(if ($tradeReady) { "ready" } else { "not ready — iframe may fail on first render" })) -ForegroundColor $(if ($tradeReady) { "Green" } else { "Yellow" })
    $execReady = Wait-PortListening -Port 8200 -TimeoutSeconds 10
    Write-Host ("  [Executive] :8200 " + $(if ($execReady) { "ready" } else { "not ready — iframe will show retry prompt" })) -ForegroundColor $(if ($execReady) { "Green" } else { "Yellow" })
    $musicReady = Wait-PortListening -Port 5050 -TimeoutSeconds 8
    Write-Host ("  [Music Dashboard] :5050 " + $(if ($musicReady) { "ready" } else { "not ready — iframe will show retry prompt" })) -ForegroundColor $(if ($musicReady) { "Green" } else { "Yellow" })
    # Guitar Trainer (:5055) — Flask cold-start fix (BFX-20260530-guitar-trainer-cold-start).
    # Browser does not retry connection-refused; must be up before portal opens.
    $gtReady = Wait-PortListening -Port 5055 -TimeoutSeconds 10
    Write-Host ("  [Guitar Trainer] :5055 " + $(if ($gtReady) { "ready" } else { "not ready — iframe will show retry prompt" })) -ForegroundColor $(if ($gtReady) { "Green" } else { "Yellow" })
    if (Test-Path $BRAVE) { & $BRAVE $portalUri } else { Start-Process $portalUri }
    Write-Host "  Portal opened." -ForegroundColor Green
} else {
    Write-Host "  Skipping browser open (invoked via protocol handler)." -ForegroundColor DarkGray
    Write-Host "  Returning immediately; services continue warming in background." -ForegroundColor DarkGray
    exit 0
}

$delay = [Math]::Max(3, $servers.Count * 2)
Write-Host "  Waiting ${delay}s for servers to bind..." -ForegroundColor DarkGray
Start-Sleep -Seconds $delay

$failed = @()
foreach ($s in $servers) {
    if (Wait-PortListening -Port ([int]$s.port) -TimeoutSeconds 20) {
        Write-Host "  [$($s.name)] :$($s.port) listening" -ForegroundColor Green
    } else {
        Write-Host "  [$($s.name)] :$($s.port) failed to start" -ForegroundColor Red
        $failed += $s
    }
}

if ($failed.Count -gt 0) {
    Write-Host "  Some services failed to bind. Check launcher scripts for listed ports." -ForegroundColor Red
    exit 1
}