@echo off
cd /d "%~dp0"

py -3.11 -c "import sys" >nul 2>&1
if errorlevel 1 (
    echo Dwell needs Python 3.11. 3.14 is too new for the camera libraries.
    echo You already have 3.11 on this PC — if this fails, install it from python.org
    pause
    exit /b 1
)

if not exist .venv (
    echo Creating a private Python environment. First run takes a few minutes...
    py -3.11 -m venv .venv
    if errorlevel 1 (
        echo Could not create .venv
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Starting Dwell. Allow the webcam if Windows asks.
echo F8 turns the mouse on. Esc quits.
echo.
python -m dwell
echo.
pause
