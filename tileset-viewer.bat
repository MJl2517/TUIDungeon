@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "tools\tileset-viewer\server.py" %*
) else (
  python "tools\tileset-viewer\server.py" %*
)
if errorlevel 1 pause
