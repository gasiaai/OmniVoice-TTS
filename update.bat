@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
REM Strip trailing backslash (prevents \" escaping issues with git -C)
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "PY="
if exist "%ROOT%\python_embeded\python.exe" set "PY=%ROOT%\python_embeded\python.exe"
if "%PY%"=="" if exist "%ROOT%\venv\Scripts\python.exe" set "PY=%ROOT%\venv\Scripts\python.exe"

echo.
echo  OmniVoice TTS - Updater
echo  ========================
echo.

REM --- Check if this is a git repo ---
if not exist "%ROOT%\.git" (
    echo [INFO] This is not a git repository (downloaded from .rar).
    echo        To update, download the latest version from:
    echo        https://github.com/gasiaai/OmniVoice-TTS/releases/latest
    echo.
    if "%PY%"=="" (
        echo        Then run install.bat to set up.
    ) else (
        echo [2/2] Re-running installer to update dependencies...
        "%PY%" "%ROOT%\install.py"
    )
    echo.
    pause
    exit /b 0
)

git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] git not found. Install from https://git-scm.com/download/win
    pause
    exit /b 1
)

echo [1/2] Pulling latest code from GitHub...
git -C "%ROOT%" pull
if errorlevel 1 (
    echo [ERROR] git pull failed. Check internet or resolve conflicts.
    pause
    exit /b 1
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
