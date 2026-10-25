"""Acknowledged, bounded control channel and game-directed patrol conversations.

Only fixed control verbs and validated opaque IDs cross into Lua; no prompt or
model-generated text is executed. Lua owns NPC selection, movement and cleanup.
"""
from __future__ import annotations

from collections import deque
import os
from pathlib import Path
import re
import uuid
import math

from nebakov_voice_playback import load_manifest

KINDS = {"heartbeat_ready", "heartbeat_busy", "audio_ready", "playing", "finished", "cancel", "error", "line_start", "line_end"}
TOKEN = re.compile(r"[A-Za-z0-9_.:+-]{0,96}\Z")
ACTIVE_PHASES = {"reserved", "approaching", "waiting_audio", "playing"}


def command_source(peer, seq, kind, session, conversation, line=0, duration=0):
    if kind not in KINDS or type(seq) is not int or not 1 <= seq < 2**53:
        raise ValueError("Invalid control command")
    if any(not isinstance(s, str) or not TOKEN.fullmatch(s) for s in (peer, session, conversation)):
        raise ValueError("Invalid control token")
    extra = ""
    if kind in {"line_start", "line_end"}:
        if type(line) is not int or not 1 <= line <= 4 or type(duration) is not int or not 0 <= duration <= 100000:
            raise ValueError("Invalid speech line/duration")
        extra = ", %d, %d" % (line, duration)
    return ("-- Generated NebakovVoice control packet; contains no dialogue code.\n"
            'nebakovrising.Conversations.Receive("%s", %d, "%s", "%s", "%s"%s)\n'
            % (peer, seq, kind, session, conversation, extra))


class CommandOutbox:
    def __init__(self, path: Path, emit):
        self.path, self.emit = path, emit
        self.peer = uuid.uuid4().hex
        self.session = None
        self.sequence = 0
        self.queue = deque()
        self.pending = None
        self.last_heartbeat = -100.0
        self.rejected = None
        self.last_ack = None

    def observe(self, packet, now):
        if packet["session"] != self.session:
            self.session = packet["session"]
            self.pending = None
            self.queue.clear()
            self.last_heartbeat = -100.0
            self.last_ack = None
            # Sequence stays monotonic when Lua starts a new conversation session.
        ack = (packet.get("director") or {}).get("control")
        if self.pending and ack and ack["peer"] == self.peer and ack["seq"] == self.pending["seq"]:
            self.last_ack = {**self.pending, "accepted": ack["accepted"]}
            self.emit("control_ack", kind=self.pending["kind"], accepted=ack["accepted"], seq=ack["seq"])
            if not ack["accepted"]:
                self.rejected = self.pending["conversation"], self.pending["kind"]
            self.pending = None

    def send(self, kind, conversation="", line=0, duration=0):
        if kind not in KINDS:
            raise ValueError("Unknown control verb")
        entry = (kind, conversation, line, duration)
        if entry not in self.queue and not (self.pending and
                (self.pending["kind"], self.pending["conversation"],
                 self.pending.get("line", 0), self.pending.get("duration", 0)) == entry):
            self.queue.append(entry)

    def cancel(self, conversation):
        self.queue = deque(e for e in self.queue if e[1] != conversation)
        if self.pending and self.pending["conversation"] == conversation:
            self.pending = None
        self.queue.appendleft(("cancel", conversation, 0, 0))

    def _write(self, message):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + f".{os.getpid()}.tmp")
        temporary.write_text(command_source(self.peer, message["seq"], message["kind"],
                                            self.session, message["conversation"],
                                            message.get("line", 0), message.get("duration", 0)), encoding="ascii")
        os.replace(temporary, self.path)

    def tick(self, now, ready):
        if self.session is None:
            return
        if not self.pending:
            if self.queue:
                kind, conversation, line, duration = self.queue.popleft()
            elif now - self.last_heartbeat >= 1:
                kind, conversation = ("heartbeat_ready" if ready else "heartbeat_busy"), ""
                line, duration = 0, 0
                self.last_heartbeat = now
            else:
                return
            self.sequence += 1
            self.pending = {"seq": self.sequence, "kind": kind, "conversation": conversation,
                            "line": line, "duration": duration,
                            "written": now, "first_written": now}
            self._write(self.pending)
            self.emit("control_sent", kind=kind, seq=self.sequence, conversation=conversation)
        elif now - self.pending["written"] >= 2:
            self.pending["written"] = now
            self._write(self.pending)  # Retry same ID, never duplicate an action.
            if now-self.pending["first_written"] >= 6 and not self.pending.get("warned"):
                self.pending["warned"] = True
                self.emit("control_waiting_for_ack", path=str(self.path), seq=self.pending["seq"],
                          hint="Check game is running and nebakov_conversation_start was called")

    def shutdown(self):
        if not self.session:
            return
        # Final cleanup supersedes an unacknowledged heartbeat; Lua also has a lease timeout.
        chosen = next((e for e in self.queue if e[0] in {"cancel", "finished"}), None)
        if chosen:
            self.sequence += 1
            self._write({"seq": self.sequence, "kind": chosen[0], "conversation": chosen[1]})
        elif self.pending:
            self._write(self.pending)


