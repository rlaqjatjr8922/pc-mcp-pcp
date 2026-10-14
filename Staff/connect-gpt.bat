@echo off
setlocal
cd /d "%~dp0"
if /I "%~1"=="--background" (
  if not exist "%~dp0mane\dat\tunnel" mkdir "%~dp0mane\dat\tunnel"
  start "" /b "%~dp0mane\.venv\Scripts\pythonw.exe" "%~dp0mane\cor\_runtime\launch_gpt.py" --background
  exit /b
)
if /I "%~1"=="--check" (
  "%~dp0mane\.venv\Scripts\python.exe" "%~dp0mane\cor\_runtime\launch_gpt.py" --check
  exit /b
)
start "" "%~dp0mane\.venv\Scripts\python.exe" "%~dp0mane\cor\_runtime\launch_gpt.py" %*
exit /b
