"""Validated data-only configuration sent to Lua through the acknowledged bridge."""
import json
import math
from pathlib import Path
import re

PROFILE_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
FIELDS = ("enabled", "randomEnabled", "searchRadius",
          "randomMinSeconds", "randomMaxSeconds", "cooldownSeconds", "npcCooldownSeconds",
          "prepareBeforeMeeting", "generationTimeout", "nearbyDistance")
BOOLS = {"enabled", "randomEnabled", "prepareBeforeMeeting"}
DEFAULT_CONFIG = Path(r"D:\NebakovVoice\config\conversations.json")

def validate(settings):
    if not isinstance(settings, dict) or settings.get("version") != 1:
        raise ValueError("Conversation config requires version 1")
    unknown=set(settings)-set(FIELDS)-{"version","profileId","prewarmModel","patrolStartHour","patrolEndHour"}
    if unknown: raise ValueError("Unknown conversation config keys: " + ", ".join(sorted(unknown)))
    settings = dict(settings)
    settings.setdefault('nearbyDistance', 2)
    if not isinstance(settings.get("profileId"), str) or not PROFILE_ID.fullmatch(settings["profileId"]):
        raise ValueError("Invalid conversation profileId")
    for name in FIELDS:
        value = settings.get(name)
        if name in BOOLS:
            if type(value) is not bool: raise ValueError(f"{name} must be boolean")
        elif type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number")
    settings.pop('patrolStartHour', None)
    settings.pop('patrolEndHour', None)
    if not 0.5 <= settings['nearbyDistance'] <= 5: raise ValueError('nearbyDistance must be within 0.5..5 metres')
    if not 1 <= settings["searchRadius"] <= 100: raise ValueError("searchRadius must be within 1..100 metres")
    if not 1 <= settings["randomMinSeconds"] <= settings["randomMaxSeconds"] <= 86400:
        raise ValueError("Invalid random interval")
    for name in ("randomMinSeconds", "randomMaxSeconds"):
        if settings[name] != int(settings[name]): raise ValueError(f"{name} must be whole seconds")
    for name in ("cooldownSeconds", "npcCooldownSeconds"):
        if not 0 <= settings[name] <= 86400: raise ValueError(f"Invalid {name}")
    if not 15 <= settings["generationTimeout"] <= 600: raise ValueError("generationTimeout must be within 15..600 seconds")
    if type(settings.get("prewarmModel", True)) is not bool: raise ValueError("prewarmModel must be boolean")
    return dict(settings)

def load_config(path=DEFAULT_CONFIG):
    path = Path(path)
    if path.stat().st_size > 32768: raise ValueError("Conversation config exceeds 32 KB")
    return validate(json.loads(path.read_text(encoding="utf-8-sig")))

def encode_settings(settings):
    settings = validate(settings)
    return ",".join(str(int(settings[k])) if k in BOOLS else format(settings[k], ".12g") for k in FIELDS), settings["profileId"]

def validate_payload(csv, profile):
    if not isinstance(csv, str) or len(csv) > 512: raise ValueError("Invalid conversation settings payload")
    try: values = [float(v) for v in csv.split(",")]
    except ValueError: raise ValueError("Invalid settings numbers") from None
    if len(values) != len(FIELDS): raise ValueError("Invalid settings field count")
    settings = {"version":1, "profileId":profile}
    for key, value in zip(FIELDS, values):
        if key in BOOLS:
            if value not in (0, 1): raise ValueError("Invalid settings boolean")
            value = bool(value)
        settings[key] = value
    return validate(settings)
