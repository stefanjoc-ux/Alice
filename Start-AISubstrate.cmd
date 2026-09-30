@echo off
title AI Substrate - Web Chat
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Python environment not found in:
    echo %cd%
    pause
    exit /b 1
)

if not exist "app.py" (
    echo app.py was not found in:
    echo %cd%
    pause
    exit /b 1
)

if not exist "mcp_server.py" (
    echo mcp_server.py was not found in:
    echo %cd%
    pause
    exit /b 1
)

rem Start the MCP server in its own window.
echo Starting MCP server on port 8001...
start "AI Substrate - MCP Server" cmd /k ".venv\Scripts\python.exe mcp_server.py"

rem Open the browser once the web server responds.
start "" /b powershell.exe -NoProfile -Command "for ($attempt = 0; $attempt -lt 60; $attempt++) { try { $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8000' -UseBasicParsing -TimeoutSec 1; if ($response.StatusCode -eq 200) { Start-Process 'http://127.0.0.1:8000'; exit } } catch {}; Start-Sleep -Seconds 1 }"

echo Starting web chat on port 8000...
echo.
echo Keep BOTH server windows open while using AI Substrate.
echo To stop everything, press Ctrl+C in each window.
echo.

".venv\Scripts\python.exe" -m uvicorn app:app --reload --host 127.0.0.1 --port 8000

pause