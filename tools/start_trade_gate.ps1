$project = Get-ChildItem -Path "f:\" -Directory | Where-Object { $_.Name -like "*Capital*" } | Select-Object -First 1
if (-not $project) { Write-Error "Could not locate Capital project under f:\"; exit 1 }
$projectRoot = $project.FullName
$env:PYTHONUTF8        = "1"
$env:PYTHONIOENCODING  = "utf-8"
& "C:\G\python.exe" (Join-Path $projectRoot "src\utils\trade_gate.py")
