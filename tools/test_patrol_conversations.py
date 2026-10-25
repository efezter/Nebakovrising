"""Real Lua director + Python control protocol; navigation/audio are explicit mocks."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import wave
import xml.etree.ElementTree as ET

from lupa.lua51 import LuaRuntime
import test_meal_flow as meal_tests
from meal_bt_driver import MealBtDriver
from nebakov_voice_receiver import decode_packet, PositionReceiver
from nebakov_voice_director import CommandOutbox, PatrolController, command_source
from nebakov_voice_playback import SequentialPlayback
from nebakov_voice_runtime import Settings, build_context
import test_voice_runtime as audio_tests

ROOT = Path(__file__).resolve().parents[1]
SETUP = r"""
worldHour = 12; lines = {}; timers = {}; worldLoaded = true
dofile = function(path) error('Fixture has no loose script: ' .. path) end
nebakovrising.Config.conversations = {
 enabled=true,searchRadius=20,playerExitRadius=30,regionCenter={x=0,y=0,z=0},
 regionRadius=100,regionExitRadius=110,regionHeight=30,randomMinSeconds=30,randomMaxSeconds=60,
 cooldownSeconds=120,npcCooldownSeconds=180,approachDistance=1.3,arrivalDistance=1.8,
 preparationTimeout=30,approachTimeout=35,conversationTimeout=150,peerTimeout=12,patrolHeartbeatMaxAge=2.5}
