r"""Turbo worker; run ONLY with turbo-test\.venv Python. Requires existing float32 fixes."""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import soundfile as sf
from nebakov_voice_samples import line_reference
import torch
from chatterbox.tts_turbo import ChatterboxTurboTTS

ROOT = Path(r"D:\NebakovVoice")
CONVERSATIONS = (ROOT / "output" / "conversations").resolve()
CONFIG = json.loads((ROOT / "tts" / "tts_config.json").read_text(encoding="utf-8"))
PORT = int(os.environ.get("NEBAKOV_WORKER_PORT", "8767"))
LOCK = threading.Lock()
CACHE = {}


def render(folder, voicesampleid=None):
    folder = folder.resolve()
    if folder == CONVERSATIONS or not folder.is_relative_to(CONVERSATIONS):
        raise ValueError("Conversation folder must be inside output/conversations")
    lines = json.loads((folder / "conversation.json").read_text(encoding="utf-8"))["lines"]
    if not isinstance(lines, list) or not 1 <= len(lines) <= 30:
        raise ValueError("Expected 1 to 30 dialogue lines")
    for line in lines:
        if not isinstance(line, dict) or line.get("speaker") not in CONFIG["voices"] or not isinstance(line.get("text"), str) or not 1 <= len(line["text"]) <= 600:
            raise ValueError("Invalid dialogue line")
    references = [line_reference(ROOT/"tts/voices",line,voicesampleid) for line in lines]
    output = folder / "chatterbox"
    output.mkdir(exist_ok=True)
    result = []
    for index, line in enumerate(lines, 1):
        speaker = line["speaker"]
        voice = CONFIG["voices"][speaker]
        ref = references[index-1] or ROOT / voice["turbo"]
        if not ref.is_file():
            raise FileNotFoundError(f"Turbo voice reference missing: {ref}")
        if sf.info(str(ref)).duration <= 5.0:
            raise ValueError(f"Turbo reference must exceed 5 seconds: {ref}")
        stat = ref.stat()
        key = (str(ref.resolve()), stat.st_size, stat.st_mtime_ns, voice.get("exaggeration", 0.5))
        started = time.perf_counter()
        with torch.inference_mode():
            if key not in CACHE:
                MODEL.prepare_conditionals(str(ref), exaggeration=voice.get("exaggeration", 0.5))
                CACHE[key] = MODEL.conds
                print(f"[TurboVoice] prepared {speaker}", flush=True)
            else:
                MODEL.conds = CACHE[key]
                print(f"[TurboVoice] cache HIT {speaker}", flush=True)
            # Pass no audio_prompt_path: generate uses conditionals prepared above.
            wav = MODEL.generate(line["text"]).detach().cpu()
        if wav.ndim == 1:
            wav = wav.unsqueeze(0)
        sr = MODEL.sr
        wav = torch.cat((torch.zeros((wav.shape[0], int(sr * 0.3))), wav, torch.zeros((wav.shape[0], int(sr * 0.5)))), dim=-1)
        name = f"{index:02d}_{speaker.lower()}.wav"
        sf.write(str(output / name), wav.T.contiguous().numpy(), sr, subtype="PCM_16")
        result.append({"file": f"chatterbox/{name}", "seconds": round(time.perf_counter()-started, 2)})
        print(f"[Turbo] {speaker}: {name} ({result[-1]['seconds']}s)", flush=True)
    return result


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.reply(200, {"status": "ready", "model": "turbo", "device": DEVICE}) if self.path == "/health" else self.reply(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/render":
            return self.reply(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                raise ValueError("Invalid request size")
            request = json.loads(self.rfile.read(length))
            relative = request.get("conversation_folder")
            if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
                raise ValueError("Use a relative conversation folder")
            with LOCK:
                result = render(CONVERSATIONS / relative, request.get("voicesampleid"))
            self.reply(200, {"status": "ok", "audio": result})
        except (ValueError, KeyError, FileNotFoundError) as exc:
            self.reply(400, {"error": str(exc)})
        except Exception as exc:
            print(f"[Turbo] ERROR: {exc}", flush=True)
            self.reply(500, {"error": str(exc)})


if __name__ == "__main__":
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    MODEL = ChatterboxTurboTTS.from_pretrained(device=DEVICE)
    print(f"[Turbo] Ready on 127.0.0.1:{PORT} ({DEVICE})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
