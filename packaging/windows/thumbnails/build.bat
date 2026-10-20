@echo off
REM Builds the Explorer thumbnail provider (64-bit) and its test program.
REM Needs Visual Studio Build Tools (C++). Run from this folder:  build.bat <version>
setlocal
set "VER=%~1"
if "%VER%"=="" set "VER=dev"
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VS=%%i"
if not defined VS ( echo Visual Studio C++ tools not found & exit /b 1 )
call "%VS%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
if not exist out mkdir out
cl /nologo /O2 /EHsc /std:c++17 /W4 /MT /LD /DUNICODE /D_UNICODE provider.cpp thumbcore.cpp tinf\tinflate.c ^
   /Feout\PrintView3DThumbnails-%VER%.dll /Foout\ /link /DEF:provider.def ole32.lib shlwapi.lib windowscodecs.lib gdi32.lib || exit /b 1
cl /nologo /O2 /EHsc /std:c++17 /MT /DUNICODE /D_UNICODE test_thumbs.cpp /Feout\test_thumbs.exe /Foout\ ^
   /link ole32.lib shell32.lib shlwapi.lib windowscodecs.lib gdi32.lib user32.lib || exit /b 1
echo Built out\PrintView3DThumbnails-%VER%.dll
