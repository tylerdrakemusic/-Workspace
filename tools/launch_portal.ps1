# Portal Launcher - config-driven, reads portal_servers.json

$TOOLS_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$CONFIG    = Join-Path $TOOLS_DIR "portal_servers.json"
$BRAVE     = "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
$PORTAL    = $TOOLS_DIR.Replace("tools","reports") + "\portal.html"

if (-not (Test-Path $CONFIG)) { Write-Host "ERROR: Config not found: $CONFIG" -ForegroundColor Red; exit 1 }
$cfg = Get-Content $CONFIG -Raw | ConvertFrom-Json
$servers = $cfg.servers | Where-Object { $_.enabled -eq $true }

function Start-Server { param($s)
    $inUse = Get-NetTCPConnection -LocalPort $s.port -State Listen -ErrorAction SilentlyContinue
    if ($inUse) { Write-Host "  [$($s.name)] :$($s.port) already listening - skipping" -ForegroundColor Cyan; return }
    Write-Host "  [$($s.name)] Starting on port $($s.port)..." -ForegroundColor Yellow
    $parts = $s.cmd -split ' ', 2
    $args = if ($parts.Count -gt 1) { $parts[1] } else { "" }
    Start-Process -FilePath $parts[0] -ArgumentList $args -WindowStyle Hidden
}

Write-Host "Portal Launcher ($($servers.Count) services)" -ForegroundColor Magenta
foreach ($s in $servers) { Start-Server $s }

$delay = [Math]::Max(3, $servers.Count * 2)
Write-Host "  Waiting ${delay}s for servers to bind..." -ForegroundColor DarkGray
Start-Sleep -Seconds $delay

$portalUri = "file:///" + ($PORTAL -replace "\\", "/")
if (Test-Path $BRAVE) { & $BRAVE $portalUri } else { Start-Process $portalUri }
Write-Host "  Portal opened." -ForegroundColor Green