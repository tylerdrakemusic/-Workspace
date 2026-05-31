$project = Get-ChildItem -Path "f:\" -Directory | Where-Object { $_.Name -like "*Workspace" } | Select-Object -First 1
if (-not $project) { Write-Error "Could not locate Workspace project under f:\"; exit 1 }
$projectRoot = $project.FullName
$env:PYTHONUTF8        = "1"
$env:PYTHONIOENCODING  = "utf-8"
& "C:\G\python.exe" (Join-Path $projectRoot "src\utils\fr_server.py") "--port" "7474"
