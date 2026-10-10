@echo off
title Alice - External endpoint check
cd /d "%~dp0"
rem Checks Microsoft 365 sign-in for Alice's external endpoint on this PC (localhost only; nothing is exposed).
rem Needs the Azure CLI (winget install Microsoft.AzureCLI) and the ALICE_EXT_* settings in .env.

if not exist ".venv\Scripts\python.exe" (
    echo Python environment not found in:
    echo %cd%
    pause
    exit /b 1
)
.venv\Scripts\python.exe external_check.py
set RESULT=%errorlevel%
echo.
pause
exit /b %RESULT%
