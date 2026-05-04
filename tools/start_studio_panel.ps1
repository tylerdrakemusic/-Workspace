$env:PYTHONPATH = "f:\❤Music\src"
$env:HEARTMUSIC_DB_KEY = [System.Environment]::GetEnvironmentVariable("HEARTMUSIC_DB_KEY", "User")
& "C:\G\python.exe" "f:\❤Music\src\studio\studio_panel.py" --port 5065
