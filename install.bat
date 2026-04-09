@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
set "PYDIR=%ROOT%python_embeded"
set "PY=%PYDIR%\python.exe"
set "PY_VER=3.11.9"
set "PY_URL=https://www.python.org/ftp/python/%PY_VER%/python-%PY_VER%-embed-amd64.zip"

echo.
echo  OmniVoice TTS - Installer
echo  ==========================
echo.

REM --- Step 1: Python embeddable ---
if exist "%PY%" (
    echo [1/4] Python embeddable found, skipping download.
    goto :bootstrap
)

echo [1/4] Downloading Python %PY_VER% embeddable...
echo Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%ROOT%py_embed.zip' -UseBasicParsing > "%TEMP%\ov_dl.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\ov_dl.ps1"
del "%TEMP%\ov_dl.ps1" 2>nul

if not exist "%ROOT%py_embed.zip" (
    echo [ERROR] Download failed. Check your internet connection.
    pause
    exit /b 1
)

echo [1/4] Extracting...
echo Expand-Archive -Path '%ROOT%py_embed.zip' -DestinationPath '%PYDIR%' -Force > "%TEMP%\ov_ex.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\ov_ex.ps1"
del "%TEMP%\ov_ex.ps1" 2>nul
del "%ROOT%py_embed.zip" 2>nul

if not exist "%PY%" (
    echo [ERROR] Extraction failed.
    pause
    exit /b 1
)
echo [1/4] Python OK.

:bootstrap
REM --- Step 2: Enable site-packages + install pip (via bootstrap.py) ---
echo [2/4] Setting up pip...
"%PY%" "%ROOT%bootstrap.py"
if errorlevel 1 (
    echo [ERROR] pip setup failed. See error above.
    pause
    exit /b 1
)

REM --- Step 3: Install packages ---
echo [3/4] Installing packages (PyTorch + OmniVoice + deps)...
echo       First run may download 3-6 GB. Please wait...
echo.
"%PY%" "%ROOT%install.py"
if errorlevel 1 (
    echo.
    echo [ERROR] Installation failed. See error above.
    pause
    exit /b 1
)

echo.
echo [4/4] Done! Run run.bat to start OmniVoice TTS.
echo.
pause
