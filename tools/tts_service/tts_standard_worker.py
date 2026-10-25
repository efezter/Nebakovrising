"""Persistent local Chatterbox service with per-voice conditioning cache.

Run with D:\\NebakovVoice\\tts\\.venv\\Scripts\\python.exe tts_server.py
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import torch
import torchaudio
from chatterbox.tts import ChatterboxTTS
import soundfile as sf
from nebakov_voice_samples import line_reference

print(f"[DEBUG] Running TTS server: {__file__}", flush=True)
print("[DEBUG] Voice cache version loaded", flush=True)

ROOT = Path(r"D:\NebakovVoice")
CONVERSATIONS = (ROOT / "output" / "conversations").resolve()
VOICES = ROOT / "tts" / "voices"
HOST, PORT = "127.0.0.1", int(os.environ.get("NEBAKOV_WORKER_PORT", "8766"))
SETTINGS = {
    "Marek": {"reference": VOICES / "marek.wav", "exaggeration": 0.55, "cfg_weight": 0.3},
    "Hertl": {"reference": VOICES / "hertl.wav", "exaggeration": 0.65, "cfg_weight": 0.3},
}
LOCK = threading.Lock()
VOICE_CACHE = {}


def activate_voice(model, speaker, reference_path=None):
    """Select cached conditioning for speaker, preparing it only when needed."""
    if not callable(getattr(model, "prepare_conditionals", None)) or not hasattr(model, "conds"):
        raise RuntimeError("This Chatterbox version lacks prepare_conditionals/conds; check installed API")

    reference = reference_path or SETTINGS[speaker]["reference"]
    if not reference.is_file():
        raise FileNotFoundError(f"Missing reference audio for {speaker}: {reference}")

    stat = reference.stat()
    key = (str(reference.resolve()), stat.st_mtime_ns, stat.st_size)
    if key in VOICE_CACHE:
        model.conds = VOICE_CACHE[key]
        print(f"[VoiceCache] HIT {speaker}", flush=True)
        return

    start = time.perf_counter()
    print(f"[VoiceCache] MISS {speaker}; preparing {reference.name}", flush=True)
    model.prepare_conditionals(str(reference))
    if model.conds is None:
        raise RuntimeError(f"Chatterbox returned no conditioning for {speaker}")

    # Keep only the newest version of this reference file in the cache.
    path = key[0]
    for old_key in list(VOICE_CACHE):
        if old_key[0] == path and old_key != key:
            del VOICE_CACHE[old_key]
    VOICE_CACHE[key] = model.conds
    print(f"[VoiceCache] STORED {speaker} in {time.perf_counter() - start:.2f}s", flush=True)


def render(folder: Path, model, voicesampleid=None):
    render_start = time.perf_counter()
    folder = folder.resolve()
    if not folder.is_relative_to(CONVERSATIONS) or folder == CONVERSATIONS:
        raise ValueError("Conversation folder must be inside output/conversations")

    with (folder / "conversation.json").open(encoding="utf-8") as f:
        document = json.load(f)
    lines = document["lines"]
    if not isinstance(lines, list) or not 1 <= len(lines) <= 30:
        raise ValueError("Expected 1 to 30 dialogue lines")

    # Validate all lines before generating any files.
    for index, line in enumerate(lines, 1):
        if not isinstance(line, dict):
            raise ValueError(f"Invalid line {index}")
        speaker, dialogue = line.get("speaker"), line.get("text")
        if speaker not in SETTINGS or not isinstance(dialogue, str) or not 1 <= len(dialogue) <= 600:
            raise ValueError(f"Invalid line {index}")

    references = [line_reference(VOICES,line,voicesampleid) for line in lines]
    output = folder / "chatterbox"
    output.mkdir(exist_ok=True)
    rendered = []

    for index, line in enumerate(lines, 1):
        speaker, dialogue = line["speaker"], line["text"]
        config = SETTINGS[speaker]
        line_start = time.perf_counter()

        with torch.inference_mode():
            activate_voice(model, speaker, references[index-1])
            wav = model.generate(
                dialogue,
                exaggeration=config["exaggeration"],
                cfg_weight=config["cfg_weight"],
            ).detach().cpu()

        if wav.ndim == 1:
            wav = wav.unsqueeze(0)
        sr = model.sr
        wav = torch.cat(
            (
                torch.zeros((wav.shape[0], int(sr * 0.3)), dtype=wav.dtype),
                wav,
                torch.zeros((wav.shape[0], int(sr * 0.5)), dtype=wav.dtype),
            ),
            dim=-1,
        )
        filename = f"{index:02d}_{speaker.lower()}.wav"
        sf.write(
            str(output / filename),
            wav.transpose(0, 1).contiguous().numpy(),
            sr,
            subtype="PCM_16"
        )
        elapsed = time.perf_counter() - line_start
        rendered.append({"file": f"chatterbox/{filename}", "seconds": round(elapsed, 2)})
        print(f"[TTS] [{index}/{len(lines)}] {speaker}: {filename} ({elapsed:.2f}s)", flush=True)

    print(f"[TTS] Total render: {time.perf_counter() - render_start:.2f}s", flush=True)
    return rendered


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, obj):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self.reply(200, {"status": "ready", "device": DEVICE, "cached_voices": len(VOICE_CACHE)})
        else:
            self.reply(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/render":
            return self.reply(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                return self.reply(413, {"error": "Invalid request size"})
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict):
                raise ValueError("Request must be a JSON object")
            relative = request.get("conversation_folder")
            if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
                raise ValueError("Use a relative conversation folder name")
            folder = CONVERSATIONS / relative
            with LOCK:
                result = render(folder, MODEL, request.get("voicesampleid"))
            self.reply(200, {"status": "ok", "audio": result})
        except (ValueError, KeyError, FileNotFoundError, json.JSONDecodeError) as exc:
            self.reply(400, {"error": str(exc)})
        except Exception as exc:
            print(f"Render error: {exc}", flush=True)
            self.reply(500, {"error": str(exc)})


if __name__ == "__main__":
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading Chatterbox on {DEVICE}...", flush=True)
    MODEL = ChatterboxTTS.from_pretrained(device=DEVICE)
    if not callable(getattr(MODEL, "prepare_conditionals", None)) or not hasattr(MODEL, "conds"):
        raise RuntimeError("Installed Chatterbox version does not support the conditioning cache API")
    print(f"Ready at http://{HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
