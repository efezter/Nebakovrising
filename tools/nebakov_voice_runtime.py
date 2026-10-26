"""Live NebakovVoice supervisor: telemetry, one generation worker, positional audio."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import queue
import sys
import time
import uuid
import wave

from nebakov_voice_receiver import (DEFAULT_LOG, DEFAULT_OUTPUT, LogTail,
                                    PositionReceiver, decode_packet, write_snapshot)
from nebakov_voice_playback import PygameAudio, SequentialPlayback, load_manifest
from nebakov_voice_engine_adapter import worker_main
from nebakov_voice_director import CommandOutbox, PatrolController
from nebakov_voice_config import DEFAULT_CONFIG, load_config
from nebakov_voice_prompts import DEFAULT_PROFILES, PromptProfiles
from nebakov_voice_transport import FileSnapshot, BoundedJournal


def build_context(packet):
    director = packet.get("director")
    if director and director.get("id"):
        behavior = director.get("behavior")
        if behavior not in {"patrol","meal","idle"}:
            raise ValueError("No conversation context handler for " + str(behavior))
        if behavior != 'patrol':
            return ('Two named Nebakov guards are nearby and '+behavior+'. They remain in their current postures. '
                    'Write a brief natural exchange with a greeting, without movement instructions.')
        hour = (director.get("context") or {}).get("hour")
        time_context = f"The in-game hour is {hour:.1f}. " if isinstance(hour, (int, float)) else ""
        return ("Marek and Hertl are speaker aliases for two castle guards at Nebakov. "
                "Both were patrolling; they have briefly paused their patrol and one is approaching the other. "
                "They will speak once together, then return to guard duty. " + time_context +
                "Write a natural exchange about the watch, castle life or the weather. "
                "Henry is nearby overhearing them; do not address him directly. "
                "Use spoken dialogue only, without narration, movement instructions or combat.")
    return ("Marek and Hertl are on duty at Nebakov Castle. Henry, a traveller, is approaching. "
            "They exchange a short, natural conversation with each other about guard duty. "
            "They remain at their current posts; do not narrate movement or actions.")


@dataclass
class Settings:
    proximity: float = 8.0
    pair_distance: float = 6.0
    exit_distance: float = 12.0
    cooldown: float = 120.0
    stale_after: float = 2.0
    dwell: float = 1.0
    error_backoff: float = 10.0
    automatic: bool = True
    volume: float = 0.85

    def validate(self):
        for key, value in asdict(self).items():
            if key != "automatic" and (not math.isfinite(value) or value < 0):
                raise ValueError(f"Invalid setting: {key}")
        if (self.proximity <= 0 or self.pair_distance <= 0 or
                self.exit_distance <= self.proximity or self.stale_after <= 0 or
                self.dwell <= 0 or not 0 <= self.volume <= 1):
            raise ValueError("Require positive radii/timers, exit > proximity, volume 0..1")


def distance(a, b):
    return math.sqrt(sum((a[k] - b[k]) ** 2 for k in ("x", "y", "z")))


class Controller:
    """No threads or file I/O; deterministic state transitions with an injected clock."""
    def __init__(self, settings, playback, submit, emit, preset=None):
        self.config, self.playback = settings, playback
        self.submit, self.emit, self.preset = submit, emit, preset
        self.state = "waiting"
        self.packet = None
        self.key = None
        self.received = self.progress = None
        self.game_time = None
        self.eligible_since = None
        self.next_allowed = 0.0
        self.armed = True
        self.job = None
        self.started = None
        self.manual_requested = False

    def transition(self, state):
        if self.state != state:
            self.state = state
            self.emit("state", state=state)

    def cancel(self, reason, now):
        active = self.state in {"generating", "playing"}
        if active:
            self.emit("conversation_cancelled", reason=reason, job=self.job)
            self.next_allowed = max(self.next_allowed, now + self.config.error_backoff)
        self.playback.stop()
        self.job, self.started, self.eligible_since = None, None, None
        self.manual_requested = False
        self.transition("waiting")

    def invalidate(self, reason, now):
        self.cancel(reason, now)
        self.packet = None

    def ingest(self, packet, now):
        key = (packet["session"], tuple(sorted((n["name"], n["entity_name"]) for n in packet["npcs"])))
        if key != self.key:
            self.cancel("session_or_binding_changed", now)
            self.key = key
            self.game_time = None
            self.armed = True
        if packet["event"] in {"world_reset", "bridge_stopped"}:
            self.invalidate(packet["event"], now)
            return
        if not packet["player"]["available"] or not all(n["available"] for n in packet["npcs"]):
            self.invalidate("entity_unavailable", now)
            return
        if self.game_time is not None and packet["game_time"] < self.game_time:
            self.invalidate("game_time_reversed", now)
            return
        if self.game_time is None or packet["game_time"] > self.game_time:
            self.progress = now
        self.game_time = packet["game_time"]
        self.received, self.packet = now, packet
        if packet["event"] == "conversation_requested":
            self.manual_requested = True
        # conversation_trigger is the milestone-1 diagnostic event, never a request.

    def fresh(self, now):
        return (self.packet is not None and self.received is not None and self.progress is not None
                and now - self.received < self.config.stale_after
                and now - self.progress < self.config.stale_after)

    def failed(self, reason, now):
        self.emit("conversation_error", reason=reason)
        self.cancel(reason, now)
        self.next_allowed = now + self.config.error_backoff

    def result(self, job, manifest, error, now):
        if self.job != job or self.state != "generating":
            self.emit("late_result_discarded", job=job)
            return
        if error:
            self.failed(error, now)
        elif not self.fresh(now):
            self.cancel("stale_before_playback", now)
        else:
            try:
                self.playback.start(Path(manifest))
                self.transition("playing")
            except Exception as exc:
                self.failed(type(exc).__name__, now)

    def tick(self, now):
        if not self.fresh(now):
            if self.state != "waiting":
                self.cancel("telemetry_stale", now)
            return
        npcs, player = self.packet["npcs"], self.packet["player"]["position"]
        radius = max(distance(n["position"], player) for n in npcs)
        pair = distance(npcs[0]["position"], npcs[1]["position"])
        if radius >= self.config.exit_distance or pair > self.config.pair_distance:
            if self.state in {"playing", "generating"}:
                self.cancel("out_of_range", now)
            self.armed, self.eligible_since, self.manual_requested = True, None, False
            return
        if self.state == "playing":
            try:
                if not self.playback.tick(self.packet):
                    self.emit("conversation_finished", job=self.job)
                    self.next_allowed = now + self.config.cooldown
                    self.job = None
                    self.transition("cooldown")
            except Exception as exc:
                self.failed(type(exc).__name__, now)
            self.manual_requested = False
            return
        if self.state == "generating":
            self.manual_requested = False
            return
        if radius > self.config.proximity:
            self.eligible_since = None
            self.manual_requested = False
            return
        if self.eligible_since is None:
            self.eligible_since = now
        manual, self.manual_requested = self.manual_requested, False
        if now < self.next_allowed:
            self.transition("cooldown")
            if manual:
                self.emit("request_ignored", reason="cooldown", seconds=round(self.next_allowed - now, 1))
            return
        self.transition("idle")
        if not manual and not (self.config.automatic and self.armed
                               and now - self.eligible_since >= self.config.dwell):
            return
        if self.preset:
            try:
                self.playback.start(self.preset)
                self.transition("playing")
            except Exception as exc:
                self.failed(type(exc).__name__, now)
        else:
            job = self.submit(self.packet)
            if not job:
                return  # Worker warming up or finishing a cancelled job; never enqueue.
            self.job, self.started = job, now
            self.transition("generating")
        self.armed = False


class Worker:
    def __init__(self, engine_dir, emit, timeout=900.0, prompts=None, prewarm=False):
        self.engine_dir, self.emit, self.timeout = engine_dir, emit, timeout
        self.ready, self.busy, self.started = False, None, time.monotonic()
        self.prompts = prompts
        context = mp.get_context("spawn")
        self.commands, self.results = context.Queue(maxsize=1), context.Queue()
        self.process = context.Process(target=worker_main, args=(self.commands, self.results, str(engine_dir), prewarm), daemon=True)
        self.process.start()

    def submit(self, packet):
        if not self.ready or self.busy:
            return None
        job = uuid.uuid4().hex
        samples = {n["name"]: n["voicesampleid"] for n in packet.get("npcs", []) if n.get("voicesampleid")}
        if packet.get("director") and packet["director"].get("voice_catalog_required") and len(samples) != 2:
            raise ValueError("Both guards need a persisted voicesampleid")
        prompts = getattr(self, "prompts", None)
        prepared = prompts.prepare(packet) if prompts and (packet.get("director") or {}).get("profile_id") else None
        self.commands.put_nowait({"id": job, "session": packet["session"],
            "context": prepared["text"] if prepared else build_context(packet), "voicesampleid": samples,
            "profile_id": prepared["profile_id"] if prepared else None,
            "prompt_parameters": prepared["prompt_parameters"] if prepared else None})
        self.busy, self.started = job, time.monotonic()
        self.emit("generation_started", job=job, session=packet["session"], seq=packet["seq"])
        return job

    def poll(self):
        messages = []
        while True:
            try:
                message = self.results.get_nowait()
            except queue.Empty:
                break
            if message["kind"] == "ready":
                self.ready = True
                self.emit("engine_ready", backend=message.get("backend", "kokoro"))
            elif message["kind"] == "fatal":
                raise RuntimeError("Engine initialization: " + message.get("detail", message["error"]))
            else:
                self.busy = None
                messages.append(message)
        if not self.process.is_alive():
            raise RuntimeError("Generation worker exited; restart the launcher (see console)")
        if (not self.ready or self.busy) and time.monotonic() - self.started > self.timeout:
            raise RuntimeError("Generation worker timed out; restart the launcher")
        return messages

    def close(self):
        if self.process.is_alive():
            self.process.terminate()
        self.process.join(timeout=3)
        self.commands.close()
        self.results.close()


class InstanceLock:
    """OS releases the byte-range lock on crashes as well as normal exit."""
    def __init__(self, path):
        self.path, self.stream = path, None

    def __enter__(self):
        import msvcrt
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
        if self.stream.tell() == 0:
            self.stream.write(b"0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.stream.close()
            self.stream = None
            raise RuntimeError("Another NebakovVoice runtime is already running")
        return self

    def __exit__(self, *args):
        import msvcrt
        if self.stream:
            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            self.stream.close()


def latest_manifest(root=Path(r"D:\NebakovVoice\output\conversations")):
    # The service writes JSON before rendering audio. Skip unfinished outputs.
    files = sorted(root.glob("*/conversation.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise ValueError(f"No saved conversation.json in {root}. Start start_patrol_conversations.cmd to generate one.")
    failures = []
    for manifest in files:
        try:
            load_manifest(manifest)
        except PermissionError:
            raise
        except (OSError, ValueError, EOFError, wave.Error) as error:
            failures.append(f"{manifest.parent.name}: {error}")
            continue
        return manifest
    raise ValueError("No playable conversation. " + "; ".join(failures[:2])
                     + ". Start start_patrol_conversations.cmd to generate a new one.")


def run(args, config, preset):
    args.output_dir.mkdir(parents=True, exist_ok=True)
    worker, audio, controller = None, None, None
    # Instance lock is global to the engine directory even with different output dirs.
    with InstanceLock(args.engine_dir / "nebakov_voice_runtime.lock"), \
            BoundedJournal(args.output_dir / "bridge_events.jsonl") as journal, \
            BoundedJournal(args.output_dir / "audio_spatial.jsonl",max_bytes=256*1024,backups=1) as audio_journal:
        completed = False
        def emit(event, **fields):
            nonlocal completed
            if event=='spatial_audio':
                audio_journal.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),
                    'event':event,**fields},ensure_ascii=True,allow_nan=False)+'\n')
                return  # Diagnostic file only, never the console or event journal.
            if event == 'telemetry' or (event in {'control_sent', 'control_ack'}
                    and fields.get('kind', '').startswith('heartbeat_')):
                return
            if event == "conversation_finished":
                completed = True
            record = {"at": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
            journal.write(json.dumps(record, ensure_ascii=True, allow_nan=False) + "\n")
            if event != "telemetry":
                print(json.dumps(record, ensure_ascii=True), flush=True)
        tail = LogTail(args.game_log, include_exit=True)
        tail.poll()  # Establish live EOF before warming models; never replay history.
        telemetry_file = args.command_file.parent / 'telemetry.json'
        file_snapshot = FileSnapshot(telemetry_file)
        receiver = PositionReceiver()
        write_snapshot(args.output_dir, {"status": "waiting_for_telemetry", "generation_enabled": preset is None, "packet": None})
        emit("runtime_started", mode="existing_wavs" if preset else "generate", settings=asdict(config),
             backend="pygame", manifest=str(preset) if preset else None)
        try:
            audio = PygameAudio()
            playback = SequentialPlayback(audio, emit, config.volume)
            if args.director:
                print(f"Conversation config: {args.config.absolute()}", flush=True)
            conversation_settings = load_config(args.config) if args.director else None
            if conversation_settings and (preset or args.manual):
                conversation_settings["randomEnabled"] = False
            prompts = PromptProfiles(args.profiles_dir) if conversation_settings else None
            if prompts:
                prompts.load(conversation_settings["profileId"])
                emit("conversation_settings", config_file=str(args.config.absolute()),
                    profiles_dir=str(args.profiles_dir.absolute()), settings=conversation_settings)
            if not preset:
                worker = Worker(args.engine_dir, emit, args.worker_timeout, prompts,
                    bool(conversation_settings and conversation_settings.get("prewarmModel", True)))
            if args.director:
                from nebakov_voice_samples import discover
                catalog = discover(args.voices_dir) if not preset else None
                if catalog:
                    emit("voice_catalog", samples=catalog["ids"], fallback=catalog["fallback"], rejected=catalog["rejected"])
                outbox = CommandOutbox(args.command_file, emit, catalog, conversation_settings, telemetry_file)
                controller = PatrolController(config, playback, worker.submit if worker else lambda p: None,
                    emit, outbox, lambda: worker is None or (worker.ready and worker.busy is None), preset)
                print("READY: " + ("manual ready-audio test. " if preset else "24-hour conversations for stationary guards. ") +
                      "Manual test: nebakov_conversation_test. Wait for settings/catalog ACK and engine_ready.", flush=True)
            else:
                controller = Controller(config, playback, worker.submit if worker else lambda p: None, emit, preset)
                print("READY: in KCD2 run nebakov_voice_bind_pair. Approach both guards within "
                      f"{config.proximity:g} m. Manual request: nebakov_voice_talk. Stop: nebakov_voice_stop.", flush=True)
            while True:
                incoming = [(False, line) for line in tail.poll()]
                file_packet = file_snapshot.poll()
                if file_packet is not None:
                    incoming.append((True, file_packet))
                for from_file, line in incoming:
                    now = time.monotonic()
                    if not from_file and b"CSystem::Quit invoked" in line:
                        controller.invalidate("game_exit", now)
                        emit("game_exit")
                        continue
                    try:
                        packet = line if from_file else decode_packet(line)
                    except (ValueError, TypeError, KeyError, UnicodeError, IndexError):
                        emit("malformed_packet")
                        continue
                    if from_file and args.director:
                        controller.outbox.note_file(packet)
                    snapshot = receiver.accept(packet, now)
                    if snapshot is None:
                        continue
                    snapshot = {**snapshot, "milestone": 2, "generation_enabled": preset is None}
                    write_snapshot(args.output_dir, snapshot)
                    emit("telemetry", session=packet["session"], seq=packet["seq"],
                         game_time=packet["game_time"], trigger=packet["event"],
                         forward_source=packet["player"].get("forward_source"))
                    controller.ingest(packet, now)
                now = time.monotonic()
                # Invalidate on range/staleness BEFORE accepting a just-finished generation.
                controller.tick(now)
                if worker:
                    for message in worker.poll():
                        controller.result(message["id"], message.get("manifest"), message.get("error"), now)
                stale = receiver.mark_stale(config.stale_after, now)
                if stale:
                    write_snapshot(args.output_dir, {**stale, "milestone": 2, "generation_enabled": preset is None})
                    emit("telemetry_stale")
                if args.once and completed:
                    emit("runtime_stopped", reason="one_conversation_completed")
                    break
                time.sleep(0.05)
        except KeyboardInterrupt:
            emit("runtime_stopped")
        except Exception as error:
            emit("runtime_error", reason=str(error)[:400])
            raise
        finally:
            if args.director and controller:
                controller.close()
            if audio:
                audio.close()
            if worker:
                worker.close()
            write_snapshot(args.output_dir, {"milestone": 2, "status": "runtime_stopped",
                "generation_enabled": False, "packet": None})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--engine-dir", type=Path, default=Path(r"D:\NebakovVoice\server"))
    parser.add_argument("--manifest", help="Existing conversation.json or 'latest'; never calls Gemini/TTS")
    parser.add_argument("--voices-dir", type=Path, default=Path(r"D:\NebakovVoice\tts\voices"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--profiles-dir", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--manual", action="store_true", help="Only nebakov_voice_talk requests; retain proximity/cooldown")
    parser.add_argument("--check", action="store_true", help="Check mixer and warm the TTS worker; never generates or plays speech")
    parser.add_argument("--once", action="store_true", help="Exit after one conversation has actually finished")
    parser.add_argument("--director", action="store_true", help="Game-owned patrol selection/approach; acknowledged Lua control channel")
    parser.add_argument("--command-file", type=Path,
        default=DEFAULT_LOG.parent / "Data/Scripts/nebakov_voice/command.lua")
    for name, default in [("proximity", 8), ("pair-distance", 6), ("exit-distance", 12), ("cooldown", 120),
                          ("stale-after", 2), ("dwell", 1), ("volume", 0.85), ("worker-timeout", 900)]:
        parser.add_argument("--" + name, type=float, default=default)
    args = parser.parse_args(argv)
    config = Settings(args.proximity, args.pair_distance, args.exit_distance, args.cooldown,
                      args.stale_after, args.dwell, automatic=not args.manual, volume=args.volume)
    try:
        config.validate()
        if not math.isfinite(args.worker_timeout) or args.worker_timeout <= 0:
            raise ValueError("Worker timeout must be positive and finite")
        preset = latest_manifest() if args.manifest == "latest" else Path(args.manifest) if args.manifest else None
        if preset:
            load_manifest(preset)
        if args.check:
            audio, worker = None, None
            try:
                audio = PygameAudio()
                if not preset:
                    worker = Worker(args.engine_dir, lambda event, **fields: print(event, flush=True), args.worker_timeout)
                    while not worker.ready:
                        worker.poll()
                        time.sleep(0.05)
                print("CHECK PASSED: mixer ready; " + ("existing manifest valid" if preset else "generation backend ready; no Gemini request"), flush=True)
            finally:
                if worker:
                    worker.close()
                if audio:
                    audio.close()
            return 0
        run(args, config, preset)
        return 0
    except Exception as error:
        print(f"NEBAKOV VOICE ERROR: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    mp.freeze_support()
    raise SystemExit(main())