class PatrolController:
    def __init__(self, config, playback, submit, emit, outbox, worker_ready, preset=None):
        self.config, self.playback, self.submit, self.emit = config, playback, submit, emit
        self.outbox, self.worker_ready, self.preset = outbox, worker_ready, preset
        self.state = "waiting"
        self.packet, self.received, self.progress, self.game_time = None, None, None, None
        self.session, self.conversation, self.job, self.manifest = None, None, None, None
        self.retired = deque(maxlen=64)
        self.started = None
        self.play_requested = False
        # Wait for the game to process each line's animation cue before sound.
        self.playback.before_line = self.prepare_line
        self.playback.after_line = self.finish_line

    def prepare_line(self, line):
        ack = self.outbox.last_ack
        if ack and ack["kind"] == "line_start" and ack["conversation"] == self.conversation \
                and ack.get("line") == line.index and ack["accepted"]:
            return True
        self.outbox.send("line_start", self.conversation, line.index, math.ceil(line.seconds * 1000))
        return False

    def finish_line(self, line):
        self.outbox.send("line_end", self.conversation, line.index)

    def transition(self, state):
        if self.state != state:
            self.state = state
            self.emit("state", state=state)

    def cancel(self, reason, now, notify=True):
        if self.conversation:
            self.emit("conversation_cancelled", reason=reason, conversation=self.conversation)
            if notify:
                self.outbox.cancel(self.conversation)
            self.retired.append(self.conversation)
        self.playback.stop()
        self.conversation = self.job = self.manifest = self.started = None
        self.play_requested = False
        self.transition("waiting")

    def invalidate(self, reason, now):
        self.cancel(reason, now)
        self.packet = None

    def fresh(self, now):
        return (self.packet is not None and self.received is not None and self.progress is not None
                and now-self.received < self.config.stale_after and now-self.progress < self.config.stale_after)

    def ingest(self, packet, now):
        if self.session != packet["session"]:
            self.cancel("session_changed", now, notify=False)
            self.session, self.game_time = packet["session"], None
        self.outbox.observe(packet, now)
        director = packet.get("director")
        if not director or not director.get("enabled") or packet["event"] in {"bridge_stopped", "world_reset"}:
            self.invalidate("director_not_active", now)
            return
        if self.game_time is None or packet["game_time"] > self.game_time:
            self.progress = now
        elif packet["game_time"] < self.game_time:
            self.invalidate("game_time_reversed", now)
            return
        self.game_time, self.packet, self.received = packet["game_time"], packet, now
        identity, phase = director["id"], director["phase"]
        if phase == "finished" and identity == self.conversation and self.state == "finishing":
            self.emit("conversation_finished", conversation=identity, job=self.job)
            self.retired.append(identity)
            self.conversation = self.job = self.manifest = self.started = None
            self.transition("waiting")
        elif phase not in ACTIVE_PHASES or not director["in_nebakov"]:
            self.cancel(director.get("reason") or phase, now, notify=False)
        elif director.get("owner") != self.outbox.peer:
            self.cancel("different_runtime_owner", now, notify=False)
        elif identity != self.conversation and identity not in self.retired:
            self.cancel("different_conversation", now, notify=False)
            self.conversation, self.started = identity, now
            self.play_requested = False
            self.emit("conversation_selected", conversation=identity, behavior=director["behavior"],
                      entities=[n["entity_name"] for n in packet["npcs"]])
            self.transition("preparing")

    def _audio_ready(self, manifest, now):
        try:
            load_manifest(Path(manifest))
            self.playback.start(Path(manifest))  # Queues lines; does not start the sound.
            self.manifest = Path(manifest)
            self.outbox.send("audio_ready", self.conversation)
            self.transition("waiting_arrival")
        except Exception as error:
            self.emit("conversation_error", reason=str(error)[:240])
            self.cancel("invalid_manifest", now)

    def result(self, job, manifest, error, now):
        if self.job != job or not self.conversation or not self.fresh(now):
            self.emit("late_result_discarded", job=job)
            return
        if error:
            self.emit("conversation_error", reason=error)
            self.cancel("generation_failed", now)
        else:
            self._audio_ready(manifest, now)

    def tick(self, now):
        self.outbox.tick(now, self.worker_ready())
        if not self.conversation:
            return
        if not self.fresh(now):
            self.cancel("telemetry_stale", now)
            return
        if now-self.started > 300:
            self.cancel("conversation_timeout", now)
            return
        p, d = self.packet, self.packet["director"]
        if not p["player"]["available"] or not all(n["available"] for n in p["npcs"]):
            self.cancel("entity_unavailable", now)
            return
        if self.outbox.rejected and self.outbox.rejected[0] == self.conversation:
            self.cancel("control_rejected", now)
            self.outbox.rejected = None
            return
        if self.state == "preparing" and d["phase"] in {"approaching", "waiting_audio"}:
            if self.preset:
                self._audio_ready(self.preset, now)
            else:
                job = self.submit(p)
                if job:
                    self.job = job
                    self.transition("generating")
        if self.manifest and d["arrived"] and d["audio_ready"]:
            if not self.play_requested:
                self.outbox.send("playing", self.conversation)
                self.play_requested = True
            if d["phase"] == "playing" and self.state != "finishing":
                self.transition("playing")
                try:
                    if not self.playback.tick(p):
                        self.outbox.send("finished", self.conversation)
                        self.transition("finishing")
                except Exception as error:
                    self.emit("conversation_error", reason=str(error)[:240])
                    self.cancel("playback_failed", now)

    def close(self):
        if self.state != "finishing":
            self.cancel("runtime_stopped", 0)
        self.outbox.shutdown()
