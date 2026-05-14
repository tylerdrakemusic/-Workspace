$project = Get-ChildItem -Path "f:\" -Directory | Where-Object { $_.Name -like "*Music" } | Select-Object -First 1
if (-not $project) {
	Write-Error "Could not locate Music project directory under f:\"
	exit 1
}

$projectRoot = $project.FullName
$env:PYTHONPATH = Join-Path $projectRoot "src"
$toolPath = Join-Path $projectRoot "src\band_mgmt\generate_band_mgmt_panel.py"

# Start band management server (Vera API + panel hot-rebuild) on port 8765.
$cmd = "import runpy,sys;sys.argv=[r'" + $toolPath + "','--serve','--port','8765'];runpy.run_path(r'" + $toolPath + "',run_name='__main__')"
& "C:\G\python.exe" -c $cmd
