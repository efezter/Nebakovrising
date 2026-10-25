"""Milestone 1: read structured KCD2 log telemetry. No Gemini, TTS or playback.

The game uses its existing System.LogAlways binding; only this external process
opens files. Start the receiver before binding the two NPCs in-game.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time

MARKER = b"NEBAKOV_VOICE_V1 "
PROTOCOL = "nebakov_voice.v1"
SPEAKERS = {"Marek", "Hertl"}
EVENTS = {"positions", "conversation_trigger", "conversation_requested", "bridge_stopped", "world_reset", "director_status"}
DEFAULT_LOG = Path(r"C:\Program Files (x86)\Steam\steamapps\common\KingdomComeDeliverance2\kcd.log")
DEFAULT_OUTPUT = Path(r"D:\NebakovVoice\output\bridge")


class LogTail:
    """Bounded incremental reads; support partial lines, truncation and replacement."""
    def __init__(self, path: Path, from_start: bool = False, include_exit: bool = False):
        self.path = path
        self.from_start = from_start
        self.include_exit = include_exit
        self.offset = None
        self.identity = None
        self.anchor = b""
        self.pending = b""

    def poll(self) -> list[bytes]:
        try:
            with self.path.open("rb") as stream:
                stat = os.fstat(stream.fileno())
                identity = stat.st_dev, stat.st_ino
                if self.offset is None:
                    self.offset = 0 if self.from_start else stat.st_size
                elif identity != self.identity or stat.st_size < self.offset:
                    self.offset, self.pending, self.anchor = 0, b"", b""
                elif self.anchor:
                    stream.seek(self.offset - len(self.anchor))
                    if stream.read(len(self.anchor)) != self.anchor:
                        self.offset, self.pending, self.anchor = 0, b"", b""
                self.identity = identity
                stream.seek(self.offset)
                chunk = stream.read(256 * 1024)
                self.offset += len(chunk)
                stream.seek(max(0, self.offset - 64))
                self.anchor = stream.read(min(self.offset, 64))
        except (FileNotFoundError, PermissionError):
            return []
        lines = (self.pending + chunk).split(b"\n")
        self.pending = lines.pop()
        if len(self.pending) > 16384:
            self.pending = b""
        return [line for line in lines if len(line) <= 16384 and
                (MARKER in line or (self.include_exit and b"CSystem::Quit invoked" in line))]


def finite_number(value) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def is_vector(value) -> bool:
    return isinstance(value, dict) and all(finite_number(value.get(axis)) for axis in ("x", "y", "z"))


def decode_packet(line: bytes) -> dict:
    payload = line.split(MARKER, 1)[1].strip()
    def number(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError("nonfinite number")
        return value
    def invalid_constant(text):
        raise ValueError("nonfinite JSON constant")
    packet = json.loads(payload.decode("utf-8"), parse_float=number, parse_constant=invalid_constant)
    if not isinstance(packet, dict) or packet.get("protocol") != PROTOCOL:
        raise ValueError("unknown protocol")
    if packet.get("event") not in EVENTS:
        raise ValueError("unknown event")
    if not isinstance(packet.get("session"), str) or not 1 <= len(packet["session"]) <= 80:
        raise ValueError("invalid session")
    if type(packet.get("seq")) is not int or packet["seq"] < 1:
        raise ValueError("invalid sequence")
    game_time = packet.get("game_time")
    if not finite_number(game_time):
        raise ValueError("invalid game time")
    npcs = packet.get("npcs")
    if not isinstance(npcs, list) or len(npcs) != 2:
        raise ValueError("expected two NPC records")
    names = []
    for npc in npcs:
        if not isinstance(npc, dict):
            raise ValueError("invalid NPC")
        if not isinstance(npc.get("name"), str):
            raise ValueError("invalid speaker")
        names.append(npc.get("name"))
        if not isinstance(npc.get("entity_name"), str) or len(npc["entity_name"]) > 255:
            raise ValueError("invalid entity name")
        if type(npc.get("available")) is not bool:
            raise ValueError("invalid NPC availability")
        if npc["available"] and not is_vector(npc.get("position")):
            raise ValueError("invalid NPC position")
    if set(names) != SPEAKERS:
        raise ValueError("unknown or duplicate speaker")
    player = packet.get("player")
    if not isinstance(player, dict) or player.get("name") != "Henry" or type(player.get("available")) is not bool:
        raise ValueError("invalid player record")
    if player["available"] and not is_vector(player.get("position")):
        raise ValueError("invalid player position")
    if player.get("forward") is not None and not is_vector(player["forward"]):
        raise ValueError("invalid player forward vector")
    director = packet.get("director")
    if director is not None:
        phases = {"idle", "reserved", "approaching", "waiting_audio", "playing", "finished", "cancelled"}
        if (not isinstance(director, dict) or director.get("version") != 1
                or not isinstance(director.get("id"), str) or len(director["id"]) > 96
                or director.get("phase") not in phases or director.get("behavior") != "patrol"
                or any(type(director.get(key)) is not bool for key in
                       ("enabled", "in_nebakov", "arrived", "audio_ready"))):
            raise ValueError("invalid conversation director")
        ack = director.get("control")
        if director.get("owner") is not None and (not isinstance(director["owner"], str)
                or len(director["owner"]) > 80):
            raise ValueError("invalid director owner")
        if ack is not None and (not isinstance(ack, dict) or not isinstance(ack.get("peer"), str)
                or type(ack.get("seq")) is not int or ack["seq"] < 1
                or type(ack.get("accepted")) is not bool):
            raise ValueError("invalid command acknowledgment")
    return packet


class PositionReceiver:
    def __init__(self):
        self.current_session = None
        self.retired_sessions = []
        self.sequence = 0
        self.received_at = None
        self.latest = None

    def accept(self, packet: dict, now: float | None = None) -> dict | None:
        if packet["session"] in self.retired_sessions:
            return None
        if packet["session"] != self.current_session:
            if self.current_session:
                self.retired_sessions = (self.retired_sessions + [self.current_session])[-64:]
            self.current_session, self.sequence = packet["session"], 0
        if packet["seq"] <= self.sequence:
            return None
        self.sequence = packet["seq"]
        self.received_at = time.monotonic() if now is None else now
        complete = packet["player"]["available"] and all(n["available"] for n in packet["npcs"])
        status = "positions_ok" if complete else "waiting_for_entities"
        if packet["event"] in {"bridge_stopped", "world_reset"}:
            status = "stopped"
        self.latest = {
            "milestone": 1, "status": status, "generation_enabled": False,
            "received_at_utc": datetime.now(timezone.utc).isoformat(), "packet": packet,
        }
        return self.latest

    def mark_stale(self, after: float, now: float | None = None) -> dict | None:
        now = time.monotonic() if now is None else now
        if self.latest is None or self.latest["status"] in {"stale", "stopped"}:
            return None
        if now - self.received_at < after:
            return None
        self.latest = {**self.latest, "status": "stale"}
        return self.latest


def write_snapshot(directory: Path, snapshot: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / f"latest_positions.{os.getpid()}.tmp"
    try:
        temporary.write_text(json.dumps(snapshot, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temporary, directory / "latest_positions.json")
    finally:
        temporary.unlink(missing_ok=True)


def describe(snapshot: dict) -> str:
    parts = []
    packet = snapshot["packet"]
    for person in packet["npcs"] + [packet["player"]]:
        if person["available"]:
            p = person["position"]
            parts.append(f"{person['name']}=({p['x']:.2f}, {p['y']:.2f}, {p['z']:.2f})")
        else:
            parts.append(f"{person['name']}=MISSING")
    return f"[{snapshot['status']}] seq={packet['seq']} " + " | ".join(parts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--from-start", action="store_true", help="Diagnostic replay; may read historical data")
    parser.add_argument("--once", action="store_true", help="Exit after receiving a complete position packet")
    parser.add_argument("--timeout", type=float, default=60, help="Timeout for --once, in seconds")
    parser.add_argument("--stale-after", type=float, default=5)
    args = parser.parse_args(argv)
    if args.timeout <= 0 or args.stale_after <= 0:
        parser.error("Timeouts must be positive")
    tail, receiver = LogTail(args.game_log, args.from_start), PositionReceiver()
    started = time.monotonic()
    # Establish the live cursor before asking the user to send the first packet.
    initial = tail.poll()
    write_snapshot(args.output_dir, {"milestone": 1, "status": "waiting_for_telemetry",
        "generation_enabled": False, "packet": None})
    print(f"Milestone 1: generation, TTS and audio playback DISABLED.\nLog: {args.game_log}", flush=True)
    print("Ready. In KCD2 run: nebakov_voice_bind_pair", flush=True)
    try:
        while True:
            lines, initial = initial + tail.poll(), []
            for line in lines:
                try:
                    packet = decode_packet(line)
                except (ValueError, TypeError, KeyError, UnicodeError) as error:
                    print(f"Skipped malformed bridge packet: {type(error).__name__}", flush=True)
                    continue
                snapshot = receiver.accept(packet)
                if snapshot is None:
                    continue
                write_snapshot(args.output_dir, snapshot)
                print(describe(snapshot), flush=True)
                if packet["event"] == "conversation_trigger":
                    print("TEST TRIGGER RECEIVED; no conversation generated (milestone 1).", flush=True)
                if args.once and snapshot["status"] == "positions_ok":
                    print("POSITIONS RECEIVED (MILESTONE 1).", flush=True)
                    return 0
            stale = receiver.mark_stale(args.stale_after)
            if stale:
                write_snapshot(args.output_dir, stale)
                print("STALE: no fresh telemetry; cached positions must not trigger conversations.", flush=True)
            if args.once and time.monotonic() - started >= args.timeout:
                print("Timed out; no complete live position packet received.", flush=True)
                return 2
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Position receiver stopped.", flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
