"""Catalog discovery, persistent Lua assignments and service voice identity."""
import io
import json
from pathlib import Path
import queue
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import wave

from lupa.lua51 import LuaRuntime
import test_meal_flow as meal
from test_patrol_conversations import SETUP
from nebakov_voice_samples import discover, reference, line_reference
from nebakov_voice_director import CommandOutbox, command_source
from nebakov_voice_engine_adapter import worker_main

ROOT=Path(__file__).resolve().parents[1]

def wav(path, seconds=6):
    with wave.open(str(path),'wb') as f:
        f.setparams((1,2,24000,0,'NONE','not compressed'));f.writeframes(b'\0\0'*int(seconds*24000))

def info(path):
    with wave.open(str(path)) as f: return types.SimpleNamespace(duration=f.getnframes()/f.getframerate())

class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'tools');self.folder=Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        stub=patch.dict(sys.modules,{'soundfile':types.SimpleNamespace(info=info)})
        stub.start();self.addCleanup(stub.stop)

    def test_new_files_and_both_prefixes_are_discovered_without_a_fixed_count(self):
        for name in ['guard1.wav','guard2.wav','guard10.wav','guards16.wav','marek.wav']: wav(self.folder/name)
        self.assertEqual(discover(self.folder)['ids'],['guard1.wav','guard2.wav','guard10.wav','guards16.wav'])
        wav(self.folder/'guards_new.wav')
        self.assertIn('guards_new.wav',discover(self.folder)['ids'])

    def test_short_reference_is_not_assigned_and_bad_default_is_reported(self):
        wav(self.folder/'guard1.wav');wav(self.folder/'guard2.wav',2)
        catalog=discover(self.folder)
        self.assertEqual(catalog['ids'],['guard1.wav']);self.assertIn('guard2.wav',catalog['rejected'])
        wav(self.folder/'guard1.wav',4)
        with self.assertRaisesRegex(ValueError,'exceed 5'): discover(self.folder)

    def test_path_escape_and_request_manifest_conflict_are_rejected(self):
        wav(self.folder/'guard1.wav')
        with self.assertRaises(ValueError):reference(self.folder,'../guard1.wav')
        with self.assertRaises(ValueError):line_reference(self.folder,{'speaker':'Marek','voicesampleid':'guard1.wav'},{'Marek':'guard2.wav'})
        self.assertEqual(line_reference(self.folder,{'speaker':'Marek'},{'Marek':'guard1.wav'}).name,'guard1.wav')

    def test_catalog_is_sent_before_ready_and_repeated_after_session_change(self):
        catalog={'ids':['guard1.wav','guards_extra.wav'],'fallback':'guard1.wav'}
        out=CommandOutbox(self.folder/'command.lua',lambda *a,**kw:None,catalog)
        out.observe({'session':'s','director':{}},0);out.tick(0,True)
        self.assertIn('voice_catalog',out.path.read_text())
        out.observe({'session':'s','director':{'control':{'peer':out.peer,'seq':1,'accepted':True}}},1)
        out.tick(1,True);self.assertEqual(out.pending['kind'],'heartbeat_ready')
        out.observe({'session':'new','director':{}},2);out.tick(2,True)
        self.assertEqual(out.pending['kind'],'voice_catalog')
        with self.assertRaises(ValueError):command_source('p',1,'voice_catalog','s','','guard1.wav,bad".wav','guard1.wav')

    def test_adapter_carries_identity_in_http_request_and_each_line(self):
        engine=types.SimpleNamespace(OUTPUT_DIR=self.folder,GEMINI_MODEL='fake')
        engine.render_with_chatterbox=lambda folder:self.fail('Expected explicit voicesampleid request')
        engine.generate_conversation=lambda *a,**k:[{'speaker':'Marek' if i%2 else 'Hertl','text':'hello'} for i in range(1,5)]
        samples={'Marek':'guard2.wav','Hertl':'guards_new.wav'}
        requests=[]
        def http(request,**kwargs):
            if isinstance(request,str):return io.BytesIO(b'{"status":"ready"}')
            body=json.loads(request.data);requests.append(body)
            self.assertEqual(body['voicesampleid'],samples)
            folder=self.folder/body['conversation_folder']
            rows=json.loads((folder/'conversation.json').read_text())['lines']
            for row in rows:
                self.assertEqual(row['voicesampleid'],samples[row['speaker']])
                audio=folder/row['audio_file'];audio.parent.mkdir(exist_ok=True);wav(audio,.1)
            return io.BytesIO(b'{"status":"ok"}')
        commands,results=queue.Queue(),queue.Queue()
        commands.put({'id':'j','session':'s','context':'patrol','voicesampleid':samples});commands.put(None)
        with patch.dict(sys.modules,{'conversation_engine':engine}),patch.dict('os.environ',{'GEMINI_API_KEY':'fixture'}),patch('urllib.request.urlopen',side_effect=http):
            worker_main(commands,results,str(self.folder))
        self.assertEqual(results.get_nowait()['kind'],'ready')
        self.assertEqual(results.get_nowait()['kind'],'result');self.assertEqual(len(requests),1)

