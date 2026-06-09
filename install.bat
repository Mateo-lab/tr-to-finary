@echo off
title TR to Finary - Installation
color 0B
echo.
echo  ====================================
echo   TR to Finary - Installation
echo  ====================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python is not installed or not in PATH.
    echo  Please install Python 3.10+ from https://python.org
    echo.
    pause
    exit /b 1
)

echo  [1/4] Python found:
python --version
echo.

:: Install main dependencies
echo  [2/4] Installing dependencies...
pip install finary-uapi pytr rich fastapi "uvicorn[standard]" jinja2 python-multipart
if errorlevel 1 (
    echo.
    echo  [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo.

:: Install Playwright for pytr
echo  [3/4] Installing Playwright (for Trade Republic login)...
python -m playwright install chromium
echo.

:: Done
echo  [4/4] Installation complete!
echo.
echo  ====================================
echo   Next steps:
echo  ====================================
echo.
echo   1. Run the setup wizard:
echo      python -m tr_to_finary.cli --setup
echo.
echo   2. Or launch the Web UI:
echo      start.bat
echo.
echo  ====================================
echo.
pause
