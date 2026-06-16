$heartSigil = [string][char]0x2764
$musicRoot = "f:\" + $heartSigil + "Music"
$env:PYTHONPATH = Join-Path $musicRoot "src"

$dbKey = [System.Environment]::GetEnvironmentVariable("HEARTMUSIC_DB_KEY", "User")
if (-not $dbKey) {
    $dbKey = [System.Environment]::GetEnvironmentVariable("HEARTMUSIC_DB_KEY", "Machine")
}
if (-not $dbKey) {
    Write-Host "WARNING: HEARTMUSIC_DB_KEY not found in User or Machine environment; Studio Panel may fail to open heartmusic.db" -ForegroundColor Yellow
}
$env:HEARTMUSIC_DB_KEY = $dbKey

$dbPath = [System.Environment]::GetEnvironmentVariable("HEARTMUSIC_DB_PATH", "User")
if (-not $dbPath) {
    $dbPath = [System.Environment]::GetEnvironmentVariable("HEARTMUSIC_DB_PATH", "Machine")
}
if ($dbPath) {
    $env:HEARTMUSIC_DB_PATH = $dbPath
    Write-Host "Using HEARTMUSIC_DB_PATH=$dbPath"
} else {
    Write-Host "Using default HEARTMUSIC_DB_PATH; no explicit override set."
}

& "C:\G\python.exe" (Join-Path $musicRoot "src\studio\studio_panel.py") --port 5065
