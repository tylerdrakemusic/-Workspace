param([string]$ProjectRoot = "f:\❤Music")

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
	Write-Error "Music project root does not exist: $ProjectRoot"
	exit 1
}

$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$toolPath = Join-Path $ProjectRoot "src\band_mgmt\generate_band_mgmt_panel.py"

# Start band management server (Vera API + panel hot-rebuild) on port 8765.
$cmd = "import runpy,sys;sys.argv=[r'" + $toolPath + "','--serve','--port','8765'];runpy.run_path(r'" + $toolPath + "',run_name='__main__')"
& "C:\G\python.exe" -c $cmd
