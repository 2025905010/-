@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (py -3 -m venv .venv) else (python -m venv .venv)
if errorlevel 1 (
  echo Failed to create virtual environment. Install Python 3.11 or later.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo Installation failed. Check your internet connection.
  pause
  exit /b 1
)
echo Installation completed. Run run_web.bat.
pause
