@echo off
REM ============================================================
REM  PrintView3D - install for the current user (no admin needed)
REM  Copies dist\PrintView3D to %LOCALAPPDATA%\Programs\PrintView3D
REM  and adds a Start menu shortcut (and optionally a desktop one).
REM ============================================================
setlocal
cd /d "%~dp0"

set "SRC=%~dp0dist\PrintView3D"
if not exist "%SRC%\PrintView3D.exe" (
    REM Also works when this script sits next to PrintView3D.exe (release zip)
    if exist "%~dp0PrintView3D.exe" (set "SRC=%~dp0.") else (
        echo [ERROR] PrintView3D.exe not found. Run build_windows.bat first.
        pause
        exit /b 1
    )
)
set "DEST=%LOCALAPPDATA%\Programs\PrintView3D"

tasklist /FI "IMAGENAME eq PrintView3D.exe" | find /I "PrintView3D.exe" >nul && (
    echo Please close PrintView3D first, then run this again.
    pause
    exit /b 1
)

echo Installing to %DEST% ...
robocopy "%SRC%" "%DEST%" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
    echo [ERROR] Copy failed.
    pause
    exit /b 1
)

set "LNK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\PrintView3D.lnk"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%LNK%'); $s.TargetPath='%DEST%\PrintView3D.exe'; $s.WorkingDirectory='%DEST%'; $s.Description='STL, 3MF and G-code viewer'; $s.Save()"

choice /C YN /M "Create a desktop shortcut too"
if errorlevel 2 goto :nodesk
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'PrintView3D.lnk')); $s.TargetPath='%DEST%\PrintView3D.exe'; $s.WorkingDirectory='%DEST%'; $s.Save()"
:nodesk

echo.
echo Installed. Open PrintView3D, then go to Settings to make it the default
echo program for .stl / .3mf / .gcode files.
start "" "%DEST%\PrintView3D.exe"
pause
