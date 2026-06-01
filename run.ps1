$Host.UI.RawUI.WindowTitle = "AMEVA Voice Screen Assistant"
Set-Location $PSScriptRoot

Write-Host "Starting AMEVA Voice Screen Assistant..."
Write-Host ""

Write-Host "[INFO] Starting LLM & VLM servers via Docker Compose..."
Set-Location docker
docker compose up -d
Set-Location ..
Write-Host ""

$pythonExe = "python"
if (Test-Path "venv\Scripts\python.exe") {
    Write-Host "[INFO] Using virtual environment (venv)..."
    $pythonExe = "venv\Scripts\python.exe"
} else {
    Write-Host "[WARNING] virtual environment (venv) not found. Using system python."
}

Write-Host ""
& $pythonExe run.py
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Application exited with error code $exitCode."
    Read-Host "Press Enter to exit..."
}
