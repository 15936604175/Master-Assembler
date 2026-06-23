@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   Master-Assembler - Windows Build
echo ========================================
echo.

:: Setup VC++ environment
echo [1/3] Setting up MSVC environment...
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
if %ERRORLEVEL% neq 0 (
    echo MSVC environment setup failed!
    exit /b 1
)

:: Frontend build
echo.
echo [2/3] Building frontend...
cd /d "%~dp0frontend"
call npm install --legacy-peer-deps
if %ERRORLEVEL% neq 0 (
    echo Frontend dependency install failed!
    exit /b 1
)
call npm run build
if %ERRORLEVEL% neq 0 (
    echo Frontend build failed!
    exit /b 1
)
cd /d "%~dp0"

:: Build Tauri (backend is embedded in Tauri binary)
echo.
echo [3/3] Building Tauri desktop app (with embedded backend)...
cd /d "%~dp0src-tauri"
set PATH=%USERPROFILE%\.cargo\bin;%PATH%
cargo tauri build
if %ERRORLEVEL% neq 0 (
    echo Tauri build failed!
    exit /b 1
)
cd /d "%~dp0"

echo.
echo ========================================
echo   Build Complete!
echo.
echo   Installer: src-tauri\target\release\bundle\nsis\Master-Assembler_1.0.0_x64-setup.exe
echo   Single exe with embedded backend - no separate backend.exe needed!
echo.
echo   To publish: create GitHub Release with tag v{version}
echo   and upload the installer above.
echo ========================================
pause
