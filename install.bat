@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set "ROOT=%~dp0"
set "PYDIR=%ROOT%python_embeded"
set "PY=%PYDIR%\python.exe"
set "PY_VER=3.11.9"
set "PY_URL=https://www.python.org/ftp/python/%PY_VER%/python-%PY_VER%-embed-amd64.zip"

echo.
echo  ============================================================
echo   OmniVoice TTS  --  Installer
echo  ============================================================
echo.

REM ── Step 1: Python embeddable ─────────────────────────────────────────────
if exist "%PY%" (
    echo  [1/4] Python embeddable found -- skip download
) else (
    echo  [1/4] Downloading Python %PY_VER% embeddable...
    powershell -NoProfile -Command ^
        "Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%ROOT%py_embed.zip' -UseBasicParsing"
    if errorlevel 1 (
        echo  [ERROR] Download failed. Check internet connection.
        pause & exit /b 1
    )
    echo  [1/4] Extracting...
    powershell -NoProfile -Command ^
        "Expand-Archive -Path '%ROOT%py_embed.zip' -DestinationPath '%PYDIR%' -Force"
    del "%ROOT%py_embed.zip" 2>nul

    REM Enable site-packages: uncomment "import site" in ._pth file
    powershell -NoProfile -Command ^
        "Get-ChildItem '%PYDIR%' -Filter '*.pth' | ForEach-Object { (Get-Content $_.FullName) -replace '#import site','import site' | Set-Content $_.FullName }"
    echo  [1/4] Python OK
)

REM ── Step 2: pip ───────────────────────────────────────────────────────────
if exist "%PYDIR%\Scripts\pip.exe" (
    echo  [2/4] pip found -- skip
) else (
    echo  [2/4] Installing pip...
    powershell -NoProfile -Command ^
        "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%ROOT%get-pip.py' -UseBasicParsing"
    "%PY%" "%ROOT%get-pip.py" --no-warn-script-location -q
    del "%ROOT%get-pip.py" 2>nul
    echo  [2/4] pip OK
)

REM ── Step 3: packages ──────────────────────────────────────────────────────
echo  [3/4] Installing packages (PyTorch + OmniVoice + deps)...
echo        First run may download 3-6 GB. Please wait...
echo.
"%PY%" "%ROOT%install.py"
if errorlevel 1 (
    echo.
    echo  [ERROR] Installation failed. See error above.
    pause & exit /b 1
)

REM ── Step 4: Done ──────────────────────────────────────────────────────────
echo.
echo  [4/4] Done!  Double-click run.bat to start OmniVoice TTS.
echo.
pause
