@echo off
rem AI Substrate desktop: installs tray dependencies, adds a Start menu entry,
rem enables start with Windows, then launches. Safe to run again.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Could not find .venv\Scripts\python.exe beside this file.
  pause & exit /b 1
)
echo Installing desktop dependencies...
".venv\Scripts\python.exe" -m pip install --quiet pystray pillow
if errorlevel 1 (
  echo Could not install pystray/pillow. Check your internet connection and try again.
  pause & exit /b 1
)
".venv\Scripts\python.exe" desktop.py --install
if errorlevel 1 (
  echo Setup failed. Run this file again, or start desktop.py manually.
  pause & exit /b 1
)
echo AI Substrate is starting in the system tray. It will now open automatically when you sign in.
timeout /t 4 >nul
