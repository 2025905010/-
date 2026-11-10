@echo off
cd /d "%~dp0"
if "%TELEGRAM_BOT_TOKEN%"=="" (
  echo TELEGRAM_BOT_TOKEN environment variable is not set.
  echo From Windows CMD: set TELEGRAM_BOT_TOKEN=YOUR_ACTUAL_TOKEN
  pause
  exit /b 1
)
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe bot.py
) else (
  python bot.py
)
pause
