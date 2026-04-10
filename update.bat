@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "REPO=https://github.com/gasiaai/OmniVoice-TTS.git"
set "PY="
if exist "%ROOT%\python_embeded\python.exe" set "PY=%ROOT%\python_embeded\python.exe"
if "%PY%"=="" if exist "%ROOT%\venv\Scripts\python.exe" set "PY=%ROOT%\venv\Scripts\python.exe"

echo.
echo  OmniVoice TTS - Updater
echo  ========================
echo.

git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] git not found. Install from https://git-scm.com/download/win
    pause
    exit /b 1
)

REM --- If no .git, initialize from remote (for .rar downloads) ---
if not exist "%ROOT%\.git" (
    echo [1/2] First update - connecting to GitHub...
    git -C "%ROOT%" init
    git -C "%ROOT%" remote add origin %REPO%
    git -C "%ROOT%" fetch origin main
    git -C "%ROOT%" reset --hard origin/main
    if errorlevel 1 (
        echo [ERROR] Could not fetch from GitHub. Check internet connection.
        pause
        exit /b 1
    )
    echo       Connected! Future updates will be faster.
) else (
    echo [1/2] Pulling latest code from GitHub...
    git -C "%ROOT%" pull
    if errorlevel 1 (
        echo [ERROR] git pull failed. Check internet or resolve conflicts.
        pause
        exit /b 1
    )
)

if "%PY%"=="" (
    echo [2/2] Not installed yet - run install.bat first.
    pause
    exit /b 0
)

echo [2/2] Updating dependencies...
"%PY%" "%ROOT%\install.py"

echo.
echo Update complete!
pause
