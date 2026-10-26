"""Natural patrol scheduling, editable profiles and prepare-before-meeting flow."""
from copy import deepcopy
import io
import json
from pathlib import Path
import queue
import random
import tempfile
import types
import unittest
from unittest.mock import patch
import wave

import test_patrol_conversations as patrol
import test_voice_runtime as audio
from nebakov_voice_config import load_config, validate, encode_settings
from nebakov_voice_prompts import PromptProfiles
from nebakov_voice_director import command_source, CommandOutbox, PatrolController
from nebakov_voice_engine_adapter import worker_main
from nebakov_voice_runtime import Settings
from nebakov_voice_playback import SequentialPlayback

ROOT=Path(__file__).resolve().parent
from nebakov_voice_defaults import ensure_defaults
_DEFAULT_TEMP=tempfile.TemporaryDirectory()
_DEFAULT_ROOT=ensure_defaults(_DEFAULT_TEMP.name)
CONFIG=_DEFAULT_ROOT/'conversations.json'
PROFILES=_DEFAULT_ROOT/'prompts'
def tearDownModule(): _DEFAULT_TEMP.cleanup()

class ConfigAndPromptTests(unittest.TestCase):
    def test_config_rejects_bad_window_nan_types_and_code_injection(self):
        settings=load_config(CONFIG)
        for key,value in [('nearbyDistance',0),('searchRadius',float('nan')),('randomMinSeconds',0),
                          ('randomEnabled','yes'),('profileId','x");bad()')]:
            with self.subTest(key=key),self.assertRaises(ValueError):validate(dict(settings,**{key:value}))
        csv,profile=encode_settings(settings)
        source=command_source('p',1,'conversation_config','s','',csv,profile)
        self.assertIn('conversation_config',source)
        with self.assertRaises(ValueError):command_source('p',1,'conversation_config','s','',csv+';bad()',profile)

    def test_topics_cycle_without_repeating_and_lua_event_parameters_are_preserved(self):
        profiles=PromptProfiles(PROFILES,random.Random(8))
        packet={'director':{'behavior':'patrol','profile_id':'patrol-daily-talk','context':{
            'hour':11.5,'location':'Nebakov Castle','guard_a':'guard_runtime_a','guard_b':'guard_runtime_b',
            'event_kind':'rain_started','event_text':'Rain has just started at the gate.'}}}
        size=len(profiles.load('patrol-daily-talk')['topics'])
        rows=[profiles.prepare(packet) for _ in range(size+1)]
        self.assertEqual(len({r['prompt_parameters']['topic'] for r in rows[:size]}),size)
        self.assertNotEqual(rows[size-1]['prompt_parameters']['topic'],rows[size]['prompt_parameters']['topic'])
        self.assertIn('Rain has just started at the gate.',rows[0]['text'])
        self.assertEqual(rows[0]['prompt_parameters']['hour'],'11.5')
        self.assertIn('guard_runtime_a',rows[0]['text'])

    def test_new_profile_is_loaded_from_json_without_code_changes(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            folder=Path(temp)
            (folder/'custom-event.json').write_text(json.dumps({'version':1,'id':'custom-event',
                'template':'$location: $event_text $custom_fact Topic: $topic','topics':['one']}))
            packet={'director':{'behavior':'patrol','profile_id':'custom-event',
                'context':{'location':'Gate','event_text':'Quiet watch.','custom_fact':'A bell was heard.'}}}
            self.assertIn('A bell was heard.',PromptProfiles(folder).prepare(packet)['text'])
            with self.assertRaises(ValueError):PromptProfiles(folder).load('../bad')

    def test_prewarm_calls_existing_service_before_worker_is_ready(self):
        engine=types.SimpleNamespace(render_with_chatterbox=lambda folder:None)
        requests=[]
        def http(request,**kwargs):
            requests.append(request)
            if isinstance(request,str):return io.BytesIO(b'{"status":"ready","default_model":"turbo","active_model":null}')
            self.assertIn('/model/switch',request.full_url)
            self.assertEqual(json.loads(request.data),{'model':'turbo'})
            return io.BytesIO(b'{"status":"ok"}')
        commands,results=queue.Queue(),queue.Queue();commands.put(None)
        with patch.dict('sys.modules',{'conversation_engine':engine}),patch.dict('os.environ',{'GEMINI_API_KEY':'fixture','NEBAKOV_TTS_MODEL':'turbo'}),patch('urllib.request.urlopen',side_effect=http):
            worker_main(commands,results,str(ROOT),True)
        self.assertEqual(results.get_nowait()['kind'],'ready');self.assertEqual(len(requests),2)

    def test_play_command_is_queued_before_an_unnecessary_idle_heartbeat(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            out=CommandOutbox(Path(temp)/'command.lua',lambda *a,**k:None)
            controller=PatrolController(Settings(),audio.Playback(),lambda p:None,lambda *a,**k:None,out,lambda:True)
            packet=audio.packet();packet['director']={'id':'c','phase':'waiting_audio','enabled':True,
                'in_nebakov':True,'behavior':'patrol','owner':out.peer,'arrived':True,'audio_ready':True}
            controller.session='s';controller.conversation='c';controller.started=0
            controller.manifest=Path('already_validated.wav');controller.state='waiting_arrival'
            controller.ingest(packet,0);controller.tick(.1)
            self.assertEqual(out.pending['kind'],'playing')

class NaturalLuaTests(unittest.TestCase):
    packet=patrol.LuaDirectorTests.packet
    def setUp(self):
        patrol.LuaDirectorTests.setUp(self)
        self.settings=load_config(CONFIG)
        csv,profile=encode_settings(self.settings)
        self.assertTrue(self.lua.globals().nebakovrising.ConversationConfig.Apply(csv,profile))

    def select(self):self.lua.execute('assert(D.TryStart(true))')

    def test_generation_does_not_preempt_patrol_and_commit_refreshes_activity_tokens(self):
        self.select()
        self.lua.execute("""
            assert(D.active.phase=='preparing_audio' and not D.HasRequest(a.this.id,ta))
            assert(C.activityRuns[tostring(a.this.id)].conversationId==nil)
            assert(C.FinishNpcActivity(a.this.id,ta))
            ta=begin(a,'patrol');D.SetPatrolPose(a,ta,'guard');assert(D.CheckActive())
            assert(D.Receive('peer',D.peer.seq+1,'audio_ready',B.session,D.active.id))
            assert(D.active.phase=='reserved' and D.active.audioReady)
            assert(D.HasRequest(a.this.id,ta) and D.HasRequest(b.this.id,tb))
            assert(C.activityRuns[tostring(a.this.id)].conversationId==D.active.id)
        """)

    def test_combat_during_generation_discards_meeting_without_freezing_other_guard(self):
        self.select()
        self.lua.execute("b.combat=true;assert(not D.Receive('peer',D.peer.seq+1,'audio_ready',B.session,D.active.id));assert(D.active==nil);assert(C.activityRuns[tostring(a.this.id)].conversationId==nil)")

    def test_conversations_have_no_hour_window_for_eligible_awake_guards(self):
        # IsNpcSleepTime/PatrolShouldStop are activity policy; isolate the removed
        # global hour gate with awake on-duty guards at each clock boundary.
        for hour in [0,3,7.99,8,19.99,20,23.99]:
            self.setUp()
            self.lua.globals().worldHour=hour
            self.lua.execute("C.PatrolShouldStop=function() return false end;assert(D.TryStart(true));assert(D.CheckActive())")

    def test_random_attempt_skips_missing_pair_and_schedules_next_configured_interval(self):
        self.lua.execute("C.activityRuns[tostring(b.this.id)].kind='meal_table';D.nextRandom=clock;D.Tick({generation=D.generation});assert(D.active==nil);assert(D.lastAttempt.reason=='two_eligible_patrol_npcs_required' and not D.lastAttempt.manual);assert(D.nextRandom>=clock+120 and D.nextRandom<=clock+240)")

    def test_outside_region_does_not_scan_guard_candidates(self):
        self.lua.execute("worldLoaded=false;D.IsPatrolling=function() error('Unexpected NPC scan') end;D.nextRandom=clock;D.Tick({generation=D.generation});assert(D.lastAttempt==nil and D.active==nil)")

    def test_event_context_from_lua_reaches_profile_and_new_event_invalidates_pending_text(self):
        self.lua.execute("assert(D.SetEventContext('gate_bell','A bell has just sounded at the gate.',120))")
        self.select()
        prepared=PromptProfiles(PROFILES).prepare(self.packet())
        self.assertEqual(prepared['profile_id'],'patrol-daily-talk')
        self.assertIn('A bell has just sounded at the gate.',prepared['text'])
        self.lua.execute("assert(D.SetEventContext('new_bell','A second bell sounds.',120));assert(not D.CheckActive());assert(D.last.reason=='context_changed')")

    def test_death_event_is_reported_only_when_actor_death_is_verified(self):
        self.lua.execute("""
            local old=nebakovrising.Roles.Resolve
            nebakovrising.Roles.Resolve=function(n) local r=old(n);r.bedPool='guard';return r end
            records[a:GetName()]={managed=true};C.RemoveManagedNpcRecord(a:GetName())
            assert(D.recentEvent==nil)
            records[b:GetName()]={managed=true};b.dead=true;C.RemoveManagedNpcRecord(b:GetName())
            assert(D.recentEvent.kind=='garrison_death')
        """)

    def test_soft_preparation_allows_patrol_to_continue_but_revalidates_actual_radius(self):
        self.select()
        self.lua.execute("C.FinishNpcActivity(a.this.id,ta);ta=begin(a,'patrol');D.SetPatrolPose(a,ta,'guard');assert(D.CheckActive());a.pos.x=21;assert(not D.CheckActive());assert(D.last.reason=='player_out_of_range')")

    def test_settings_handshake_applies_data_and_rejects_invalid_payload_atomically(self):
        csv,profile=encode_settings(dict(self.settings,randomMinSeconds=5,randomMaxSeconds=10))
        self.assertTrue(self.lua.globals().D.Receive('peer',2,'conversation_config',self.lua.globals().B.session,'',csv,profile))
        self.lua.execute("assert(D.peer.hasSettings);assert(nebakovrising.Config.conversations.randomMinSeconds==5)")
        self.assertFalse(self.lua.globals().D.Receive('peer',3,'conversation_config',self.lua.globals().B.session,'','bad','../bad'))
        self.lua.execute("assert(nebakovrising.Config.conversations.randomMinSeconds==5)")

    def test_full_ready_first_protocol_commits_after_audio_then_plays_only_after_turn(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            folder=Path(temp);manifest=folder/'conversation.json';rows=[]
            for i in range(1,5):
                name=f'{i}.wav'
                with wave.open(str(folder/name),'wb') as f:
                    f.setparams((1,2,24000,0,'NONE','not compressed'));f.writeframes(b'\0\0'*2400)
                rows.append({'index':i,'speaker':'Marek' if i%2 else 'Hertl','audio_file':name})
            manifest.write_text(json.dumps({'lines':rows}))
            events=[];emit=lambda event,**kw:events.append((event,kw))
            out=CommandOutbox(folder/'command.lua',emit,settings=self.settings)
            self.lua.globals().read_control=lambda path:out.path.read_text()
            self.lua.execute("D.peer=nil;dofile=function(path) return assert(loadstring(read_control(path)))() end")
            sound=audio.Audio();playback=SequentialPlayback(sound,emit)
            jobs=[];submit=lambda packet:jobs.append(deepcopy(packet)) or 'job'
            controller=PatrolController(Settings(stale_after=4),playback,submit,emit,out,lambda:True)
            selected=False;drivers=[];result_sent=False
            for i in range(350):
                self.lua.execute('clock=clock+0.1;C.ActivityHeartbeat(a.this.id,ta);C.ActivityHeartbeat(b.this.id,tb)')
                if not selected and self.lua.eval('D.peer~=nil and D.peer.ready'):
                    self.select();selected=True
                if jobs and not result_sent and i>30:
                    self.lua.execute('assert(D.active.phase=="preparing_audio");assert(not D.HasRequest(a.this.id,ta))')
                    controller.result('job',manifest,None,i*.1);result_sent=True
                if not drivers and self.lua.eval("D.active~=nil and D.active.phase=='reserved'"):
                    g=self.lua.globals();p1=g.D.active.participants[1];p2=g.D.active.participants[2]
                    drivers=[patrol.ConversationDriver(self.lua,g.System.GetEntity(p.entityId),p.token) for p in [p1,p2]]
                for driver in drivers:
                    if driver.generator:next(driver.generator)
                self.lua.execute('D.Tick({generation=D.generation})')
                packet=self.packet();controller.ingest(packet,i*.1);controller.tick(i*.1)
                if sound.busy:
                    self.assertTrue(packet['director']['arrived']);self.assertEqual(packet['director']['phase'],'playing')
                sound.busy=False
                if any(e=='conversation_finished' for e,_ in events):break
            self.assertEqual(len(jobs),1)
            self.assertEqual([line.speaker for line,_ in sound.played],['Marek','Hertl','Marek','Hertl'])
            self.assertTrue(any(e=='conversation_finished' for e,_ in events))
