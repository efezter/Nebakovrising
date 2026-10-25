"""Sequential positional WAV playback. Keeps original conversation files intact.

Spatial playback follows the position-provider pattern in KRYSYS1/KCD2.AI.NPC.
This implementation uses its own mixer/state code and equal-power stereo gains.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import wave


@dataclass(frozen=True)
class Line:
    index: int
    speaker: str
    text: str
    path: Path
    seconds: float
    rate: int


def load_manifest(path: Path) -> list[Line]:
    path = path.resolve(strict=True)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("Manifest exceeds 1 MB")
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = document.get("lines")
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError("Expected exactly four conversation lines")
    if any(not isinstance(r, dict) or type(r.get("index")) is not int for r in rows):
        raise ValueError("Invalid line index")
    rows = sorted(rows, key=lambda r: r["index"])
    result = []
    for index, row in enumerate(rows, 1):
        if row["index"] != index or row.get("speaker") != ("Marek" if index % 2 else "Hertl"):
            raise ValueError("Expected alternating Marek/Hertl lines with indices 1..4")
        filename = row.get("audio_file")
        if not isinstance(filename, str) or not filename:
            raise ValueError("Missing audio_file")
        audio = (path.parent / filename).resolve(strict=True)
        if not audio.is_relative_to(path.parent) or audio.suffix.lower() != ".wav":
            raise ValueError("WAV must be inside the conversation folder")
        if audio.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("WAV exceeds 32 MB")
        with wave.open(str(audio), "rb") as wav:
            seconds = wav.getnframes() / wav.getframerate()
            if (wav.getnchannels() != 1 or wav.getsampwidth() != 2 or
                    wav.getcomptype() != "NONE" or not 0 < seconds <= 100):
                raise ValueError("Expected mono PCM16 WAV, at most 100 seconds")
            result.append(Line(index, row["speaker"], str(row.get("text", "")),
                               audio, seconds, wav.getframerate()))
    return result


def spatial_gains(npc: dict, player: dict, forward: dict | None,
                  volume: float = 0.85, max_distance: float = 24.0) -> tuple[float, float]:
    dx, dy, dz = (npc[a] - player[a] for a in ("x", "y", "z"))
    distance = math.sqrt(dx * dx + dy * dy + dz * dz)
    if distance >= max_distance:
        return 0.0, 0.0
    horizontal = math.hypot(dx, dy)
    pan, front = 0.0, 1.0
    if forward and horizontal > 0.001:
        length = math.hypot(forward["x"], forward["y"])
        if length > 0.001:
            fx, fy = forward["x"] / length, forward["y"] / length
            pan = max(-1.0, min(1.0, (dx * fy - dy * fx) / horizontal))
            front = (dx * fx + dy * fy) / horizontal
    # Full gain within 2 m, inverse-square-like falloff, then fade to silence.
    attenuation = 1.0 / (1.0 + (max(0.0, distance - 2.0) / 6.0) ** 2)
    attenuation *= min(1.0, (max_distance - distance) / 4.0)
    gain = volume * attenuation * (1.0 + min(0.0, front) * 0.25)
    angle = (pan + 1.0) * math.pi / 4.0
    return gain * math.cos(angle), gain * math.sin(angle)


class PygameAudio:
    """One dedicated stereo channel. All access is on the supervisor thread."""
    def __init__(self):
        import pygame
        self.pg = pygame
        pygame.mixer.init(frequency=24000, size=-16, channels=2, buffer=512)
        self.channel = pygame.mixer.Channel(0)
        self.sound = None

    def play(self, line: Line, gains: tuple[float, float]):
        self.sound = self.pg.mixer.Sound(str(line.path))
        # The stereo mixer converts mono WAV sources to stereo on load.
        import pygame.sndarray
        if pygame.sndarray.array(self.sound).ndim != 2:
            raise RuntimeError("Stereo mixer conversion failed")
        self.channel.set_volume(*gains)
        self.channel.play(self.sound)

    def update(self, gains):
        self.channel.set_volume(*gains)

    def is_busy(self):
        return self.channel.get_busy()

    def stop(self):
        self.channel.stop()
        self.sound = None

    def close(self):
        self.stop()
        self.pg.mixer.quit()


class SequentialPlayback:
    def __init__(self, audio, emit, volume=0.85, max_distance=24.0):
        self.audio, self.emit = audio, emit
        self.volume, self.max_distance = volume, max_distance
        self.lines = []
        self.current = None
        self.before_line = None
        self.after_line = None

    def start(self, manifest: Path):
        self.stop()
        self.lines = load_manifest(manifest)

    def stop(self):
        self.audio.stop()
        self.lines, self.current = [], None

    def tick(self, packet: dict) -> bool:
        if self.current and not self.audio.is_busy():
            self.emit("line_finished", index=self.current.index, speaker=self.current.speaker)
            if self.after_line:
                self.after_line(self.current)
            self.current = None
        starting = self.current is None
        if starting:
            if not self.lines:
                return False
            if self.before_line and not self.before_line(self.lines[0]):
                return True
            self.current = self.lines.pop(0)
        npc = next(n for n in packet["npcs"] if n["name"] == self.current.speaker)
        player = packet["player"]
        gains = spatial_gains(npc["position"], player["position"], player.get("forward"),
                              self.volume, self.max_distance)
        if starting:
            self.audio.play(self.current, gains)
            self.emit("line_started", index=self.current.index, speaker=self.current.speaker,
                      seconds=self.current.seconds, entity_name=npc["entity_name"])
        else:
            self.audio.update(gains)
        return True
