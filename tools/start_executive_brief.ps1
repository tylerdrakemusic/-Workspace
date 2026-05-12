$project = Get-ChildItem -Path "f:\" -Directory | Where-Object { $_.Name -like "*AI-Manifest" } | Select-Object -First 1
if (-not $project) {
	Write-Error "Could not locate AI-Manifest project directory under f:\"
	exit 1
}

$projectRoot = $project.FullName
$env:PYTHONPATH = Join-Path $projectRoot "src"
$toolPath = Join-Path $projectRoot "tools\executive_audio_brief.py"

& "C:\G\python.exe" $toolPath --serve --port 8200
