$project = Get-ChildItem -Path "f:\" -Directory | Where-Object { $_.Name -like "*AI-Manifest" } | Select-Object -First 1
if (-not $project) {
	Write-Error "Could not locate AI-Manifest project directory under f:\"
	exit 1
}

$projectRoot = $project.FullName
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "$projectRoot;$(Join-Path $projectRoot 'src')"
$toolPath = Join-Path $projectRoot "tools\executive_audio_brief.py"

# Prevent the brief server from auto-opening a separate browser tab.
$briefNoOpenCmd = "import runpy,sys,webbrowser;webbrowser.open=lambda *a,**k: False;sys.argv=[r'" + $toolPath + "','--serve','--port','8200'];runpy.run_path(r'" + $toolPath + "',run_name='__main__')"
& "C:\G\python.exe" -c $briefNoOpenCmd
