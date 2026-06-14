$Host.UI.RawUI.WindowTitle = "AMEVA Voice Screen Assistant"
Set-Location $PSScriptRoot

Write-Host "Starting AMEVA Voice Screen Assistant..."
Write-Host ""

# [1] Virtual environment setup check
$EnvDir = "venv"
if (-not (Test-Path $EnvDir)) {
    Write-Host "Virtual environment not found. Running setup.ps1..." -ForegroundColor Yellow
    powershell -ExecutionPolicy Bypass -File .\setup.ps1
}

# [2] Hardware and engine validation (CUDA offload support check)
Write-Host "Verifying hardware and LLM engine match..." -ForegroundColor Cyan
$videoControllers = Get-CimInstance Win32_VideoController
$hasNvidia = $false
foreach ($vc in $videoControllers) {
    if ($vc.Name -match "NVIDIA") { $hasNvidia = $true }
}

if ($hasNvidia) {
    $cudaPath = [Environment]::GetEnvironmentVariable('CUDA_PATH')
    if (-not $cudaPath) {
        $machineCuda = [Environment]::GetEnvironmentVariable('CUDA_PATH', 'Machine')
        if ($machineCuda) {
            Write-Host "Discovered CUDA_PATH from registry. Applying to current session." -ForegroundColor Green
            [Environment]::SetEnvironmentVariable('CUDA_PATH', $machineCuda, 'Process')
            $env:PATH += ";$machineCuda\bin"
            $cudaPath = $machineCuda
        }
    }
    if (-not $cudaPath) {
        Write-Host "[WARNING] NVIDIA GPU detected, but CUDA Toolkit (CUDA_PATH) is missing. Reverting to CPU mode." -ForegroundColor Yellow
        $hasNvidia = $false
    }
}

$pythonExe = "$EnvDir\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

$checkScript = "try:`n    from llama_cpp import llama_supports_gpu_offload`n    print('GPU' if llama_supports_gpu_offload() else 'CPU')`nexcept Exception as e:`n    if 'llama.dll' in str(e) or 'cudart' in str(e).lower(): print('GPU_MISSING_CUDA')`n    else: print('NONE')"
$engineStatus = & $pythonExe -c $checkScript

if ($hasNvidia -and $engineStatus -eq "CPU") {
    Write-Host "NVIDIA GPU detected, but CPU engine is installed. Installing GPU acceleration..." -ForegroundColor Yellow
    & $pythonExe -m pip install llama-cpp-python[server] --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121 --force-reinstall --no-cache-dir --only-binary=llama-cpp-python
} elseif ($hasNvidia -and $engineStatus -eq "GPU_MISSING_CUDA") {
    Write-Host "[WARNING] NVIDIA GPU detected, but CUDA 12 Toolkit is missing. Reverting to CPU engine to prevent crash." -ForegroundColor Red
    & $pythonExe -m pip install llama-cpp-python[server] --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --force-reinstall --no-cache-dir --only-binary=llama-cpp-python
} elseif (-not $hasNvidia -and ($engineStatus -eq "GPU" -or $engineStatus -eq "GPU_MISSING_CUDA")) {
    Write-Host "No NVIDIA GPU detected, but GPU engine is installed. Reverting to CPU..." -ForegroundColor Yellow
    & $pythonExe -m pip install llama-cpp-python[server] --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --force-reinstall --no-cache-dir --only-binary=llama-cpp-python
} elseif ($engineStatus -eq "NONE") {
    Write-Host "Engine not found. Installing default CPU engine..." -ForegroundColor Yellow
    & $pythonExe -m pip install llama-cpp-python[server] --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --only-binary=llama-cpp-python
} else {
    Write-Host "Hardware and Engine configuration matches ($engineStatus mode)." -ForegroundColor Green
}

Write-Host ""
& $pythonExe run.py
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] Application exited with error code $exitCode."
    Read-Host "Press Enter to exit..."
}

