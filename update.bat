@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
set "PY=%ROOT%python_embeded\python.exe"

echo.
echo  ============================================================
echo   OmniVoice TTS  --  Updater
echo  ============================================================
echo.

REM ── Check git ────────────────────────────────────────────────────────────
git --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] ไม่พบ git  กรุณาติดตั้ง git ก่อน
    echo          https://git-scm.com/download/win
    pause & exit /b 1
)

REM ── Pull latest code ─────────────────────────────────────────────────────
echo  [1/2] Pulling latest code from GitHub...
git -C "%ROOT%" pull
if errorlevel 1 (
    echo  [ERROR] git pull ล้มเหลว  ตรวจสอบ internet หรือ conflict
    pause & exit /b 1
)

REM ── Re-run install.py to pick up new dependencies ────────────────────────
if exist "%PY%" (
    echo.
    echo  [2/2] Updating dependencies...
    "%PY%" "%ROOT%install.py"
) else (
    echo  [2/2] Not installed yet -- run install.bat first
)

echo.
echo  Update complete!
pause
