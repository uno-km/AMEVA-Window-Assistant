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
Write-Host "[1/5] Checking Python installation..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "  Found: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python not found. Please install Python 3.10+ first." -ForegroundColor Red
    exit 1
}

# --- Step 2: Create virtual environment ---
Write-Host "[2/5] Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path $VENV_DIR) {
    Write-Host "  venv already exists, skipping creation." -ForegroundColor DarkGray
} else {
    python -m venv $VENV_DIR
    Write-Host "  Created: $VENV_DIR" -ForegroundColor Green
}

# --- Step 3: Activate and upgrade pip ---
Write-Host "[3/5] Activating venv and upgrading pip..." -ForegroundColor Yellow
$activateScript = Join-Path $VENV_DIR "Scripts\Activate.ps1"
& $activateScript
python -m pip install --upgrade pip --quiet

# --- Step 4: Install dependencies ---
Write-Host "[4/5] Installing dependencies..." -ForegroundColor Yellow
if (Test-Path $REQ_FILE) {
    pip install -r $REQ_FILE --quiet
    Write-Host "  Dependencies installed successfully." -ForegroundColor Green
} else {
    Write-Host "  WARNING: requirements.txt not found at $REQ_FILE" -ForegroundColor Red
}

# --- Step 5: Install Tesseract OCR ---
Write-Host "[5/5] Checking and Installing Tesseract OCR..." -ForegroundColor Yellow
$tessRoot = "C:\Program Files\Tesseract-OCR"
$tessExe = Join-Path $tessRoot "tesseract.exe"
if (-not (Test-Path $tessExe)) {
    $tessRoot = "C:\ameva\AI_Models\Tesseract-OCR"
    $tessExe = Join-Path $tessRoot "tesseract.exe"
}

if (Test-Path $tessExe) {
    Write-Host "  Tesseract OCR is already installed at $tessExe" -ForegroundColor Green
} else {
    Write-Host "  Tesseract OCR not found. Installing..." -ForegroundColor Yellow
    
    # Define download URL and temp installer path
    $downloadUrl = "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
    $tempDir = Join-Path $env:TEMP "ameva_tesseract"
    if (-not (Test-Path $tempDir)) { New-Item -ItemType Directory -Path $tempDir -Force | Out-Null }
    $installerPath = Join-Path $tempDir "tesseract-setup.exe"
    
    Write-Host "  Downloading Tesseract installer (approx. 40MB)..." -ForegroundColor Gray
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $downloadUrl -UserAgent "Mozilla/5.0" -OutFile $installerPath -TimeoutSec 300
        Write-Host "  Download complete." -ForegroundColor Green
    } catch {
        Write-Host "  ERROR: Failed to download Tesseract installer from $downloadUrl" -ForegroundColor Red
        Write-Host "  Exception: $_" -ForegroundColor DarkGray
    }
    
    if (Test-Path $installerPath) {
        Write-Host "  Installing Tesseract silently to $tessRoot..." -ForegroundColor Gray
        try {
            $process = Start-Process -FilePath $installerPath -ArgumentList "/S", "/D=$tessRoot" -Wait -PassThru -NoNewWindow
            if ($process.ExitCode -eq 0 -or (Test-Path $tessExe)) {
                Write-Host "  Tesseract installed successfully." -ForegroundColor Green
            } else {
                Write-Host "  ERROR: Tesseract installation exited with code $($process.ExitCode)" -ForegroundColor Red
            }
        } catch {
            Write-Host "  ERROR: Failed to run Tesseract installer: $_" -ForegroundColor Red
        } finally {
            Remove-Item $installerPath -Force -ErrorAction SilentlyContinue | Out-Null
        }
    }
}

# Verify and download Korean language data
if (Test-Path $tessRoot) {
    $tessDataDir = Join-Path $tessRoot "tessdata"
    $korTrainedData = Join-Path $tessDataDir "kor.traineddata"
    if (-not (Test-Path $tessDataDir)) { New-Item -ItemType Directory -Path $tessDataDir -Force | Out-Null }
    if (-not (Test-Path $korTrainedData)) {
        Write-Host "  Korean language pack not found. Downloading..." -ForegroundColor Yellow
        $korUrl = "https://github.com/tesseract-ocr/tessdata_fast/raw/master/kor.traineddata"
        try {
            Invoke-WebRequest -Uri $korUrl -OutFile $korTrainedData -TimeoutSec 180
            Write-Host "  Downloaded kor.traineddata." -ForegroundColor Green
        } catch {
            Write-Host "  WARNING: Failed to download Korean language pack: $_" -ForegroundColor Red
        }
    } else {
        Write-Host "  Korean language pack is already present." -ForegroundColor Green
    }
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
