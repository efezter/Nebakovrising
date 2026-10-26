"""Persistent worker adapter; the existing conversation_engine stays unchanged."""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
import uuid
import urllib.request


def safe_error(error):
    detail = str(error)
    key = os.getenv("GEMINI_API_KEY")
    if key:
        detail = detail.replace(key, "[redacted]")
    return detail[:400]


def worker_main(commands, results, engine_dir: str, prewarm=False):
    sys.path.insert(0, engine_dir)
    try:
        import conversation_engine as engine
        if not os.getenv("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY is missing from the runtime environment")
        service = callable(getattr(engine, "render_with_chatterbox", None))
        if service:
            with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=5) as response:
                health = json.load(response)
                if health.get("status") != "ready":
                    raise RuntimeError("NebakovVoice TTS service is not ready")
            desired = os.environ.get("NEBAKOV_TTS_MODEL") or health.get("default_model", "turbo")
            if prewarm and health.get("active_model") != desired:
                print("[Bridge] Preparing existing TTS service model before conversations...", flush=True)
                request = urllib.request.Request("http://127.0.0.1:8765/model/switch",
                    data=json.dumps({"model":desired}).encode(),headers={"Content-Type":"application/json"},method="POST")
                with urllib.request.urlopen(request,timeout=180) as response:
                    if json.load(response).get("status")!="ok": raise RuntimeError("TTS model preparation failed")
            tts = None  # Model ownership stays entirely in the existing service.
        else:
            tts = engine.create_tts()
        results.put({"kind": "ready", "backend": "tts_service" if service else "kokoro"})
    except Exception as error:
        results.put({"kind": "fatal", "error": type(error).__name__, "detail": safe_error(error)})
        return
    while True:
        job = commands.get()
        if job is None:
            return
        try:
            lines = engine.generate_conversation("Marek", "Hertl", job["context"], line_count=4)
            folder = Path(engine.OUTPUT_DIR) / (
                datetime.now().strftime("nebakov_%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:12])
            folder.mkdir(parents=True, exist_ok=False)
            manifest_lines = []
            for index, line in enumerate(lines, 1):
                speaker, text = line["speaker"], line["text"]
                filename = ("chatterbox/" if service else "") + f"{index:02d}_{speaker.lower()}.wav"
                manifest_lines.append({"index": index, "speaker": speaker, "text": text,
                                       "audio_file": filename})
                if job.get("voicesampleid", {}).get(speaker):
                    manifest_lines[-1]["voicesampleid"] = job["voicesampleid"][speaker]
                if not service:
                    voice_id = engine.NPCS[speaker]["voice_id"]
                    elapsed = engine.generate_audio(tts, text, folder / filename, voice_id)
                    manifest_lines[-1].update(voice_id=voice_id, generation_seconds=round(elapsed, 2))
            document = {"location": "Nebakov Castle", "model": engine.GEMINI_MODEL,
                        "context": job["context"], "lines": manifest_lines,
                        "bridge_job_id": job["id"], "bridge_session": job["session"]}
            if job.get("profile_id"):
                document.update(profile_id=job["profile_id"], prompt_parameters=job.get("prompt_parameters"))
            temporary = folder / "conversation.json.tmp"
            temporary.write_text(json.dumps(document, indent=2, ensure_ascii=True), encoding="utf-8")
            manifest = folder / "conversation.json"
            temporary.replace(manifest)
            if service:
                samples = job.get("voicesampleid")
                if samples:
                    body = {"conversation_folder":folder.name, "voicesampleid":samples}
                    if os.environ.get("NEBAKOV_TTS_MODEL"): body["model"]=os.environ["NEBAKOV_TTS_MODEL"]
                    request = urllib.request.Request("http://127.0.0.1:8765/render", data=json.dumps(body).encode(),
                        headers={"Content-Type":"application/json"}, method="POST")
                    with urllib.request.urlopen(request,timeout=600) as response:
                        if json.load(response).get("status")!="ok": raise RuntimeError("TTS service rendering failed")
                else:
                    engine.render_with_chatterbox(folder)
            from nebakov_voice_playback import load_manifest
            load_manifest(manifest)  # Never publish a missing/partial audio result.
            results.put({"kind": "result", "id": job["id"], "manifest": str(manifest)})
        except Exception as error:
            # Do not include request bodies/URLs or credentials in bridge logs.
            results.put({"kind": "error", "id": job["id"],
                         "error": type(error).__name__ + ": " + safe_error(error)})
