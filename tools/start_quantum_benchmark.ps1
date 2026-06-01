# Quantum Benchmark Server — seeds orion_config.db on first run, then starts
# gen_benchmark_dashboard.py in --serve mode on port 8210.
# Launched by launch_portal.ps1 via portal_servers.json.

$env:PYTHONUTF8 = "1"

$quantum = Get-ChildItem -Path "f:\" -Directory | Where-Object { $_.Name -like "*Quantum*" } | Select-Object -First 1
if (-not $quantum) {
    Write-Error "Could not locate Quantum project directory under f:\"
    exit 1
}

$projectRoot  = $quantum.FullName
$env:PYTHONPATH = Join-Path $projectRoot "src"

$dbPath   = Join-Path $projectRoot "src\data\orion_config.db"
$seedScript = Join-Path $projectRoot "tools\seed_orion_config.py"

# Seed orion_config.db if it doesn't exist yet.
if (-not (Test-Path $dbPath)) {
    Write-Host "  [Quantum Benchmark] Seeding orion_config.db..."
    & "C:\G\python.exe" $seedScript
}

$serverScript = Join-Path $projectRoot "tools\gen_benchmark_dashboard.py"

# Start the server in a hidden window; port 8210, no auto-open browser tab.
# Note: serve mode is the default (no --static flag needed).
Start-Process -FilePath "C:\G\python.exe" `
    -ArgumentList @($serverScript, "--port", "8210", "--no-open") `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden
