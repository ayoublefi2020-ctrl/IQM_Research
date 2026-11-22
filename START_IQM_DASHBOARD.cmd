@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Missing .venv. Follow README_WINDOWS.md to install the dependencies.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" dashboard\launch.py
if errorlevel 1 pause