class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(meal.MOCKS)
        self.lua.execute((ROOT/'src/Scripts/mods/CastleUtils.lua').read_text())
        self.lua.execute(SETUP)
        self.lua.execute("nebakovrising.Roles.Resolve=function() return {id='guard_melee',bedPool='guard'} end")
        self.lua.execute((ROOT/'src/Scripts/mods/nebakov_voice_registry.lua').read_text())
        self.lua.execute("V=nebakovrising.Voices; records={};store.health.nebakovNpcRecords=records;function add(n) makeEntity(n,n);records[n]={managed=true} end")

    def apply(self,count=15):
        ids=','.join(f'guard{i}.wav' for i in range(1,count+1))
        self.assertTrue(self.lua.globals().V.Apply(ids,'guard1.wav'))

    def test_first_fifteen_unique_then_overflow_uses_guard1(self):
        self.apply()
        self.lua.execute("for i=1,17 do add('g'..i);V.Reconcile() end;seen={};for i=1,15 do local id=records['g'..i].voicesampleid;assert(not seen[id]);seen[id]=true end;assert(records.g16.voicesampleid=='guard1.wav' and records.g17.voicesampleid=='guard1.wav')")

    def test_save_reload_catalog_growth_and_streaming_preserve_voices(self):
        self.apply(2)
        self.lua.execute("add('g1');add('g2');V.Reconcile();one=records.g1.voicesampleid;two=records.g2.voicesampleid;entities.g1=nil;V.Reset();assert(records.g1.voicesampleid==one and records.g2.voicesampleid==two)")
        self.apply(3)
        self.lua.execute("add('g3');V.Reconcile();assert(records.g3.voicesampleid=='guard3.wav');assert(records.g1.voicesampleid==one)")

    def test_death_releases_voice_for_a_new_guard(self):
        self.apply(2)
        self.lua.execute("add('g1');add('g2');V.Reconcile();freed=records.g1.voicesampleid;entities.g1.dead=true;V.Reconcile();assert(records.g1.voicesampleid==nil);add('g3');V.Reconcile();assert(records.g3.voicesampleid==freed)")

    def test_removed_file_uses_fallback_without_rewriting_saved_identity(self):
        self.apply(2)
        self.lua.execute("add('g');records.g.voicesampleid='guard2.wav'")
        self.apply(1)
        self.lua.execute("assert(records.g.voicesampleid=='guard2.wav');assert(V.Get('g')=='guard1.wav')")

    def test_hostile_or_duplicate_names_do_not_change_saved_catalog(self):
        self.apply(2)
        for csv in ['guard1.wav,../guard2.wav','guard1.wav,guard1.wav','guard1.wav,','x.wav']:
            self.assertFalse(self.lua.globals().V.Apply(csv,'guard1.wav'))
        self.assertEqual(len(self.lua.globals().V.ids),2)

class CatalogIntegrationTests(unittest.TestCase):
    def test_catalog_ack_persisted_assignments_telemetry_and_generation_job(self):
        from test_patrol_conversations import LuaDirectorTests
        from nebakov_voice_runtime import Worker
        fixture=LuaDirectorTests();fixture.setUp();lua=fixture.lua
        lua.execute((ROOT/'src/Scripts/mods/nebakov_voice_registry.lua').read_text())
        lua.execute("local old=nebakovrising.Roles.Resolve;nebakovrising.Roles.Resolve=function(n) local r=old(n);r.bedPool='guard';return r end;records.guard_a={managed=true};records.guard_b={managed=true};D.peer=nil")
        with tempfile.TemporaryDirectory(dir=ROOT/'tools') as temp:
            out=CommandOutbox(Path(temp)/'command.lua',lambda *a,**k:None,
                {'ids':['guard1.wav','guards_extra.wav'],'fallback':'guard1.wav'})
            lua.globals().read_control=lambda path:out.path.read_text()
            lua.execute('dofile=function(path) return assert(loadstring(read_control(path)))() end')
            for step in range(5):
                packet=fixture.packet();out.observe(packet,step);out.tick(step,True)
                lua.execute('D.Tick({generation=D.generation})')
            lua.execute('assert(D.peer.ready and D.peer.hasCatalog);assert(D.TryStart(true))')
            packet=fixture.packet()
            ids={npc['name']:npc['voicesampleid'] for npc in packet['npcs']}
            self.assertEqual(set(ids.values()),{'guard1.wav','guards_extra.wav'})
            worker=Worker.__new__(Worker);worker.ready=True;worker.busy=None
            worker.commands=queue.Queue();worker.emit=lambda *a,**k:None
            worker.submit(packet)
            self.assertEqual(worker.commands.get_nowait()['voicesampleid'],ids)
