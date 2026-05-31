# restart_servers.ps1
# Reads portal_servers.json and kills any processes that are listening on the
# configured ports. Called by open_portal.ps1 before launching fresh servers,
# so that stale dev-session processes do not block the new instances.
# This script ONLY kills — it does not start anything.

$jsonPath = Join-Path $PSScriptRoot "..\tools\portal_servers.json"
$config   = Get-Content -Raw -Path $jsonPath | ConvertFrom-Json

foreach ($s in $config.servers) {
    if (-not $s.enabled) { continue }

    $conn = Get-NetTCPConnection -LocalPort $s.port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        $targetPid = $conn | Select-Object -ExpandProperty OwningProcess -First 1
        Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
        Write-Host "  [$($s.name)] :$($s.port) — killed PID $targetPid"
    } else {
        Write-Host "  [$($s.name)] :$($s.port) — not running, skipping"
    }
}
