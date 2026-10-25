"""Filename-based voice catalog shared by the bridge and TTS workers."""
from pathlib import Path
import re

SAMPLE_NAME = re.compile(r"guard[A-Za-z0-9_-]*\.wav\Z", re.I)

def valid_name(name):
    return isinstance(name, str) and len(name) <= 80 and SAMPLE_NAME.fullmatch(name) is not None

def reference(root, name):
    if not valid_name(name):
        raise ValueError("Invalid voicesampleid; use a guard*.wav filename")
    root = Path(root).resolve(strict=True)
    path = (root / name).resolve(strict=True)
    if path.parent != root:
        raise ValueError("Voice sample must be directly inside tts/voices")
    import soundfile as sf
    seconds = sf.info(str(path)).duration
    if seconds <= 5:
        raise ValueError(f"Voice reference must exceed 5 seconds: {name} ({seconds:.2f}s)")
    return path

def discover(root):
    root = Path(root)
    ids, rejected = [], {}
    for path in root.iterdir():
        if not path.is_file() or not valid_name(path.name): continue
        try: reference(root, path.name)
        except (OSError, ValueError, RuntimeError) as error: rejected[path.name] = str(error)
        else: ids.append(path.name)
    ids.sort(key=lambda s: [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", s)])
    if len(ids) > 128: raise ValueError("Guard catalog supports at most 128 samples")
    for name in rejected:
        if name.lower() == "guard1.wav": raise ValueError(rejected[name])
    if not ids: raise ValueError("No guard*.wav samples longer than 5 seconds in tts/voices")
    return {"ids": ids, "fallback": next((n for n in ids if n.lower()=="guard1.wav"), ids[0]), "rejected": rejected}

def line_reference(root, line, requested=None):
    requested = requested or {}
    if not isinstance(requested, dict) or any(k not in {"Marek", "Hertl"} for k in requested):
        raise ValueError("voicesampleid must map Marek/Hertl to sample filenames")
    explicit, saved = requested.get(line["speaker"]), line.get("voicesampleid")
    if explicit is not None and saved is not None and explicit != saved:
        raise ValueError("Request and manifest voicesampleid disagree")
    sample = explicit if explicit is not None else saved
    return reference(root, sample) if sample is not None else None
