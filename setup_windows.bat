@echo off
REM Wildlife Summary — Windows Setup
REM Run once as Administrator: setup_windows.bat

SET SCRIPT_DIR=%~dp0
SET TASK_NAME=WildlifeSummary
SET PYTHON=python

echo === Wildlife Summary Setup (Windows) ===

REM Install dependencies
echo Installing Python dependencies...
%PYTHON% -m pip install -q -r "%SCRIPT_DIR%requirements.txt"

REM Verify .env exists
IF NOT EXIST "%SCRIPT_DIR%.env" (
  echo ERROR: .env file not found.
  echo Please create it from .env.example first.
  pause
  exit /b 1
)

REM Delete existing task if present
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

REM Create scheduled task — runs daily at 21:00 (9 PM)
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "%PYTHON% \"%SCRIPT_DIR%run.py\"" ^
  /sc daily ^
  /st 21:00 ^
  /ru "%USERNAME%" ^
  /f

IF %ERRORLEVEL% EQU 0 (
  echo.
  echo [OK] Done! Wildlife summary will run every day at 9:00 PM.
  echo      To test now, run:  python "%SCRIPT_DIR%run.py" --dry-run
) ELSE (
  echo.
  echo [WARN] Scheduled task creation failed.
  echo        Try running this script as Administrator.
)
pause
