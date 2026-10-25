@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo NebakovVoice Python environment not found beside this launcher.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -u nebakov_voice_runtime.py %*
pause
