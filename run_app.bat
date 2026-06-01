@echo off
title AMEVA Voice Screen Assistant
cd /d "%~dp0"

echo Starting AMEVA Voice Screen Assistant...
echo.

echo [INFO] Starting LLM server via Docker Compose (if not already running)...
cd docker
docker compose up -d
cd ..
echo.

if not exist venv\Scripts\activate.bat goto no_venv
echo [INFO] Activating virtual environment (venv)...
call venv\Scripts\activate.bat
goto run_app

:no_venv
echo [WARNING] virtual environment (venv) not found.
echo Running with system default python...

:run_app
echo.
python run.py
if errorlevel 1 goto error_exit
goto end

:error_exit
echo.
echo [ERROR] Application exited with error code %ERRORLEVEL%.
pause

:end
