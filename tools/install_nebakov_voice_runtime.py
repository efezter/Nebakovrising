"""Install only bridge files into NebakovVoice; preserve all existing engine code."""
from datetime import datetime
import hashlib
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SERVER = Path(r"D:\NebakovVoice\server")
FILES = ["nebakov_voice_receiver.py", "nebakov_voice_playback.py",
         "nebakov_voice_engine_adapter.py", "nebakov_voice_runtime.py",
         "nebakov_voice_director.py", "start_patrol_conversations.cmd", "test_patrol_voices.cmd",
         "start_nebakov_voice.cmd", "test_existing_npc_voices.cmd"]
ENGINE_FILES = ["conversation_engine.py", "config.py", "generate_dialogue.py", "offline-tts.py"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install():
    if not (SERVER / ".venv/Scripts/python.exe").is_file():
        raise RuntimeError("Existing NebakovVoice environment not found")
    before = {name: digest(SERVER / name) for name in ENGINE_FILES}
    backup = SERVER / "bridge_backups" / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    for name in FILES:
        source, destination = ROOT / "tools" / name, SERVER / name
        if destination.exists() and source.read_bytes() != destination.read_bytes():
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, backup / name)
        temporary = destination.with_name(destination.name + ".install.tmp")
        shutil.copyfile(source, temporary)
        temporary.replace(destination)
        if digest(source) != digest(destination):
            raise RuntimeError(f"Install mismatch: {name}")
    after = {name: digest(SERVER / name) for name in ENGINE_FILES}
    if before != after:
        raise RuntimeError("Engine files changed during installation")
    command = ROOT.parents[1] / "Data/Scripts/nebakov_voice/command.lua"
    command.parent.mkdir(parents=True, exist_ok=True)
    if not command.exists():
        command.write_text("-- NebakovVoice control channel; waiting for runtime.\n", encoding="ascii")
    print(f"Installed and hash-verified {len(FILES)} bridge files; engine/TTS files unchanged.")
    if backup.exists():
        print(f"Previous bridge versions: {backup}")


if __name__ == "__main__":
    install()
