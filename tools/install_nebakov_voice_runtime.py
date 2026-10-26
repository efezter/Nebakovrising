"""Install only bridge files into NebakovVoice; preserve all existing engine code."""
from datetime import datetime
import hashlib
from pathlib import Path
import shutil
import json

ROOT = Path(__file__).resolve().parents[1]
SERVER = Path(r"D:\NebakovVoice\server")
FILES = ["nebakov_voice_receiver.py", "nebakov_voice_playback.py",
         "nebakov_voice_engine_adapter.py", "nebakov_voice_runtime.py",
         "nebakov_voice_director.py", "start_patrol_conversations.cmd", "test_patrol_voices.cmd",
         "start_nebakov_voice.cmd", "test_existing_npc_voices.cmd", "nebakov_voice_samples.py",
         "nebakov_voice_config.py", "nebakov_voice_prompts.py",
         "nebakov_voice_defaults.py", "nebakov_voice_transport.py"]
ENGINE_FILES = ["conversation_engine.py", "config.py", "generate_dialogue.py", "offline-tts.py"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install():
    if not (SERVER / ".venv/Scripts/python.exe").is_file():
        raise RuntimeError("Existing NebakovVoice environment not found")
    before = {name: digest(SERVER / name) for name in ENGINE_FILES}
    from nebakov_voice_config import load_config
    from nebakov_voice_prompts import PromptProfiles
    config_root = SERVER.parent / "config"
    settings_file = config_root / "conversations.json"
    from nebakov_voice_defaults import ensure_defaults
    ensure_defaults(config_root)
    settings = load_config(settings_file)
    PromptProfiles(config_root / 'prompts').load(settings['profileId'])
    service = ROOT / "tools/tts_service"
    baseline = json.loads((service / "baseline_hashes.json").read_text())
    state_file = SERVER.parent / "tts/nebakov_voice_installed.json"
    installed = json.loads(state_file.read_text()) if state_file.exists() else {}
    for name, expected in baseline.items():
        current = SERVER.parent / "tts" / name
        allowed = expected if isinstance(expected, list) else [expected]
        if digest(current) not in [*allowed, digest(service / name), installed.get(name)]:
            raise RuntimeError(f"TTS file changed since integration staging: {name}")
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
    for name in [*baseline, "nebakov_voice_samples.py"]:
        source = service / name if name in baseline else ROOT / "tools" / name
        destination = SERVER.parent / "tts" / name
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            (backup / "tts").mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, backup / "tts" / name)
        temporary = destination.with_name(name + ".install.tmp")
        shutil.copyfile(source, temporary)
        temporary.replace(destination)
        if digest(source) != digest(destination): raise RuntimeError(f"TTS install mismatch: {name}")
    state_tmp = state_file.with_suffix(".json.tmp")
    state_tmp.write_text(json.dumps({name:digest(SERVER.parent/"tts"/name) for name in baseline},indent=2))
    state_tmp.replace(state_file)
    command = ROOT.parents[1] / "Data/Scripts/nebakov_voice/command.lua"
    command.parent.mkdir(parents=True, exist_ok=True)
    if not command.exists():
        command.write_text("-- NebakovVoice control channel; waiting for runtime.\n", encoding="ascii")
    print(f"Installed and hash-verified {len(FILES)} bridge files and TTS voice routing; engine/generation/model logic preserved.")
    print(f"Conversation settings: {settings_file}; existing JSON settings/profiles preserved.")
    if backup.exists():
        print(f"Previous bridge versions: {backup}")


if __name__ == "__main__":
    install()
