@echo off
chcp 65001 >nul
setlocal

set "PY=%~dp0python_embeded\python.exe"

if not exist "%PY%" (
    echo  Please run install.bat first.
    pause
    exit /b 1
)

"%PY%" "%~dp0server.py"
if errorlevel 1 pause
