@echo off
REM ============================================================
REM  PrintView3D - build the Windows program (PrintView3D.exe)
REM  Requires Python 3.10-3.14 from python.org (3.12 recommended).
REM  Result: dist\PrintView3D\PrintView3D.exe
REM ============================================================
setlocal
cd /d "%~dp0"

REM The 3D engine (VTK) only supports certain Python versions, so pick one
REM of those explicitly instead of whatever Python is newest on this PC.
set "PY="
for %%V in (3.12 3.13 3.14 3.11 3.10) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V"
    )
)
if not defined PY (
    echo [ERROR] No supported Python version was found.
    echo         PrintView3D needs Python 3.10 to 3.14 ^(3.12 recommended^).
    echo         Newer versions such as 3.15 are not supported yet by the VTK 3D engine.
    echo         Install Python 3.12 from https://www.python.org/downloads/
    echo         It can be installed next to your existing Python - both keep working.
    pause
    exit /b 1
)
echo Using Python: %PY%

echo [1/4] Creating virtual environment (.venv) ...
if not exist ".venv\Scripts\python.exe" (
    %PY% -m venv .venv || goto :fail
)

echo [2/4] Installing dependencies (first time takes a few minutes) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-build.txt || goto :fail

echo [3/4] Running tests ...
".venv\Scripts\python.exe" tests\make_samples.py >nul
".venv\Scripts\python.exe" -m pytest -q tests || goto :fail

echo [4/4] Building PrintView3D.exe ...
".venv\Scripts\pyinstaller.exe" --noconfirm --clean printview3d.spec || goto :fail

echo.
echo ============================================================
echo  Done!  dist\PrintView3D\PrintView3D.exe
echo  Run install_windows.bat to install it for your user account.
echo ============================================================
pause
exit /b 0

:fail
echo.
echo [ERROR] Build failed - see the messages above.
pause
exit /b 1
