@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (echo Install Python 3.11 or newer from python.org and enable Add to PATH.& pause & exit /b 1)
if not exist .venv py -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 (echo Dependency install failed.& pause & exit /b 1)
echo.
echo Open http://127.0.0.1:5000/setup in your browser
python -m waitress --listen=127.0.0.1:5000 app:app
pause
