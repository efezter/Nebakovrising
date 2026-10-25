@echo off
setlocal
"D:\NebakovVoice\server\.venv\Scripts\python.exe" -u "%~dp0nebakov_voice_runtime.py" --director --stale-after 4 %*
pause
