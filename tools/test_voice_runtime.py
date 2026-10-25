"""Runtime invariants using fake audio/engine; no API calls or audible playback."""
from copy import deepcopy
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import wave
import io

sys.dont_write_bytecode = True
from nebakov_voice_runtime import Controller, Settings, InstanceLock, latest_manifest
from nebakov_voice_playback import SequentialPlayback, load_manifest, spatial_gains
from nebakov_voice_engine_adapter import worker_main
import test_voice_bridge as bridge_tests

ROOT = Path(__file__).resolve().parent


def packet(seq=1, event="positions", session="s", x=0):
    return {"session": session, "seq": seq, "event": event, "game_time": seq * 0.25,
            "player": {"available": True, "position": {"x": x, "y": 0, "z": 0},
                       "forward": {"x": 0, "y": 1, "z": 0}},
            "npcs": [{"name": name, "entity_name": "guard_" + name, "available": True,
                      "position": {"x": i + 1, "y": 1, "z": 0}} for i, name in enumerate(["Marek", "Hertl"])]}


class Audio:
    def __init__(self):
        self.busy, self.played, self.stops = False, [], 0

    def play(self, line, gains):
        assert not self.busy, "overlapping lines"
        self.busy = True
        self.played.append((line, gains))

    def update(self, gains):
        self.gains = gains

    def is_busy(self):
        return self.busy

    def stop(self):
        self.busy = False
        self.stops += 1


class Playback:
    def __init__(self):
        self.started, self.active, self.stops = [], True, 0

    def start(self, path):
        self.started.append(path)

    def tick(self, p):
        return self.active

    def stop(self):
        self.stops += 1


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.audio, self.jobs, self.events = Playback(), [], []
        self.config = Settings(cooldown=3, dwell=0.5)
        self.controller = Controller(self.config, self.audio, self.submit,
                                     lambda event, **kw: self.events.append((event, kw)))

    def submit(self, p):
        job = f"job{len(self.jobs) + 1}"
        self.jobs.append(deepcopy(p))
        return job

    def feed(self, now, seq, **kw):
        self.controller.ingest(packet(seq, **kw), now)
        self.controller.tick(now)

    def generate(self):
        self.feed(0, 1)
        self.feed(0.6, 2)
        self.assertEqual(self.controller.state, "generating")

    def test_proximity_and_one_job_despite_repeated_requests(self):
        self.generate()
        for i in range(3, 12):
            self.feed(i / 4, i, event="conversation_requested")
        self.assertEqual(len(self.jobs), 1)

    def test_missing_npc_cancels_and_late_result_does_not_play(self):
        self.generate()
        p = packet(3)
        p["npcs"][0]["available"] = False
        self.controller.ingest(p, 0.7)
        self.controller.result("job1", "not_needed.json", None, 0.8)
        self.assertFalse(self.audio.started)
        self.assertEqual(self.controller.state, "waiting")

    def test_session_and_binding_change_cancel(self):
        for mutate in [lambda p: p.update(session="new"),
                       lambda p: p["npcs"][0].update(entity_name="new_guard")]:
            self.setUp()
            self.generate()
            p = packet(3)
            mutate(p)
            self.controller.ingest(p, 0.7)
            self.assertIsNone(self.controller.job)

    def test_stale_or_frozen_game_time_cancels(self):
        self.generate()
        p = packet(2)
        self.controller.ingest(p, 2.5)  # Fresh transport, frozen game clock.
        self.controller.tick(2.7)
        self.assertEqual(self.controller.state, "waiting")
        self.assertIsNone(self.controller.job)

    def test_leaving_range_discards_generation_result(self):
        self.generate()
        self.feed(0.7, 3, x=50)
        self.controller.result("job1", "unused", None, 0.8)
        self.assertFalse(self.audio.started)

    def test_cooldown_and_reentry_prevent_repeating_while_standing(self):
        self.controller.preset = Path("preset")
        self.feed(0, 1)
        self.feed(0.6, 2)
        self.audio.active = False
        self.feed(0.7, 3)
        for i in range(4, 30):
            self.feed(i / 4, i)
        self.assertEqual(len(self.audio.started), 1)
        self.feed(8, 32, x=50)
        self.feed(8.2, 33)
        self.feed(8.8, 34)
        self.assertEqual(len(self.audio.started), 2)

    def test_manual_only_ignores_milestone_test_command(self):
        self.config.automatic = False
        self.feed(0, 1)
        self.feed(0.7, 2, event="conversation_trigger")
        self.assertFalse(self.jobs)
        self.feed(0.8, 3, event="conversation_requested")
        self.assertEqual(len(self.jobs), 1)

    def test_manual_request_still_obeys_range_and_cooldown(self):
        self.config.automatic = False
        self.feed(0, 1, event="conversation_requested", x=50)
        self.assertFalse(self.jobs)
        self.controller.next_allowed = 10
        self.feed(1, 2, event="conversation_requested")
        self.assertFalse(self.jobs)

    def test_busy_worker_never_creates_queue(self):
        self.controller.submit = lambda p: None
        self.feed(0, 1)
        self.feed(1, 2)
        self.assertEqual(self.controller.state, "idle")
        self.assertTrue(self.controller.armed)


class FilesAndAudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.folder = Path(self.tmp.name)
        self.rows = []
        for i in range(1, 5):
            p = self.folder / f"{i}.wav"
            with wave.open(str(p), "wb") as wav:
                wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                wav.writeframes(b"\0\0" * 2400)
            self.rows.append({"index": i, "speaker": "Marek" if i % 2 else "Hertl", "audio_file": p.name})
        self.manifest = self.folder / "conversation.json"
        self.save()

    def save(self):
        self.manifest.write_text(json.dumps({"lines": self.rows}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_service_subfolder_audio_and_existing_path_escape(self):
        nested = self.folder / "chatterbox"
        nested.mkdir()
        for row in self.rows:
            (self.folder / row["audio_file"]).replace(nested / row["audio_file"])
            row["audio_file"] = "chatterbox/" + row["audio_file"]
        self.save()
        self.assertEqual(len(load_manifest(self.manifest)), 4)
        # All targets exist, but are outside this nested manifest's folder.
        outside = nested / "conversation.json"
        (self.folder / "outside.wav").write_bytes((nested / "1.wav").read_bytes())
        escaped = [dict(row, audio_file="../outside.wav") for row in self.rows]
        outside.write_text(json.dumps({"lines": escaped}))
        with self.assertRaises(ValueError):
            load_manifest(outside)

    def test_latest_skips_service_job_still_rendering(self):
        complete = self.folder / "complete"
        complete.mkdir()
        for path in list(self.folder.glob("*.wav")) + [self.manifest]:
            path.replace(complete / path.name)
        incomplete = self.folder / "rendering"
        incomplete.mkdir()
        pending = incomplete / "conversation.json"
        pending.write_text(json.dumps({"lines": self.rows}))
        os.utime(pending, (2000000000, 2000000000))
        self.assertEqual(latest_manifest(self.folder), complete / "conversation.json")

    def test_manifest_order_and_actual_channel_completion(self):
        self.rows.reverse()
        self.save()
        audio, events = Audio(), []
        player = SequentialPlayback(audio, lambda event, **kw: events.append((event, kw)))
        player.start(self.manifest)
        for i in range(4):
            self.assertTrue(player.tick(packet()))
            self.assertTrue(player.tick(packet()))  # Busy line cannot advance.
            self.assertEqual(len(audio.played), i + 1)
            audio.busy = False
        self.assertFalse(player.tick(packet()))
        self.assertEqual([x[0].speaker for x in audio.played], ["Marek", "Hertl", "Marek", "Hertl"])
        self.assertEqual(len(list(self.folder.glob("*.wav"))), 4)

    def test_bad_final_line_prevents_partial_playback(self):
        (self.folder / "4.wav").unlink()
        audio = Audio()
        playback = SequentialPlayback(audio, lambda *a, **kw: None)
        with self.assertRaises(FileNotFoundError):
            playback.start(self.manifest)
        self.assertFalse(audio.played)

    def test_unknown_speaker_duplicate_index_and_path_escape_rejected(self):
        for field, value in [("speaker", "Henry"), ("index", 1), ("audio_file", "../outside.wav")]:
            original = deepcopy(self.rows)
            self.rows[3][field] = value
            self.save()
            with self.assertRaises((ValueError, FileNotFoundError)):
                load_manifest(self.manifest)
            self.rows = original

    def test_mixer_pan_turning_distance_and_vertical_separation(self):
        p = {"x": 0, "y": 0, "z": 0}
        npc = {"x": 2, "y": 0, "z": 0}
        left, right = spatial_gains(npc, p, {"x": 0, "y": 1, "z": 0})
        self.assertGreater(right, left)
        left2, right2 = spatial_gains(npc, p, {"x": 0, "y": -1, "z": 0})
        self.assertGreater(left2, right2)
        self.assertEqual(spatial_gains({"x": 0, "y": 0, "z": 30}, p, None), (0, 0))

    def test_single_instance_lock(self):
        with InstanceLock(self.folder / "runtime.lock"):
            with self.assertRaises(RuntimeError):
                with InstanceLock(self.folder / "runtime.lock"):
                    pass

    def test_persistent_adapter_loads_tts_once_and_publishes_two_unique_jobs(self):
        calls = []
        engine = types.SimpleNamespace(OUTPUT_DIR=self.folder, GEMINI_MODEL="fake", NPCS={
            "Marek": {"voice_id": 1}, "Hertl": {"voice_id": 2}})
        engine.create_tts = lambda: calls.append("tts") or object()
        engine.generate_conversation = lambda *a, **kw: [dict(r, text="hello") for r in self.rows]
        def generate(tts, text, path, sid):
            path.write_bytes((self.folder / "1.wav").read_bytes())
            return 0.01
        engine.generate_audio = generate
        commands, results = queue.Queue(), queue.Queue()
        for i in range(2):
            commands.put({"id": str(i), "session": "s", "context": "duty"})
        commands.put(None)
        with patch.dict(sys.modules, {"conversation_engine": engine}), patch.dict(os.environ, {"GEMINI_API_KEY": "test-fixture"}):
            worker_main(commands, results, str(self.folder))
        messages = [results.get_nowait() for _ in range(3)]
        self.assertEqual(calls, ["tts"])
        manifests = [Path(m["manifest"]) for m in messages[1:]]
        self.assertNotEqual(manifests[0], manifests[1])
        for path in manifests:
            self.assertEqual(len(load_manifest(path)), 4)

    def test_service_adapter_uses_existing_renderer_without_loading_local_tts(self):
        rendered = []
        engine = types.SimpleNamespace(OUTPUT_DIR=self.folder, GEMINI_MODEL="fake")
        engine.generate_conversation = lambda *a, **kw: [dict(r, text="hello") for r in self.rows]
        def render(folder):
            document = json.loads((folder / "conversation.json").read_text())
            for row in document["lines"]:
                audio = folder / row["audio_file"]
                audio.parent.mkdir(exist_ok=True)
                audio.write_bytes((self.folder / "1.wav").read_bytes())
            rendered.append(folder)
        engine.render_with_chatterbox = render
        commands, results = queue.Queue(), queue.Queue()
        commands.put({"id":"service_job", "session":"s", "context":"patrol"})
        commands.put(None)
        with patch.dict(sys.modules, {"conversation_engine":engine}), \
                patch.dict(os.environ, {"GEMINI_API_KEY":"test-fixture"}), \
                patch("urllib.request.urlopen", return_value=io.BytesIO(b'{"status":"ready"}')):
            worker_main(commands, results, str(self.folder))
        self.assertEqual(results.get_nowait()["backend"], "tts_service")
        result = results.get_nowait()
        self.assertEqual(result["kind"], "result")
        self.assertEqual(len(rendered), 1)
        self.assertTrue(all(line.path.parent.name == "chatterbox" for line in load_manifest(Path(result["manifest"]))))


class CameraTests(unittest.TestCase):
    setUp = bridge_tests.VoiceBridgeTests.setUp
    packets = bridge_tests.VoiceBridgeTests.packets

    def test_camera_forward_precedes_body_fallback_and_talk_event(self):
        self.lua.execute("System.GetViewCameraDir = function() return {x=1,y=0,z=0} end; B.BindExistingPair(); B.Emit('conversation_requested')")
        p = self.packets()[-1]
        self.assertEqual(p["player"]["forward"], {"x": 1, "y": 0, "z": 0})
        self.assertEqual(p["player"]["forward_source"], "camera")
        self.assertEqual(p["event"], "conversation_requested")

    def test_native_probe_uses_current_bound_entity_position(self):
        self.lua.execute("System.ExecuteCommand = function(cmd) lastCommand = cmd end; B.BindExistingPair(); assert(B.TestNativeAudio())")
        self.assertEqual(self.lua.globals().lastCommand, "sfw_play nebakov_voice_probe 11.000000 22.500000 33.000000")


if __name__ == "__main__":
    unittest.main(verbosity=2)
