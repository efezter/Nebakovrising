"""Single public API (8765); lazily starts one isolated worker at a time."""
import json
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(r"D:\NebakovVoice")
CONFIG_FILE = ROOT / "tts" / "tts_config.json"
LOCK = threading.RLock()
STATE = {"model": None, "process": None}


def config():
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def worker_url(model):
    return f"http://127.0.0.1:{config()['workers'][model]}"


def request_json(url, payload=None, timeout=10):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def ensure_worker(model):
    if model not in config()["workers"]:
        raise ValueError(f"Unknown TTS model: {model}")
    if STATE["model"] == model and STATE["process"] and STATE["process"].poll() is None:
        return
    if STATE["process"] is not None:
        old = STATE["process"]
        old.terminate()
        try:
            old.wait(timeout=15)
        except subprocess.TimeoutExpired:
            old.kill()
            old.wait()
        STATE.update(model=None, process=None)
    if model == "standard":
        python = ROOT / "tts" / ".venv" / "Scripts" / "python.exe"
        script = ROOT / "tts" / "tts_standard_worker.py"
    else:
        python = ROOT / "turbo-test" / ".venv" / "Scripts" / "python.exe"
        script = ROOT / "tts" / "tts_turbo_worker.py"
    if not python.is_file() or not script.is_file():
        raise FileNotFoundError(f"Worker executable or script missing: {python}, {script}")
    print(f"[Router] Starting {model} worker...", flush=True)
    import os
    env = os.environ.copy()
    env["NEBAKOV_WORKER_PORT"] = str(config()["workers"][model])
    proc = subprocess.Popen([str(python), "-u", str(script)], cwd=str(ROOT), env=env)
    STATE.update(model=model, process=proc)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            STATE.update(model=None, process=None)
            raise RuntimeError(f"{model} worker exited with code {proc.returncode}")
        try:
            if request_json(worker_url(model) + "/health", timeout=2).get("status") == "ready":
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.5)
    proc.terminate()
    STATE.update(model=None, process=None)
    raise TimeoutError(f"{model} worker startup timed out")


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        # A client can close/restart while inference is running. Once a response
        # starts, never try to send a second HTTP response on that connection.
        if getattr(self, "_reply_started", False):
            return False
        raw = json.dumps(data).encode("utf-8")
        self._reply_started = True
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        except (ConnectionError, TimeoutError) as exc:
            self.close_connection = True
            print(f"[Router] Client disconnected; HTTP {status} response not delivered: {type(exc).__name__}", flush=True)
            return False
        return True

    def do_GET(self):
        self._reply_started = False
        if self.path != "/health":
            return self.reply(404, {"error": "Not found"})
        self.reply(200, {"status": "ready", "default_model": config()["default_model"], "active_model": STATE["model"]})

    def do_POST(self):
        self._reply_started = False
        if self.path not in ("/render", "/model/switch"):
            return self.reply(404, {"error": "Not found"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 8192:
                return self.reply(413, {"error": "Invalid request size"})
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            with LOCK:
                model = payload.get("model", config()["default_model"])
                if model not in config()["workers"]:
                    raise ValueError("model must be 'standard' or 'turbo'")
                if self.path == "/model/switch":
                    ensure_worker(model)
                    return self.reply(200, {"status": "ok", "active_model": model})
                samples = payload.get("voicesampleid", {})
                from nebakov_voice_samples import valid_name
                if not isinstance(samples, dict) or any(k not in ("Marek","Hertl") or not valid_name(v) for k,v in samples.items()):
                    raise ValueError("Invalid voicesampleid mapping")
                folder = payload.get("conversation_folder")
                if not isinstance(folder, str) or not folder or Path(folder).is_absolute():
                    raise ValueError("conversation_folder must be relative")
                ensure_worker(model)
                try:
                    result = request_json(worker_url(model) + "/render", {"conversation_folder": folder, "voicesampleid":samples}, timeout=600)
                    return self.reply(200, {**result, "model": model})
                except urllib.error.HTTPError as exc:
                    body = exc.read().decode("utf-8", errors="replace")
                    return self.reply(exc.code, {"error": body, "model": model})
        except (ValueError, FileNotFoundError) as exc:
            self.reply(400, {"error": str(exc)})
        except Exception as exc:
            print(f"[Router] ERROR: {exc}", flush=True)
            self.reply(500, {"error": str(exc)})


if __name__ == "__main__":
    print("[Router] Ready at http://127.0.0.1:8765", flush=True)
    try:
        ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
    finally:
        if STATE["process"] and STATE["process"].poll() is None:
            STATE["process"].terminate()
