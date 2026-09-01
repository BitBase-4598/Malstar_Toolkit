@echo off
cd /d "%~dp0frontend"
call npm.cmd install
if errorlevel 1 exit /b 1
call npm.cmd run build
if errorlevel 1 exit /b 1
cd /d "%~dp0backend"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
python -m pip install -r requirements.txt
set FLASK_HOST=0.0.0.0
set PORT=8080
set FLASK_DEBUG=false
echo.
echo MALSTAR_Toolkit is starting on http://0.0.0.0:8080 (waitress)
python app.py
