"""Real installed pygame + manifest + supervisor smoke test on SDL dummy audio.

Synthetic game log; no game or Gemini request. Real WAVs are decoded and timed.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from nebakov_voice_playback import load_manifest
from nebakov_voice_runtime import latest_manifest


def main():
    server = Path(r"D:\NebakovVoice\server")
    manifest = latest_manifest()
    lines = load_manifest(manifest)
    hashes = {line.path: hashlib.sha256(line.path.read_bytes()).hexdigest() for line in lines}
    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
        folder = Path(temp)
        game_log, console = folder / "game.log", folder / "console.log"
        game_log.write_bytes(b"old log\n")
        env = {**os.environ, "SDL_AUDIODRIVER": "dummy", "PYGAME_HIDE_SUPPORT_PROMPT": "1"}
        with console.open("w", encoding="utf-8") as output:
            process = subprocess.Popen([str(server / ".venv/Scripts/python.exe"), "-B", "-u",
                str(server / "nebakov_voice_runtime.py"), "--manifest", str(manifest),
                "--engine-dir", str(folder), "--output-dir", str(folder), "--game-log", str(game_log),
                "--manual", "--once"], stdout=output, stderr=subprocess.STDOUT, env=env)
        try:
            started, sequence = time.monotonic(), 0
            while "READY:" not in console.read_text(encoding="utf-8"):
                if process.poll() is not None or time.monotonic() - started > 15:
                    raise RuntimeError(console.read_text(encoding="utf-8"))
                time.sleep(0.05)
            while process.poll() is None:
                sequence += 1
                p = {"protocol": "nebakov_voice.v1", "session": "synthetic_audio_smoke", "seq": sequence,
                    "event": "conversation_requested" if sequence == 2 else "positions",
                    "game_time": sequence * 0.25,
                    "player": {"name": "Henry", "available": True,
                               "position": {"x": 0, "y": 0, "z": 0},
                               "forward": {"x": 0, "y": 1 if sequence < 12 else -1, "z": 0}},
                    "npcs": [{"name": name, "entity_name": "smoke_" + name, "available": True,
                              "position": {"x": i * 2 - 1, "y": 1, "z": 0}}
                             for i, name in enumerate(["Marek", "Hertl"])]}
                with game_log.open("ab") as stream:
                    stream.write(b"NEBAKOV_VOICE_V1 " + json.dumps(p).encode() + b"\n")
                if time.monotonic() - started > sum(l.seconds for l in lines) + 15:
                    raise RuntimeError("Smoke playback timed out: " + console.read_text(encoding="utf-8"))
                time.sleep(0.25)
            if process.returncode:
                raise RuntimeError(console.read_text(encoding="utf-8"))
            events = [json.loads(line) for line in (folder / "bridge_events.jsonl").read_text().splitlines()]
            spoken = [e["speaker"] for e in events if e["event"] == "line_started"]
            assert spoken == ["Marek", "Hertl", "Marek", "Hertl"], spoken
            assert len([e for e in events if e["event"] == "line_finished"]) == 4
            assert any(e["event"] == "conversation_finished" for e in events)
            assert json.loads((folder / "latest_positions.json").read_text())["status"] == "runtime_stopped"
            for path, digest in hashes.items():
                assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
            print("PASS: installed runtime, real four WAVs, real pygame dummy mixer, ordered completion, camera updates, archived files preserved.")
            print("Synthetic telemetry only; this does not confirm in-game audibility.")
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
