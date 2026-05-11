$heartSigil = [string][char]0x2764
$musicRoot = "f:\" + $heartSigil + "Music"
$env:PYTHONPATH = Join-Path $musicRoot "src"
$dbKey = [System.Environment]::GetEnvironmentVariable("HEARTMUSIC_DB_KEY", "User")
if (-not $dbKey) {
	$dbKey = [System.Environment]::GetEnvironmentVariable("HEARTMUSIC_DB_KEY", "Machine")
}
$env:HEARTMUSIC_DB_KEY = $dbKey
& "C:\G\python.exe" (Join-Path $musicRoot "src\studio\studio_panel.py") --port 5065
