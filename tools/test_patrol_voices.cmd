@echo off
setlocal
rem Lightweight playback bridge only; the separate TTS service owns generation.
echo Ready-audio test: requires an existing completed conversation.
echo If the output folder is empty, use start_patrol_conversations.cmd instead.
"D:\NebakovVoice\server\.venv\Scripts\python.exe" -u "%~dp0nebakov_voice_runtime.py" --director --stale-after 4 --manifest latest %*
pause
