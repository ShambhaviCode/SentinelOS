# SentinelOS setup for a Snapdragon Windows PC.
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1            # QNN (NPU) runtime
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Cpu       # CPU-only runtime
param([switch]$Cpu)
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# Find a native ARM64 Python via the py launcher.
$py = $null
foreach ($v in @("-3.12-arm64", "-3.11-arm64", "-3.13-arm64", "-3-arm64")) {
    try { $m = & py $v -c "import platform; print(platform.machine())" 2>$null; if ($m -eq "ARM64") { $py = $v; break } } catch {}
}
if (-not $py -and -not $Cpu) {
    Write-Host "No native ARM64 Python found. The QNN provider will not load under x64 emulation." -ForegroundColor Yellow
    Write-Host "Install the ARM64 build from https://www.python.org/downloads/windows/ and re-run, or use -Cpu."
    exit 1
}
if (-not $py) { $py = "-3" }

& py $py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($Cpu) { & .\.venv\Scripts\python.exe -m pip install -r requirements-ml-cpu.txt }
else { & .\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt }
& .\.venv\Scripts\python.exe -c "import platform, onnxruntime as o; print('Python arch:', platform.machine()); print('ORT', o.__version__, o.get_available_providers())"
Write-Host "`nActivate with: .\.venv\Scripts\Activate.ps1"