nebakovrising.Config.voiceBridge = {sampleIntervalMs=250}
nebakovrising.Utils = {GetPlayer=function() return player end, Log=function(s) lines[#lines+1]=s end}
nebakovrising.Spawner = {GetSpawnedNames=function() return {} end}
local makeOriginal = makeEntity
function makeEntity(name, wuid)
 local entity = makeOriginal(name,wuid)
 entity.pos={x=0,y=0,z=0}; entity.dead=false; entity.combat=false
 function entity:GetWorldPos() return self.pos end
 function entity:GetDirectionVector() return self.dir or {x=0,y=1,z=0} end
 function entity:GetAngles() local f=self:GetDirectionVector();return {x=0,y=0,z=math.atan2(-f.x,f.y)} end
 function entity:SetAngles(a) self.dir={x=-math.sin(a.z),y=math.cos(a.z),z=0} end
 entity.actor={IsDead=function() return entity.dead end, IsUnconscious=function() return false end}
 entity.soul={HasScriptContext=function() return entity.combat end}
 entity.faceStarts={};entity.faceStops={}
 function entity:GetAnimationLength(slot,clip) return 2 end
 function entity:StartAnimation(slot,clip,layer,blend,speed,loop)
  self.faceStarts[#self.faceStarts+1]={slot=slot,clip=clip,layer=layer,loop=loop};return true
 end
 function entity:StopAnimation(slot,layer) self.faceStops[#self.faceStops+1]={slot=slot,layer=layer} end
 entities[entity.id]=entity
 return entity
end
System.LogAlways=function(s) lines[#lines+1]=s end
System.AddCCommand=function() end
local getEntityId=System.GetEntityIdByName
System.GetEntityIdByName=function(name)
 if name=='trosecko' then return worldLoaded and 'trosecko' or nil end
 return getEntityId(name)
end
Script={SetTimerForFunction=function(delay,fn,data) timers[#timers+1]={delay=delay,data=data};return #timers end,
 LoadScript=function() return true end}
UIAction={RegisterEventSystemListener=function() end}
player=makeEntity('Henry','player')
a=diner('guard_a'); a.pos={x=3,y=0,z=0}; ta=begin(a,'patrol')
b=diner('guard_b'); b.pos={x=9,y=0,z=0}; tb=begin(b,'patrol')
function turnToward(e,target)
 local a,b=e:GetWorldPos(),target:GetWorldPos();e.dir={x=b.x-a.x,y=b.y-a.y,z=0}
end
function facePair()
 turnToward(e1,e2);turnToward(e2,e1)
 assert(D.Faced(e1,p1.token));assert(D.Faced(e2,p2.token))
end
"""


class ConversationDriver(MealBtDriver):
    def __init__(self, lua, entity, token, blocked=False):
        super().__init__(lua, ROOT/'src/AI/nebakovrising_meal.xml', entity, token)
        self.functions.update({t.get('name'): t for t in ET.parse(ROOT/'src/AI/nebakovrising_conversation.xml').getroot()})
        self.blocked = blocked
        self.generator = self.function('nebakovrising_patrol_conversation', token)

    def function(self, name, token):
        tree = self.functions[name]
        data = self.lua.table(activityToken=token)
        for variable in tree.find('Variables'):
            value = variable.get('values','')
            if variable.get('type') == 'vec3':
                data[variable.get('name')] = self.lua.table(x=0,y=0,z=0)
            else:
                data[variable.get('name')] = value == 'true' if value in ('true','false') else None
        return (yield from self.node(tree.find('Root/Behavior')[0], data))

    def node(self, node, data):
        if node.tag == 'MoveParamsDecorator':
            return (yield from self.sequence(node,data))
        if node.tag == 'Move':
            self.events.append(('move',self.stance))
            assert self.stance == 'standing'
            while self.blocked:
                yield
            self.entity.pos = self.lua.table(x=data.target.x,y=data.target.y,z=data.target.z)
            yield
            return True
        if node.tag == 'Turn':
            other=self.lua.globals().XGenAIModule.GetEntityByWUID(data.partner)
            self.lua.globals().turnToward(self.entity,other)
            self.events.append(('turn',data.partner))
            yield
            return True
        return (yield from super().node(node,data))


class LuaDirectorTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(meal_tests.MOCKS)
        self.lua.execute((ROOT/'src/Scripts/mods/CastleUtils.lua').read_text('utf-8'))
        self.lua.execute(SETUP)
        self.lua.execute((ROOT/'src/Scripts/mods/nebakov_voice_bridge.lua').read_text('utf-8'))
        self.lua.execute((ROOT/'src/Scripts/mods/nebakov_voice_face.lua').read_text('utf-8'))
        self.lua.execute((ROOT/'src/Scripts/mods/nebakov_conversations.lua').read_text('utf-8'))
        self.lua.execute("C=nebakovrising.CastleUtils; B=nebakovrising.VoiceBridge; D=nebakovrising.Conversations; B.NewSession(); D.Start(); assert(D.Receive('peer',1,'heartbeat_ready',B.session,''))")

    def start(self):
        self.lua.execute('assert(D.TryStart(true))')

    def keep_alive(self):
        self.lua.execute("C.ActivityHeartbeat(a.this.id,ta); C.ActivityHeartbeat(b.this.id,tb); D.Receive('peer', D.peer.seq+1,'heartbeat_busy',B.session,'')")

    def packet(self):
        self.lua.execute("B.Emit('director_status')")
        lines = [s for _,s in self.lua.globals().lines.items() if 'NEBAKOV_VOICE_V1 ' in s]
        return decode_packet(lines[-1].encode())

    def prepare(self):
        self.lua.execute("p1=D.active.participants[1]; p2=D.active.participants[2]; e1=System.GetEntity(p1.entityId); e2=System.GetEntity(p2.entityId); assert(D.Prepare(e1,p1.token)); plan=D.Prepare(e2,p2.token)")

    def test_role_is_not_enough_actual_patrol_and_fresh_heartbeat_required(self):
        for change in ["C.activityRuns[tostring(b.this.id)].kind='meal_table'",
                       "C.activityRuns[tostring(b.this.id)].started=false",
                       "C.activityRuns[tostring(b.this.id)].heartbeat=clock-3",
                       'b.dead=true','b.combat=true']:
            self.setUp()
            self.lua.execute(change)
            self.assertFalse(self.lua.eval('D.TryStart(true)')[0])

    def test_region_world_proximity_and_peer_gates(self):
        for change, reason in [('worldLoaded=false','outside_nebakov'),
                               ('player.pos.x=200','outside_nebakov'),
                               ('b.pos.x=25','two_eligible_patrol_npcs_required'),
                               ('D.peer=nil','python_not_connected'),
                               ('D.peer.ready=false','python_not_ready')]:
            self.setUp(); self.lua.execute(change)
            result = self.lua.eval('D.TryStart(true)')
            self.assertEqual(result,(False,reason))

    def test_reservation_is_atomic_and_second_request_cannot_take_pair(self):
        self.start()
        self.assertEqual(self.lua.eval('D.TryStart(true)'),(False,'conversation_active'))
        self.lua.execute('assert(C.activityRuns[tostring(a.this.id)].conversationId == D.active.id); assert(C.activityRuns[tostring(b.this.id)].conversationId == D.active.id)')

    def test_audio_and_arrival_are_both_required_for_play_authorization(self):
        self.start(); self.prepare()
        self.lua.execute("assert(not D.Receive('peer',2,'playing',B.session,D.active.id)); assert(D.Receive('peer',3,'audio_ready',B.session,D.active.id)); assert(not D.Receive('peer',4,'playing',B.session,D.active.id)); e2.pos=plan.target; assert(D.Arrived(e2,p2.token)); assert(not D.active.arrived); facePair(); assert(D.Receive('peer',5,'playing',B.session,D.active.id)); assert(D.Receive('peer',6,'finished',B.session,D.active.id)); assert(D.active==nil)")

    def test_meeting_does_not_allow_speech_until_both_guards_face_each_other(self):
        self.start();self.prepare()
        self.lua.execute("""
            e2.pos=plan.target;assert(D.Arrived(e2,p2.token));assert(not D.active.arrived)
            e1.dir={x=0,y=0,z=1};assert(not D.Faced(e1,p1.token))
            turnToward(e1,e2);assert(D.Faced(e1,p1.token));assert(not D.active.arrived)
            turnToward(e2,e1);assert(D.Faced(e2,p2.token));assert(D.active.arrived)
        """)

    def test_wake_order_has_one_immediate_guard_then_five_to_fifteen_second_gaps(self):
        self.lua.execute("assert(D.active==nil)")
        self.lua.execute("""
            nebakovrising.Config.wakeStaggerMin=5;nebakovrising.Config.wakeStaggerMax=15
            C.GetSleepingNpcWuids=function() return {'a','b','c','d','e','f','g','h','i','j'} end
            C.wakeUpSlotsAssigned=false;C.AssignWakeUpSlots();times={}
            for _,at in pairs(C.npcWakeSlots) do times[#times+1]=at end
            table.sort(times);assert(#times==10 and times[1]==clock)
            for i=2,#times do assert(times[i]-times[i-1]>=5 and times[i]-times[i-1]<=15) end
        """)

    def test_failed_turn_cancels_without_waiting_for_generation_timeout(self):
        self.start();self.prepare()
        self.lua.execute("e2.pos=plan.target;assert(D.Arrived(e2,p2.token));clock=clock+9;C.ActivityHeartbeat(a.this.id,ta);C.ActivityHeartbeat(b.this.id,tb);assert(not D.CheckActive());assert(D.last.reason=='facing_timeout')")

    def test_smooth_turn_reaches_both_directions_and_only_then_allows_playback(self):
        self.start();self.prepare()
        self.lua.execute("e2.pos=plan.target;assert(D.Arrived(e2,p2.token));e1.dir={x=0,y=-1,z=0};e2.dir={x=0,y=-1,z=0}")
        self.lua.execute("""
            for i=1,30 do
                clock=clock+0.1;C.ActivityHeartbeat(a.this.id,ta);C.ActivityHeartbeat(b.this.id,tb)
                D.TurnStep(e1,p1.token);D.TurnStep(e2,p2.token)
                D.Faced(e1,p1.token);D.Faced(e2,p2.token)
            end
            assert(D.active.arrived and D.active.participants[1].facingError<=20
                and D.active.participants[2].facingError<=20)
        """)

    def test_smooth_turn_uses_body_transform_even_when_actor_setter_silently_does_nothing(self):
        self.start();self.prepare()
        self.lua.execute("""
            e2.pos=plan.target;assert(D.Arrived(e2,p2.token));e1.dir={x=0,y=-1,z=0}
            actorWrites=0;e1.actor.SetAngles=function(_,angles) actorWrites=actorWrites+1 end
            for i=1,20 do
                clock=clock+0.1;C.ActivityHeartbeat(a.this.id,ta);C.ActivityHeartbeat(b.this.id,tb)
                D.TurnStep(e1,p1.token)
            end
            assert(D.Faced(e1,p1.token));assert(p1.turnMethod=='entity.SetAngles' and actorWrites==0)
            e1.actor.SetAngles=nil;e1.SetAngles=nil;e1.dir={x=0,y=-1,z=0}
            assert(not D.TurnStep(e1,p1.token));assert(p1.turnError=='Body rotation API unavailable')
        """)

    def test_turn_and_facing_gate_use_documented_no_argument_forward_vector(self):
        self.start();self.prepare()
        self.lua.execute("""
            e2.pos=plan.target;assert(D.Arrived(e2,p2.token))
            local old=e1.GetDirectionVector
            e1.GetDirectionVector=function(self,axis)
                if axis~=nil then error('Indexed vector is not the forward binding') end
                return old(self)
            end
            for i=1,20 do
                clock=clock+0.1;C.ActivityHeartbeat(a.this.id,ta);C.ActivityHeartbeat(b.this.id,tb)
                D.TurnStep(e1,p1.token)
            end
            assert(D.Faced(e1,p1.token))
        """)

    def test_actor_fallback_reads_and_writes_actor_angles_as_a_pair(self):
        self.start();self.prepare()
        self.lua.execute("""
            e2.pos=plan.target;assert(D.Arrived(e2,p2.token))
            local get,set=e1.GetAngles,e1.SetAngles
            e1.actor.GetAngles=function() return get(e1) end
            e1.actor.SetAngles=function(_,angles) return set(e1,angles) end
            e1.GetAngles=nil;e1.SetAngles=nil
            for i=1,20 do
                clock=clock+0.1;C.ActivityHeartbeat(a.this.id,ta);C.ActivityHeartbeat(b.this.id,tb)
                D.TurnStep(e1,p1.token)
            end
            assert(D.Faced(e1,p1.token));assert(p1.turnMethod=='actor.GetAngles/SetAngles')
        """)

    def test_wake_slots_use_runtime_wuid_and_reset_every_night(self):
        self.lua.execute("""
            nebakovrising.Config.npcSleepStartHour=0;nebakovrising.Config.npcWakeHour=8
            nebakovrising.Config.wakeStaggerMin=5;nebakovrising.Config.wakeStaggerMax=15
            g1=makeEntity('nebakovrising_guard_one','wuid_one')
            g2=makeEntity('nebakovrising_guard_two','wuid_two')
            cook=makeEntity('nebakovrising_cook','wuid_cook')
            C.activityRuns.wuid_one={kind='sleep'};C.activityRuns.wuid_two={kind='sleep'}
            C.activityRuns.wuid_cook={kind='sleep'}
            System.GetEntitiesByClass=function(class) if class=='NPC' then return {g1,g2,cook} else return {store} end end
            nebakovrising.Roles.Resolve=function(name) return {bedPool=name=='nebakovrising_cook' and 'servant' or 'guard'} end
            worldHour=8;C.AssignWakeUpSlots()
            assert(C.npcWakeSlots[g1.id]==nil and C.npcWakeSlots.wuid_cook==nil)
            assert(C.npcWakeSlots.wuid_one and C.npcWakeSlots.wuid_two)
            later=C.npcWakeSlots.wuid_one>clock and 'wuid_one' or 'wuid_two'
            assert(C.IsNpcSleepTime(later))
            clock=clock+30;assert(not C.IsNpcSleepTime(later))
            worldHour=1;assert(C.IsNpcSleepTime(later));assert(not C.wakeUpSlotsAssigned)
            worldHour=8;C.AssignWakeUpSlots();assert(C.npcWakeSlots[later]>=clock)
            assert(math.max(C.npcWakeSlots.wuid_one,C.npcWakeSlots.wuid_two)>clock)
        """)

    def test_old_peer_session_sequence_and_conversation_cannot_control_new_work(self):
        self.start()
        self.lua.execute("assert(not D.Receive('peer',1,'audio_ready',B.session,D.active.id)); assert(not D.Receive('peer',2,'audio_ready','old',D.active.id)); assert(not D.Receive('other',2,'audio_ready',B.session,D.active.id)); assert(not D.Receive('peer',2,'audio_ready',B.session,'wrong')); assert(D.active.audioReady==nil)")

    def test_combat_and_activity_interruption_release_both_participants(self):
        self.start()
        self.lua.execute("a.combat=true; assert(not D.CheckActive()); assert(D.active==nil)")
        self.setUp(); self.start()
        self.lua.execute("C.FailNpcActivity(a,ta); assert(D.active==nil); assert(not D.HasRequest(b.this.id,tb))")

    def test_voluntary_social_exit_does_not_blacklist_patrol_point(self):
        self.start()
        self.lua.execute("C.patrolAssignments[a:GetName()]={selector='point'}; D.Cancel('timeout'); C.FailNpcActivity(a,ta); assert(C.patrolBlocked.point==nil)")

    def test_timeout_and_peer_disconnect_cancel(self):
        self.start()
        self.lua.execute("clock=clock+13; C.ActivityHeartbeat(a.this.id,ta);C.ActivityHeartbeat(b.this.id,tb); assert(not D.CheckActive()); assert(D.last.reason=='python_disconnected')")
        self.setUp(); self.start()
        self.lua.execute('D.active.deadline=clock')
        self.assertFalse(self.lua.eval('D.CheckActive()'))

    def test_same_floor_and_physical_arrival_checked(self):
        self.start(); self.prepare()
        self.lua.execute("e2.pos={x=e1.pos.x,y=e1.pos.y,z=e1.pos.z+3};assert(not D.Arrived(e2,p2.token)); assert(D.active==nil)")

    def test_actual_bt_stands_before_navigation_and_cancels_blocked_move(self):
        self.start()
        self.lua.execute('p1=D.active.participants[1];p2=D.active.participants[2]')
        g=self.lua.globals()
        anchor=ConversationDriver(self.lua,g.System.GetEntity(g.p1.entityId),g.p1.token)
        mover=ConversationDriver(self.lua,g.System.GetEntity(g.p2.entityId),g.p2.token,blocked=True)
        for _ in range(10):
            self.keep_alive();anchor.tick();mover.tick()
            if mover.events: break
        self.assertIn(('move','standing'),mover.events)
        self.assertFalse(self.lua.eval('D.active.arrived == true'))
        self.lua.execute("D.Cancel('test_path_abort')")
        result=None
        for _ in range(6):
            result=mover.tick()
            if result is not None: break
        self.assertTrue(result)

    def test_old_timer_and_save_load_clear_reservations_and_peer(self):
        self.start()
        self.lua.execute('old={generation=D.generation}; D.OnGameplayStarted(); count=#timers;D.Tick(old);assert(#timers==count);assert(D.active==nil);assert(D.peer==nil)')

    def test_actual_bt_meets_then_returns_to_scheduler_after_playback(self):
        self.start()
        self.lua.execute('p1=D.active.participants[1];p2=D.active.participants[2]')
        g=self.lua.globals()
        anchor=ConversationDriver(self.lua,g.System.GetEntity(g.p1.entityId),g.p1.token)
        mover=ConversationDriver(self.lua,g.System.GetEntity(g.p2.entityId),g.p2.token)
        # Rotation is updated at 100 ms; the meal driver's coarse 500 ms steps
        # per entity artificially stretch the two concurrent turn loops.
        for _ in range(120):
            self.lua.execute('clock=clock+0.1')
            self.keep_alive();next(anchor.generator);next(mover.generator)
            if self.lua.eval('D.active.arrived == true'):break
        self.assertTrue(self.lua.eval('D.active.arrived == true'))
        self.assertFalse(any(e[0]=='move' for e in anchor.events))
        self.lua.execute("assert(D.Receive('peer',D.peer.seq+1,'audio_ready',B.session,D.active.id));assert(D.Receive('peer',D.peer.seq+1,'playing',B.session,D.active.id));assert(D.Receive('peer',D.peer.seq+1,'finished',B.session,D.active.id))")
        for driver in (anchor,mover):
            result=None
            for _ in range(8):
                result=driver.tick()
                if result is not None:break
            self.assertTrue(result)
        self.lua.execute("assert(C.FinishNpcActivity(a.this.id,ta));assert(C.FinishNpcActivity(b.this.id,tb));assert(C.NextNpcActivity(a)=='patrol');assert(C.NextNpcActivity(b)=='patrol')")

    def test_failed_standing_cancels_pair_without_movement(self):
        self.start()
        self.lua.execute('p1=D.active.participants[1];p2=D.active.participants[2]')
        g=self.lua.globals();entity=g.System.GetEntity(g.p2.entityId)
        mover=ConversationDriver(self.lua,entity,g.p2.token)
        mover.blocked_standing=True
        result=None
        for _ in range(50):
            self.keep_alive();result=mover.tick()
            if result is not None:break
        self.assertFalse(result)
        self.assertFalse(mover.events)
        g.C.FailNpcActivity(entity,g.p2.token)
        self.assertTrue(self.lua.eval('D.active==nil'))

    def test_random_scheduler_and_manual_command_honor_cooldown(self):
        self.lua.execute('D.nextRandom=clock; D.Tick({generation=D.generation});assert(D.active~=nil)')
        self.lua.execute("D.Finish('done',true)")
        self.assertEqual(self.lua.eval('D.TryStart(true)'),(False,'global_cooldown'))

    def test_manual_only_service_test_does_not_start_random_conversation(self):
        self.lua.execute('nebakovrising.Config.conversations.randomEnabled=false; D.nextRandom=clock; D.Tick({generation=D.generation});assert(D.active==nil)')
        self.start()

    def test_speech_cues_alternate_entities_and_stop_only_facial_layer(self):
        self.start()
        self.lua.execute("""
            F=nebakovrising.VoiceFace;D.active.phase='playing';D.active.arrived=true;D.active.audioReady=true
            p1=D.active.participants[1];p2=D.active.participants[2]
            e1=System.GetEntity(p1.entityId);e2=System.GetEntity(p2.entityId)
            assert(D.Receive('peer',2,'line_start',B.session,D.active.id,1,1200))
            assert(F.current.entityId==e1.id and e1.faceStarts[1].layer==12)
            assert(not D.Receive('peer',3,'line_end',B.session,D.active.id,2,0))
            assert(F.current~=nil)
            assert(D.Receive('peer',4,'line_end',B.session,D.active.id,1,0))
            assert(F.current==nil and e1.faceStops[1].layer==12)
            assert(D.Receive('peer',5,'line_start',B.session,D.active.id,2,1200))
            assert(F.current.entityId==e2.id)
            D.Cancel('test');assert(F.current==nil and e2.faceStops[1].layer==12)
        """)

    def test_face_watchdog_cannot_stop_a_newer_line_and_api_failure_is_optional(self):
        self.lua.execute("""
            F=nebakovrising.VoiceFace
            assert(F.Start(a,'Marek','c',1,1000));old=F.generation
            assert(F.Start(b,'Hertl','c',2,1000))
            F.Expire({generation=old});assert(F.current.entityId==b.id)
            F.Expire({generation=F.generation});assert(F.current==nil)
            a.GetAnimationLength=function() return 0 end
            assert(not F.Start(a,'Marek','c',1,1000));assert(F.last.status=='clip_not_loaded')
        """)

    def test_restarted_python_cannot_adopt_old_reservation(self):
        self.start()
        self.lua.execute("clock=clock+13; C.ActivityHeartbeat(a.this.id,ta);C.ActivityHeartbeat(b.this.id,tb); assert(D.Receive('new_peer',1,'heartbeat_ready',B.session,''));assert(not D.CheckActive());assert(D.active==nil)")

    def test_nonthrowing_cached_loader_is_not_reported_as_executed(self):
        self.lua.execute("D.peer=nil; Script.LoadScript=function() return true end; Script.ReloadScript=function() return false end; assert(not D.PollControl()); assert(D.controlIO.executed==false);assert(D.peer==nil)")

    def test_dofile_re_reads_changed_command_and_acknowledges_heartbeat(self):
        self.lua.execute("""
            D.peer=nil; value=1
            dofile=function(path)
                if path ~= 'Data/Scripts/nebakov_voice/command.lua' then error('missing') end
                D.Receive('reader_peer',value,'heartbeat_ready',B.session,'')
            end
            assert(D.PollControl());assert(D.peer.ready);assert(D.ack.seq==1)
            assert(D.controlIO.method=='dofile'); value=2
            assert(D.PollControl());assert(D.ack.seq==2)
        """)

    def test_explicit_reload_fallback_bypasses_load_cache(self):
        self.lua.execute("""
            D.peer=nil; dofile=nil; Script.LoadScript=function() return true end
            Script.ReloadScript=function(path) D.Receive('reload_peer',3,'heartbeat_ready',B.session,'') end
            assert(D.PollControl());assert(D.controlIO.method=='reload');assert(D.ack.seq==3)
        """)


class ProtocolTests(unittest.TestCase):
    def test_control_tokens_cannot_inject_lua_code(self):
        with self.assertRaises(ValueError):
            command_source('peer',1,'audio_ready','session','x"); dofile("evil")')
        with self.assertRaises(ValueError):
            command_source('peer',1,'run_script','session','id')

    def test_outbox_waits_for_ack_and_retries_same_sequence(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tools') as folder:
            out=CommandOutbox(Path(folder)/'command.lua',lambda *a,**kw:None)
            p={'session':'s','director':{}}
            out.observe(p,0);out.tick(0,True)
            first=out.path.read_text()
            out.send('audio_ready','conversation')
            out.tick(1,True);self.assertEqual(first,out.path.read_text())
            out.tick(3,True);self.assertEqual(first,out.path.read_text())
            p['director']['control']={'peer':out.peer,'seq':1,'accepted':True}
            out.observe(p,3.1);out.tick(3.1,True)
            self.assertEqual(out.pending['kind'],'audio_ready')
            self.assertEqual(out.pending['seq'],2)
            out.observe({'session':'new','director':{}},4);out.tick(4,True)
            self.assertEqual(out.pending['seq'],3)

    def test_behavior_specific_prompt_does_not_reuse_patrol_for_combat(self):
        p={'director':{'id':'id','behavior':'patrol','context':{'hour':14}}}
        self.assertIn('paused their patrol',build_context(p))
        p['director']['behavior']='combat'
        with self.assertRaises(ValueError):build_context(p)


class EndToEndTests(unittest.TestCase):
    setUp = LuaDirectorTests.setUp
    packet = LuaDirectorTests.packet

    def scenario(self, audio_delay):
        with tempfile.TemporaryDirectory(dir=ROOT/'tools') as folder:
            folder=Path(folder)
            rows=[]
            for i in range(1,5):
                path=folder/f'{i}.wav'
                with wave.open(str(path),'wb') as wav:
                    wav.setparams((1,2,24000,0,'NONE','not compressed'));wav.writeframes(b'\0\0'*2400)
                rows.append({'index':i,'speaker':'Marek' if i%2 else 'Hertl','audio_file':path.name})
            manifest=folder/'conversation.json';manifest.write_text(json.dumps({'lines':rows}))
            events=[];emit=lambda event,**fields:events.append((event,fields))
            out=CommandOutbox(folder/'command.lua',emit)
            def read_control(path):
                if path != 'Data/Scripts/nebakov_voice/command.lua':raise FileNotFoundError(path)
                return out.path.read_text('ascii')
            self.lua.globals().read_control=read_control
            self.lua.execute('dofile=function(path) return assert(loadstring(read_control(path)))() end')
            audio=audio_tests.Audio();playback=SequentialPlayback(audio,emit)
            jobs=[]
            def submit(p):
                jobs.append(deepcopy(p));return 'job1'
            controller=PatrolController(Settings(stale_after=4),playback,submit,emit,out,lambda:True)
            self.lua.execute('D.peer=nil')
            selected=False;prepared=False;generated=False;start_step=None
            for step in range(140):
                self.lua.execute('clock=clock+0.25; C.ActivityHeartbeat(a.this.id,ta);C.ActivityHeartbeat(b.this.id,tb)')
                if not selected and self.lua.eval('D.peer ~= nil and D.peer.ready == true'):
                    self.lua.execute('assert(D.TryStart(true))');selected=True
                if selected and not prepared:
                    self.lua.execute('p1=D.active.participants[1];p2=D.active.participants[2];e1=System.GetEntity(p1.entityId);e2=System.GetEntity(p2.entityId);D.Prepare(e1,p1.token);plan=D.Prepare(e2,p2.token)')
                    prepared=True;start_step=step
                if selected and step-start_step == 12:
                    self.lua.execute('e2.pos=plan.target; assert(D.Arrived(e2,p2.token)); facePair()')
                self.lua.execute('D.Tick({generation=D.generation})')
                p=self.packet();previous_count=len(audio.played)
                controller.ingest(p,step*.25);controller.tick(step*.25)
                if jobs and not generated and step-start_step >= audio_delay:
                    controller.result('job1',manifest,None,step*.25);generated=True
                if len(audio.played)>previous_count:
                    self.assertTrue(p['director']['arrived'])
                    self.assertEqual(p['director']['phase'],'playing')
                audio.busy=False
                if any(e[0]=='conversation_finished' for e in events):break
            self.assertEqual(len(jobs),1)
            self.assertEqual([line.speaker for line,gains in audio.played],['Marek','Hertl','Marek','Hertl'])
            self.assertTrue(any(e[0]=='conversation_finished' for e in events),events)
            self.assertTrue(self.lua.eval("D.active==nil and D.last.phase=='finished'"))

    def test_generation_ready_before_arrival_waits_for_lua_authorization(self):
        self.scenario(audio_delay=2)

    def test_arrival_before_generation_waits_for_manifest_then_finishes(self):
        self.scenario(audio_delay=20)


if __name__=='__main__':
    unittest.main(verbosity=2)
