@echo off
title Alice - Tests
cd /d "%~dp0"
rem Runs Alice's checks safely: a throwaway data folder and dummy keys. Your data\ and .env keys are never used.
rem Optional: drag nothing on it, or run from a prompt with suite names, e.g.  Run-Tests.cmd rules organisations

if not exist ".venv\Scripts\python.exe" (
    echo Python environment not found in:
    echo %cd%
    pause
    exit /b 1
)

echo Step 1 of 2: import check
.venv\Scripts\python.exe -c "import app, mcp_server; print('Import check OK')"
if errorlevel 1 (
    echo.
    echo IMPORT CHECK FAILED - a file is missing or has a syntax error. See the message above.
    pause
    exit /b 1
)

echo.
echo Step 2 of 2: test suites ^(about two minutes^)
.venv\Scripts\python.exe tests\run_tests.py %*
set RESULT=%errorlevel%

echo.
if %RESULT%==0 (
    echo ALL TESTS PASSED. Safe to relaunch Alice.
) else (
    echo SOME TESTS FAILED. Do not relaunch on this code; send the output above to Claude.
)
pause
exit /b %RESULT%
