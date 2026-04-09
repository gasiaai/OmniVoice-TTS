@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"

if exist "%ROOT%python_embeded\python.exe" (
    set "PY=%ROOT%python_embeded\python.exe"
    goto :run
)
if exist "%ROOT%venv\Scripts\python.exe" (
    set "PY=%ROOT%venv\Scripts\python.exe"
    goto :run
)

echo Please run install.bat first.
pause
exit /b 1

:run
"%PY%" "%ROOT%server.py"
if errorlevel 1 pause
