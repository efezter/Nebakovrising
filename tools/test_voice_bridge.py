"""Milestone 1 tests use the real Lua serializer and Python receiver; no game/API calls."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
from lupa.lua51 import LuaRuntime
from nebakov_voice_receiver import LogTail, PositionReceiver, decode_packet, write_snapshot

ROOT = Path(__file__).resolve().parents[1]
MOCKS = r"""
lines = {}; entities = {}; timers = {}; names = {}
nebakovrising = {Config = {voiceBridge = {sampleIntervalMs = 1000}},
    Roles = {Resolve = function() return {patrol = {}} end},
    Spawner = {GetSpawnedNames = function() return names end},
    Utils = {GetPlayer = function() return player end}}
System = {
    LogAlways = function(line) lines[#lines + 1] = line end,
    GetCurrTime = function() return 123.25 end,
    GetEntity = function(id) return entities[id] end,
    GetEntityIdByName = function(name)
        for id, entity in pairs(entities) do if entity:GetName() == name then return id end end
    end,
    GetEntitiesByClass = function() return entities end,
    AddCCommand = function() end,
    SpawnEntity = function() error('Bridge must never spawn an NPC') end,
}
Script = {SetTimerForFunction = function(delay, callback, data)
    timers[#timers + 1] = {delay = delay, callback = callback, data = data}
    return #timers
end}
UIAction = {RegisterEventSystemListener = function() end}
function makeEntity(id, name, x, y, z)
    local entity = {id = id, name = name, pos = {x=x,y=y,z=z}, actor = {IsDead = function() return false end}}
    function entity:GetName() return self.name end
    function entity:GetWorldPos() return self.pos end
    function entity:GetDirectionVector() return {x=0,y=1,z=0} end
    entities[id] = entity
    return entity
end
player = makeEntity(1, 'Henry', 10.25, 20, 30)
a = makeEntity(2, 'nebakovrising_MeleeGuard_2', 11, 22.5, 33)
b = makeEntity(3, 'nebakovrising_MeleeGuard_3', 15, 25, 35)
names = {a:GetName(), b:GetName()}
"""


class VoiceBridgeTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(MOCKS)
        self.lua.execute((ROOT / "src/Scripts/mods/nebakov_voice_bridge.lua").read_text(encoding="utf-8"))
        self.lua.execute("B = nebakovrising.VoiceBridge")

    def packets(self):
        return [decode_packet(line.encode("utf-8")) for _, line in self.lua.globals().lines.items() if "NEBAKOV_VOICE_V1 " in line]

    def test_existing_pair_registers_and_sends_real_lua_json(self):
        self.lua.execute("assert(B.BindExistingPair())")
        packet = self.packets()[-1]
        self.assertEqual({n["name"] for n in packet["npcs"]}, {"Marek", "Hertl"})
        self.assertEqual(packet["npcs"][0]["position"], {"x": 11, "y": 22.5, "z": 33})
        self.assertNotIn("reason", packet["npcs"][0])
        self.assertEqual(packet["player"]["position"]["x"], 10.25)
        self.assertIs(type(packet["seq"]), int)
        self.assertEqual(self.lua.eval("#timers"), 1)

    def test_duplicate_entity_rejected(self):
        self.lua.execute("assert(B.Register('Marek', a)); assert(not B.Register('Hertl', a))")

    def test_later_npc_despawn_and_reused_entity_id_are_safe(self):
        self.lua.execute("B.BindExistingPair(); entities[2] = nil; B.Emit('positions')")
        self.assertFalse(self.packets()[-1]["npcs"][0]["available"])
        self.lua.execute("makeEntity(2, 'unrelated', 0, 0, 0); B.Emit('positions')")
        self.assertEqual(self.packets()[-1]["npcs"][0]["reason"], "entity_replaced")

    def test_nonfinite_position_and_missing_player_do_not_crash(self):
        self.lua.execute("B.BindExistingPair(); a.pos.x = 0/0; player = nil; B.Emit('positions')")
        packet = self.packets()[-1]
        self.assertFalse(packet["npcs"][0]["available"])
        self.assertFalse(packet["player"]["available"])

    def test_old_timer_cannot_restart_after_stop_or_rebind(self):
        self.lua.execute("B.BindExistingPair(); old = timers[1].data; B.Stop(); B.Tick(old)")
        self.assertEqual(self.lua.eval("#timers"), 1)
        self.lua.execute("B.BindExistingPair(); B.Tick(old)")
        self.assertEqual(self.lua.eval("#timers"), 2)

    def test_gameplay_reload_clears_stale_references(self):
        self.lua.execute("B.BindExistingPair(); old = timers[1].data; B.OnGameplayStarted(); B.Tick(old)")
        packet = self.packets()[-1]
        self.assertEqual(packet["event"], "world_reset")
        self.assertFalse(any(n["available"] for n in packet["npcs"]))

    def test_restored_pair_lookup_excludes_vanilla_npcs_and_dead_guards(self):
        self.lua.execute("""
            names = {}
            makeEntity(4, 'aaa_vanilla_guard', 1, 1, 1)
            dead = makeEntity(5, 'nebakovrising_MeleeGuard_1', 1, 1, 1)
            dead.actor.IsDead = function() return true end
            assert(B.BindExistingPair())
        """)
        packet = self.packets()[-1]
        self.assertEqual([n["entity_name"] for n in packet["npcs"]], ["nebakovrising_MeleeGuard_2", "nebakovrising_MeleeGuard_3"])

    def test_json_escapes_log_control_characters(self):
        self.lua.execute("a.name = 'guard\\\"\\\\\\n'; B.Register('Marek', a); B.Register('Hertl', b); B.Emit('positions')")
        self.assertEqual(self.packets()[-1]["npcs"][0]["entity_name"], 'guard"\\\n')

    def test_lua_to_log_tail_to_python_snapshot(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tools", prefix=".voice-test-") as directory:
            path = Path(directory) / "kcd.log"
            path.write_bytes(b"existing game log\n")
            tail = LogTail(path)
            self.assertEqual(tail.poll(), [])
            self.lua.execute("B.BindExistingPair(); B.Emit('conversation_trigger')")
            with path.open("ab") as stream:
                for _, line in self.lua.globals().lines.items():
                    stream.write(line.encode("utf-8") + b"\n")
            receiver = PositionReceiver()
            accepted = [receiver.accept(decode_packet(line)) for line in tail.poll()]
            self.assertEqual(accepted[-1]["status"], "positions_ok")
            self.assertEqual(accepted[-1]["packet"]["event"], "conversation_trigger")
            self.assertFalse(accepted[-1]["generation_enabled"])
            write_snapshot(Path(directory) / "out", accepted[-1])
            saved = json.loads((Path(directory) / "out/latest_positions.json").read_text())
            self.assertEqual(saved["packet"]["player"]["position"]["x"], 10.25)


class LogReceiverTests(unittest.TestCase):
    def test_partial_line_truncation_and_replacement(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tools", prefix=".voice-test-") as directory:
            path = Path(directory) / "kcd.log"
            path.write_bytes(b"old\n")
            tail = LogTail(path)
            self.assertEqual(tail.poll(), [])
            with path.open("ab") as stream: stream.write(b"NEBAKOV_VOICE_V1 {\"part\"")
            self.assertEqual(tail.poll(), [])
            with path.open("ab") as stream: stream.write(b":1}\n")
            self.assertEqual(len(tail.poll()), 1)
            path.write_bytes(b"NEBAKOV_VOICE_V1 {}\n")
            self.assertEqual(len(tail.poll()), 1)
            replacement = Path(directory) / "new.log"
            replacement.write_bytes(b"NEBAKOV_VOICE_V1 {\"new\":true}\n")
            replacement.replace(path)
            self.assertEqual(len(tail.poll()), 1)

    def test_duplicate_sequence_retired_session_and_staleness(self):
        packet = {"session": "a", "seq": 1, "event": "positions", "npcs": [{"available": True}, {"available": True}], "player": {"available": True}}
        receiver = PositionReceiver()
        self.assertIsNotNone(receiver.accept(packet, now=1))
        self.assertIsNone(receiver.accept(packet, now=2))
        self.assertEqual(receiver.mark_stale(5, now=7)["status"], "stale")
        self.assertEqual(receiver.accept({**packet, "seq": 2}, now=8)["status"], "positions_ok")
        receiver.accept({**packet, "session": "b"}, now=9)
        self.assertIsNone(receiver.accept({**packet, "seq": 3}, now=10))


if __name__ == "__main__":
    unittest.main(verbosity=2)
