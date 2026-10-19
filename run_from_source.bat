@echo off
REM Run PrintView3D directly from the source code (for development/testing).
REM Run build_windows.bat once first so the .venv folder exists.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Run build_windows.bat first to set up the environment.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" tools\i18n.py compile >nul
set "PYTHONPATH=%~dp0src"
start "" ".venv\Scripts\pythonw.exe" -m printview3d %*
