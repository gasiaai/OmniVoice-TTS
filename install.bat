@echo off
chcp 65001 >nul

python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

if not exist venv (
    python -m venv venv
)

call venv\Scripts\activate.bat
python install.py
pause
