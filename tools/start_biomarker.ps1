#Requires -Version 5.1
# ∞Life Biomarker Dashboard server launcher — called by launch_portal.ps1 via portal_servers.json
# Starts gen_biomarker_dashboard.py in serve mode on port 8300 (hidden window, background process).
# BFX: BFX-20260531-portal-localhost-refused (use discovery to avoid ANSI-encoding of Unicode paths)

$project = Get-ChildItem -Path "f:\" -Directory | Where-Object { $_.Name -like "*Life" } | Select-Object -First 1
if (-not $project) { Write-Error "Could not locate Life project under f:\"; exit 1 }
$Python = 'C:\G\python.exe'
$Script = Join-Path $project.FullName 'src\dashboard\gen_biomarker_dashboard.py'
$Port   = 8300

$env:PYTHONUTF8        = '1'
$env:PYTHONIOENCODING  = 'utf-8'

if (-not (Test-Path $Script)) {
    Write-Error "gen_biomarker_dashboard.py not found at $Script"
    exit 1
}

& $Python $Script --serve --port $Port
