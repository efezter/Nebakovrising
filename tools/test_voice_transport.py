"""Snapshot negotiation, partial writes, fallback, bounded storage and config preservation."""
import json
from pathlib import Path
import tempfile
import unittest

from nebakov_voice_transport import FileSnapshot, BoundedJournal, MAX_PACKET_BYTES, lua_path
from nebakov_voice_director import CommandOutbox
from nebakov_voice_defaults import ensure_defaults
from nebakov_voice_receiver import MARKER, decode_packet
import test_patrol_conversations as patrol


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)/'nebakov_voice'
        self.folder.mkdir()
        self.path = self.folder/'telemetry.json'
        self.fixture = patrol.LuaDirectorTests(); self.fixture.setUp()
        self.lua = self.fixture.lua
        self.lua.globals().target = str(self.path)

    def emit(self):
        self.lua.execute("B.Emit('director_status')")

    def logged(self):
        return [s for _,s in self.lua.globals().lines.items() if MARKER.decode() in s]

    def test_console_stops_only_after_fresh_file_proof_and_confirmation(self):
        self.lua.execute('D.peer=nil')
        reader = FileSnapshot(self.path)
        out = CommandOutbox(self.folder/'command.lua', lambda *a,**k:None, telemetry_file=self.path)
        packet = self.fixture.packet(); out.observe(packet,0); out.tick(0,True)
        self.assertEqual(out.pending['kind'],'telemetry_probe')
        self.lua.execute(out.path.read_text())
        self.emit()
        packet = decode_packet(self.logged()[-1].encode()); out.observe(packet,.1)
        # A log ACK alone cannot disable console packets.
        out.tick(.1,True)
        self.assertNotEqual(out.pending['kind'],'telemetry_confirm')
        self.lua.execute(out.path.read_text()); self.emit()
        packet=reader.poll(); self.assertIsNotNone(packet)
        out.note_file(packet); out.observe(packet,.2); out.tick(.2,True)
        self.assertEqual(out.pending['kind'],'telemetry_confirm')
        self.lua.execute(out.path.read_text())
        count=len(self.logged()); self.emit()
        self.assertEqual(len(self.logged()),count)
        self.assertEqual(reader.poll()['transport']['mode'],'file')
        # A later write error reopens console transport and does not lose telemetry.
        self.lua.execute("io.open=function() return nil,'denied' end")
        self.emit()
        self.assertEqual(len(self.logged()),count+1)
        packet=decode_packet(self.logged()[-1].encode())
        self.assertEqual(packet['transport']['mode'],'log')
        out.observe(packet,.3)
        self.assertFalse(out.confirm_sent)

    def test_no_io_keeps_log_and_rejects_premature_confirmation(self):
        self.lua.execute('io=nil;assert(B.ConfigureTelemetry(target,false));assert(not B.ConfigureTelemetry(target,true))')
        self.emit(); self.emit()
        self.assertEqual(len(self.logged()),2)
        packet=decode_packet(self.logged()[-1].encode())
        self.assertEqual(packet['transport']['file_status'],'unavailable')
        warnings=[s for _,s in self.lua.globals().lines.items() if 'File telemetry unavailable' in s]
        self.assertEqual(len(warnings),1)

    def test_ignores_leftover_and_retries_partial_snapshot(self):
        self.path.write_text(json.dumps(self.fixture.packet()))
        reader=FileSnapshot(self.path)
        self.assertIsNone(reader.poll())
        self.path.write_text('{"protocol":')
        self.assertIsNone(reader.poll()); self.assertIsNotNone(reader.last_error)
        packet=self.fixture.packet(); self.path.write_text(json.dumps(packet))
        self.assertEqual(reader.poll()['seq'],packet['seq'])
        self.assertIsNone(reader.poll())
        self.path.write_bytes(b'x'*(MAX_PACKET_BYTES+1))
        self.assertIsNone(reader.poll())

    def test_snapshot_is_overwritten_instead_of_appended(self):
        self.lua.execute('assert(B.ConfigureTelemetry(target,false))')
        self.emit(); first=self.path.stat().st_size
        for _ in range(100): self.emit()
        self.assertLess(self.path.stat().st_size,first+16)
        self.assertEqual(json.loads(self.path.read_text())['seq'],101)

    def test_paths_reject_control_characters_and_escape_quotes(self):
        for value in ['bad.lua','x\n/nebakov_voice/telemetry.json','x\0/nebakov_voice/telemetry.json']:
            with self.assertRaises(ValueError): lua_path(value)
            self.assertFalse(self.lua.globals().B.ConfigureTelemetry(value,False))
        value='C:/a"quoted/nebakov_voice/telemetry.json'
        self.assertEqual(self.lua.eval(lua_path(value)),value)

    def test_existing_settings_and_profile_are_never_overwritten(self):
        root=ensure_defaults(self.folder/'config')
        settings=root/'conversations.json'; profile=root/'prompts/patrol-daily-talk.json'
        custom=json.loads(settings.read_text()); custom.update(randomMinSeconds=20,randomMaxSeconds=50)
        settings.write_text(json.dumps(custom)); profile.write_text('custom profile')
        before=settings.read_bytes(),profile.read_bytes()
        ensure_defaults(root)
        self.assertEqual((settings.read_bytes(),profile.read_bytes()),before)

    def test_event_journal_rotates_and_trims_legacy_file(self):
        path=self.folder/'events.jsonl'
        path.write_bytes(b'old record\n'*1000)
        with BoundedJournal(path,max_bytes=512,backups=2) as journal:
            for i in range(200): journal.write(json.dumps({'event':'test','i':i})+'\n')
        files=list(self.folder.glob('events.jsonl*'))
        self.assertEqual(len(files),3)
        for p in files:
            self.assertLessEqual(p.stat().st_size,512)
            for line in p.read_text().splitlines(): json.loads(line)
        self.assertEqual(json.loads(path.read_text().splitlines()[-1])['i'],199)


if __name__=='__main__': unittest.main()
