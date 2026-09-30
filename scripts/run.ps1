# Start SentinelOS: http://127.0.0.1:8765
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = if (Test-Path .\.venv\Scripts\python.exe) { ".\.venv\Scripts\python.exe" } else { "python" }
& $python -m sentinel.server @args
