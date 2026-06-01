# =============================================================================
# AMEVA Voice Screen Assistant — Windows Environment Setup
# =============================================================================
# Usage: powershell -ExecutionPolicy Bypass -File setup.ps1
# =============================================================================

$ErrorActionPreference = "Stop"

$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$VENV_DIR     = Join-Path $PROJECT_ROOT "venv"
$REQ_FILE     = Join-Path $PROJECT_ROOT "requirements.txt"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  AMEVA Voice Screen Assistant Setup"        -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# --- Step 1: Check Python ---
Write-Host "[1/4] Checking Python installation..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "  Found: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python not found. Please install Python 3.10+ first." -ForegroundColor Red
    exit 1
}

# --- Step 2: Create virtual environment ---
Write-Host "[2/4] Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path $VENV_DIR) {
    Write-Host "  venv already exists, skipping creation." -ForegroundColor DarkGray
} else {
    python -m venv $VENV_DIR
    Write-Host "  Created: $VENV_DIR" -ForegroundColor Green
}

# --- Step 3: Activate and upgrade pip ---
Write-Host "[3/4] Activating venv and upgrading pip..." -ForegroundColor Yellow
$activateScript = Join-Path $VENV_DIR "Scripts\Activate.ps1"
& $activateScript
python -m pip install --upgrade pip --quiet

# --- Step 4: Install dependencies ---
Write-Host "[4/4] Installing dependencies..." -ForegroundColor Yellow
if (Test-Path $REQ_FILE) {
    pip install -r $REQ_FILE --quiet
    Write-Host "  Dependencies installed successfully." -ForegroundColor Green
} else {
    Write-Host "  WARNING: requirements.txt not found at $REQ_FILE" -ForegroundColor Red
}

# --- Create runtime directories ---
Write-Host ""
Write-Host "Creating runtime directories..." -ForegroundColor Yellow
$dirs = @("db", "logs", "data\captures")
foreach ($d in $dirs) {
    $fullPath = Join-Path $PROJECT_ROOT $d
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
        Write-Host "  Created: $d" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Setup complete!"                           -ForegroundColor Green
Write-Host "  Run the app with: python run.py"           -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
