@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo NebakovVoice virtual environment not found in this directory.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -u "%~dp0nebakov_voice_receiver.py"
pause
