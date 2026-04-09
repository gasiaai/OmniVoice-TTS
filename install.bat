@echo off
chcp 65001 >nul
setlocal

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
    echo  [1/4] Python embeddable พบแล้ว -- ข้ามขั้นตอนนี้
    goto :pip
)

echo  [1/4] กำลังดาวน์โหลด Python %PY_VER% embeddable...

REM เขียน PowerShell script ลง temp file เพื่อหลีกเลี่ยงปัญหา ^ continuation
echo Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%ROOT%py_embed.zip' -UseBasicParsing > "%TEMP%\ov_dl.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\ov_dl.ps1"
del "%TEMP%\ov_dl.ps1" 2>nul

if not exist "%ROOT%py_embed.zip" (
    echo.
    echo  [ERROR] ดาวน์โหลด Python ล้มเหลว
    echo          ตรวจสอบอินเทอร์เน็ต แล้วลองใหม่
    pause & exit /b 1
)

echo  [1/4] กำลังแตกไฟล์...
echo Expand-Archive -Path '%ROOT%py_embed.zip' -DestinationPath '%PYDIR%' -Force > "%TEMP%\ov_ex.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\ov_ex.ps1"
del "%TEMP%\ov_ex.ps1" 2>nul
del "%ROOT%py_embed.zip" 2>nul

if not exist "%PY%" (
    echo  [ERROR] แตกไฟล์ล้มเหลว
    pause & exit /b 1
)

REM เปิด site-packages: เปลี่ยน #import site → import site ใน ._pth
for %%F in ("%PYDIR%\*.pth") do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-Content '%%F') -replace '#import site','import site' | Set-Content '%%F'"
)
echo  [1/4] Python OK

:pip
REM ── Step 2: pip ───────────────────────────────────────────────────────────
if exist "%PYDIR%\Scripts\pip.exe" (
    echo  [2/4] pip พบแล้ว -- ข้ามขั้นตอนนี้
    goto :packages
)

echo  [2/4] กำลังติดตั้ง pip...
echo Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%ROOT%get-pip.py' -UseBasicParsing > "%TEMP%\ov_pip.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\ov_pip.ps1"
del "%TEMP%\ov_pip.ps1" 2>nul

if not exist "%ROOT%get-pip.py" (
    echo  [ERROR] ดาวน์โหลด pip ล้มเหลว
    pause & exit /b 1
)
"%PY%" "%ROOT%get-pip.py" --no-warn-script-location -q
del "%ROOT%get-pip.py" 2>nul
echo  [2/4] pip OK

:packages
REM ── Step 3: packages ──────────────────────────────────────────────────────
echo  [3/4] กำลังติดตั้ง packages (PyTorch + OmniVoice + deps)...
echo        ครั้งแรกอาจโหลดนานมาก (~3-6 GB) กรุณารอ...
echo.
"%PY%" "%ROOT%install.py"
if errorlevel 1 (
    echo.
    echo  [ERROR] ติดตั้งล้มเหลว -- ดูข้อผิดพลาดด้านบน
    pause & exit /b 1
)

REM ── Done ──────────────────────────────────────────────────────────────────
echo.
echo  [4/4] ติดตั้งเสร็จสิ้น!  ดับเบิลคลิก run.bat เพื่อเริ่มใช้งาน
echo.
pause
