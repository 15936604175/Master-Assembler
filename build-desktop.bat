@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   Master-Assembler - Windows Build
echo ========================================
echo.

:: Setup VC++ environment
echo [1/4] Setting up MSVC environment...
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
if %ERRORLEVEL% neq 0 (
    echo MSVC environment setup failed!
    exit /b 1
)

:: Frontend build
echo.
echo [2/4] Building frontend...
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

:: Backend PyInstaller
echo.
echo [3/4] Packaging backend with PyInstaller...
cd /d "%~dp0backend"
if exist "dist\backend" rmdir /s /q "dist\backend"
if exist "dist\backend.exe" del /q "dist\backend.exe"
if exist "build" rmdir /s /q "build"
pip install pyinstaller --quiet
pyinstaller backend.spec -y
if %ERRORLEVEL% neq 0 (
    echo Backend packaging failed!
    exit /b 1
)
cd /d "%~dp0"

:: Copy sidecar and build Tauri
echo.
echo [4/4] Building Tauri desktop app...
if exist "%~dp0src-tauri\binaries" rmdir /s /q "%~dp0src-tauri\binaries"
xcopy /E /I /Y "%~dp0backend\dist\backend" "%~dp0src-tauri\binaries"

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
echo.
echo   To publish: create GitHub Release with tag v{version}
echo   and upload the installer above.
echo ========================================
pause
