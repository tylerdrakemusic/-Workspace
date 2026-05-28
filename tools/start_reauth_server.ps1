#Requires -Version 5.1
# ∞Life Re-auth Micro-Server launcher — called by launch_portal.ps1 via portal_servers.json
# Starts reauth_server.py on port 8766 (hidden window, background process).
# FR: FR-20260528-mfp-reauth-ux

$Python = 'C:\G\python.exe'
$Script = 'f:\∞Life\tools\reauth_server.py'
$Port   = 8766

$env:PYTHONUTF8        = '1'
$env:PYTHONIOENCODING  = 'utf-8'

if (-not (Test-Path $Script)) {
    Write-Error "reauth_server.py not found at $Script"
    exit 1
}

& $Python $Script --port $Port
