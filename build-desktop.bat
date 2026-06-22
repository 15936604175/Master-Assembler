@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   装配大师 - Windows 桌面客户端构建
echo ========================================
echo.

:: 配置 VC++ 环境
echo [准备] 配置 MSVC 编译环境...
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul

echo [1/5] 安装前端依赖...
cd /d "%~dp0frontend"
call npm install --legacy-peer-deps
if %ERRORLEVEL% neq 0 (
    echo 前端依赖安装失败!
    exit /b 1
)
cd /d "%~dp0"

echo.
echo [2/5] 构建前端...
cd /d "%~dp0frontend"
call npm run build
if %ERRORLEVEL% neq 0 (
    echo 前端构建失败!
    exit /b 1
)
cd /d "%~dp0"

echo.
echo [3/5] 安装 PyInstaller 并打包后端...
pip install pyinstaller --quiet
cd /d "%~dp0backend"
pyinstaller backend.spec
if %ERRORLEVEL% neq 0 (
    echo 后端打包失败!
    exit /b 1
)
cd /d "%~dp0"

echo.
echo [4/5] 复制 sidecar 到 Tauri...
if not exist "%~dp0src-tauri\binaries" mkdir "%~dp0src-tauri\binaries"
copy /Y "%~dp0backend\dist\backend\backend.exe" "%~dp0src-tauri\binaries\backend-x86_64-pc-windows-msvc.exe"

echo.
echo [5/5] Tauri 构建...
cd /d "%~dp0src-tauri"
set PATH=%USERPROFILE%\.cargo\bin;%PATH%
rustup target add x86_64-pc-windows-msvc >nul 2>&1
cargo tauri build --target x86_64-pc-windows-msvc
if %ERRORLEVEL% neq 0 (
    echo Tauri 构建失败!
    exit /b 1
)
cd /d "%~dp0"

echo.
echo ========================================
echo   构建完成!
echo.
echo   EXE:          src-tauri\target\release\master-assembler.exe
echo   安装包:       src-tauri\target\release\bundle\nsis\装配大师_1.0.0_x64-setup.exe
echo.
echo   发布到 GitHub:
echo     1. 更新 frontend\src\config.ts 中的版本号
echo     2. 在 GitHub 创建新 Release，标签为 v{版本号}
echo     3. 上传安装包到 Release 附件
echo ========================================
pause
