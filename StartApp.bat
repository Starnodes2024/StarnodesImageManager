@echo off
echo Starting StarImageBrowse Application...
cd /d "%~dp0"
venv\Scripts\python.exe main.py
if %ERRORLEVEL% NEQ 0 (
  echo An error occurred while running the application.
  echo Press any key to close this window...
  pause > nul
)
