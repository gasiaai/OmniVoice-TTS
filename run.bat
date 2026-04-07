@echo off
chcp 65001 >nul

if not exist venv\Scripts\activate.bat (
    echo Please run install.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
python app.py
if errorlevel 1 pause
