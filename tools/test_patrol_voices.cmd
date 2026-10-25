@echo off
setlocal
rem Lightweight playback bridge only; the separate TTS service owns generation.
"D:\NebakovVoice\server\.venv\Scripts\python.exe" -u "%~dp0nebakov_voice_runtime.py" --director --stale-after 4 --manifest latest %*
pause
