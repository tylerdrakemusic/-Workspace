param([string]$ProjectRoot = "f:\❤Music")

if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
	Write-Error "Music project root does not exist: $ProjectRoot"
	exit 1
}

$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$script = Join-Path $ProjectRoot "src\analysis\music_dashboard.py"
& "C:\G\python.exe" $script --port 5050 --no-open