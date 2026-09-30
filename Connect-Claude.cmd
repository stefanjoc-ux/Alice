@echo off
rem Connects Claude Desktop to AI Substrate (local MCP). Safe to run again.
cd /d "%~dp0"
".venv\Scripts\python.exe" connect_claude.py %*
pause
