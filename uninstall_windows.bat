@echo off
REM ============================================================
REM  PrintView3D - remove the per-user installation
REM  Removes file associations, shortcuts and the program folder.
REM  Your settings (%APPDATA%\PrintView3D) are kept unless you agree.
REM ============================================================
setlocal
set "DEST=%LOCALAPPDATA%\Programs\PrintView3D"

tasklist /FI "IMAGENAME eq PrintView3D.exe" | find /I "PrintView3D.exe" >nul && (
    echo Please close PrintView3D first, then run this again.
    pause
    exit /b 1
)

if exist "%DEST%\PrintView3D.exe" (
    echo Removing file associations ...
    "%DEST%\PrintView3D.exe" --unregister
)
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\PrintView3D.lnk" 2>nul
powershell -NoProfile -Command "Remove-Item -ErrorAction SilentlyContinue (Join-Path ([Environment]::GetFolderPath('Desktop')) 'PrintView3D.lnk')"
if exist "%DEST%" rmdir /S /Q "%DEST%"

choice /C YN /M "Also delete your PrintView3D settings (recent files, Creality Print path)"
if errorlevel 2 goto :done
if exist "%APPDATA%\PrintView3D" rmdir /S /Q "%APPDATA%\PrintView3D"
:done
echo PrintView3D has been removed.
pause
