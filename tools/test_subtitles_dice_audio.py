"""Prototype integration contracts: real Lua/BT and protocol, mocked game APIs."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from lupa.lua51 import LuaRuntime
from nebakov_voice_director import command_source, CommandOutbox
from nebakov_voice_playback import Line, SequentialPlayback, PygameAudio
import test_patrol_conversations as patrol
import test_guard_shifts as shifts
import test_voice_runtime as voice
from meal_bt_driver import MealBtDriver

ROOT=Path(__file__).resolve().parents[1]


class SubtitleTests(unittest.TestCase):
    def setUp(self):
        fixture=patrol.LuaDirectorTests();fixture.setUp();self.lua=fixture.lua
        for name in ['nebakov_subtitles.lua','nebakov_subtitle_entity.lua']:
            self.lua.execute((ROOT/'src/Scripts/mods'/name).read_text('utf-8'))
        self.lua.execute("""
            S=nebakovrising.Subtitles;draws={};activations={}
            System.DrawLabel=function(pos,size,text) draws[#draws+1]={pos=pos,size=size,text=text} end
            System.SpawnEntity=function(params)
                assert(params.class=='NebakovSubtitle' and params.properties.bSaved_by_game==0)
                renderer={id='renderer'}
                function renderer:GetName() return 'nebakov_subtitle_renderer' end
                function renderer:Activate(value) activations[#activations+1]=value end
                entities.renderer=renderer;return renderer
            end
        """)

    def test_line_text_is_data_and_unicode_round_trips_through_lua51(self):
        text='Hey! " ; pwned=true; --\\\nGünaydın, Jiří!'
        source=command_source('peer',1,'line_start','session','scene',1,6000,text)
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.execute('nebakovrising={Conversations={Receive=function(...) received={...} end}}')
        lua.execute(source)
        self.assertEqual(lua.globals().received[8],' '.join(text.split()))
        self.assertIsNone(lua.globals().pwned)
        for bad in ['x\0y','x'*801,'漢'*801]:
            with self.assertRaises(ValueError):command_source('peer',1,'line_start','s','c',1,5000,bad)

    def test_existing_line_start_carries_text_without_extra_command_or_ack(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tools') as folder:
            out=CommandOutbox(Path(folder)/'command.lua',lambda *a,**k:None)
            out.session='s';out.send('line_start','scene',1,5000,text='Hello, friend!')
            out.tick(0,True)
            self.assertEqual(out.pending['kind'],'line_start')
            self.assertFalse(out.queue)
            text=out.path.read_text('utf-8')
            lua=LuaRuntime();lua.execute('nebakovrising={Conversations={Receive=function(...) received={...} end}}')
            lua.execute(text);self.assertEqual(lua.globals().received[8],'Hello, friend!')

    def test_render_entity_uses_frame_callback_and_current_npc_position(self):
        self.lua.execute("""
            assert(S.Start(a,'scene',1,'Hello there!',6000))
            NebakovSubtitle.OnUpdate(renderer,0.016);assert(#draws==1)
            assert(draws[1].pos.x==a.pos.x and draws[1].text=='Hello there!')
            a.pos.x=5;NebakovSubtitle.OnUpdate(renderer,0.016)
            assert(draws[2].pos.x==5 and S.renderSeen)
            S.Stop('scene',1);assert(S.active==nil and activations[#activations]==0)
        """)

    def test_hide_at_distance_resume_nearby_and_expire(self):
        self.lua.execute("""
            assert(S.Start(a,'scene',1,'Hey!',6000));a.pos.x=30;S.Render();assert(#draws==0)
            a.pos.x=3;S.Render();assert(#draws==1)
            clock=clock+6;S.Render();assert(S.active==nil and #draws==1)
        """)

    def test_stale_end_cannot_clear_another_scene_or_line(self):
        self.lua.execute("""
            assert(S.Start(a,'new',2,'Hey!',6000));S.Stop('old',2);S.Stop('new',1)
            assert(S.active and S.active.line==2);S.Stop('new',2);assert(S.active==nil)
        """)

    def test_reused_entity_ids_cannot_deactivate_or_label_other_npcs(self):
        self.lua.execute("""
            S.renderer=a.id;function a:Activate() error('Must not deactivate NPC') end
            S.Stop();assert(S.Start(a,'scene',1,'Hey!',6000))
            entities[a.id]=b;S.Render();assert(S.active==nil)
        """)

    def test_long_text_is_split_into_pages_and_missing_draw_api_does_not_break_speech(self):
        self.lua.execute("""
            assert(#S.Pages(string.rep('a word ',70))>1)
            System.DrawLabel=nil;assert(not S.Start(a,'scene',1,'Hey!',6000))
            assert(S.active==nil)
        """)

    def test_line_start_end_and_cancel_use_existing_conversation_lifecycle(self):
        self.lua.execute("""
            assert(D.TryStart(true));p1=D.active.participants[1];p2=D.active.participants[2]
            e1=System.GetEntity(p1.entityId);e2=System.GetEntity(p2.entityId)
            D.Prepare(e1,p1.token);local plan=D.Prepare(e2,p2.token);e2.pos=plan.target
            D.Arrived(e2,p2.token);facePair()
            assert(D.Receive('peer',2,'audio_ready',B.session,D.active.id))
            assert(D.Receive('peer',3,'playing',B.session,D.active.id))
            assert(D.Receive('peer',4,'line_start',B.session,D.active.id,1,4000,'Hey, friend!'))
            assert(S.active and S.active.id==e1.id);S.Render();assert(draws[1].text=='Hey, friend!')
            assert(D.Receive('peer',5,'line_end',B.session,D.active.id,1,0));assert(S.active==nil)
            assert(D.Receive('peer',6,'line_start',B.session,D.active.id,2,4000,'Good evening.'))
            D.Cancel('test');assert(S.active==nil)
        """)


class DiceDriver(MealBtDriver):
    def __init__(self,lua,entity,token,fail_native=False):
        super().__init__(lua,ROOT/'src/AI/nebakovrising_meal.xml',entity,token)
        self.functions.update({t.get('name'):t for t in ET.parse(ROOT/'src/AI/nebakovrising_dice.xml').getroot()})
        self.fail_native=fail_native;self.stance='standing'
        self.generator=self.function('nebakovrising_post_meal_dice',token)

    def node(self,node,data):
        if node.tag=='ReserveBehavior':return (yield from self.sequence(node.find('Exec'),data))
        if node.tag=='CallBehavior':
            self.events.append(('native',data.behavior))
            if self.fail_native:return False
            self.stance='sitting'
            self.lua.globals().diceLinks[self.entity.this.id]=self.lua.table(dice_table=self.lua.table_from(['table:wuid']))
            try:
                while True:yield
            finally:self.lua.globals().diceLinks[self.entity.this.id]=None
        return (yield from super().node(node,data))


class DiceTests(unittest.TestCase):
    def setUp(self):
        fixture=shifts.ShiftTests();fixture.setUp();self.lua=fixture.lua
        self.lua.execute((ROOT/'src/Scripts/mods/nebakov_dice.lua').read_text('utf-8'))
        self.lua.execute("""
            D=nebakovrising.Dice;worldHour=21;seats(10)
            local oldGuard=guard
            guard=function(i,shift) local e=oldGuard(i,shift);entities[e.id]=e;return e end
            diceTable=makeEntity('dice_table','table:wuid');entities[diceTable.id]=diceTable
            diceTable.Properties={guidSmartObjectType='9a3317b0-9c92-466e-bab6-571f23356bca'}
            diceLinks={['table:wuid']={}}
            for _,tag in ipairs({'seat1_SO','seat2_SO','cupSlot1','cupSlot2','hiddenSlot1','hiddenSlot2'}) do
                diceLinks['table:wuid'][tag]={tag}
            end
            local oldFind=XGenAIModule.FindLinks
            XGenAIModule.FindLinks=function(wuid,tag)
                if diceLinks[wuid] then return diceLinks[wuid][tag] or {} end
                return oldFind(wuid,tag)
            end
            local oldGet=System.GetEntitiesByClass
            System.GetEntitiesByClass=function(class) if class=='SmartObjectHolder' then return {diceTable} end return oldGet(class) end
            function finishDiner(i,group,kind)
                local e=guard(i,group or 'day');records[e:GetName()].mealKind=kind or 'evening'
                local token=collect(e);C.OnMealEaten(e,token);C.FinishMeal(e,token)
                return e,token
            end
        """)

    def test_first_two_completed_off_duty_diners_are_selected_in_order(self):
        self.lua.execute("""
            a,ta=finishDiner(1);assert(D.active and #D.active.participants==1)
            b,tb=finishDiner(2);c,tc=finishDiner(3)
            assert(D.active.participants[1].name==a:GetName() and D.active.participants[2].name==b:GetName())
            assert(not D.HasRequest(c,tc) and D.used)
            assert(records[a:GetName()].mealBenchSelector==nil and records[b:GetName()].mealBenchSelector==nil)
        """)

    def test_breakfast_and_on_duty_night_guards_are_never_selected(self):
        self.lua.execute("""
            worldHour=8;a,ta=finishDiner(1,'day','breakfast');assert(D.active==nil)
            worldHour=19;b,tb=finishDiner(2,'night','breakfast');assert(D.active==nil)
        """)

    def test_night_pair_is_selected_after_eight_am_end_of_shift_meal(self):
        self.lua.execute("""
            worldHour=8;a,ta=finishDiner(1,'night');b,tb=finishDiner(2,'night')
            assert(D.active and #D.active.participants==2)
            worldHour=11;assert(not D.Check());assert(D.active==nil)
            assert(C.activityRuns[tostring(a.this.id)].diceScene==nil)
        """)

    def test_unfinished_meal_missing_table_and_broken_links_do_not_hold_guard(self):
        self.lua.execute("""
            a=guard(1,'day');records[a:GetName()].mealKind='evening';ta=collect(a)
            C.FinishMeal(a,ta);assert(D.active==nil)
            diceLinks['table:wuid'].cupSlot2=nil;b,tb=finishDiner(2);assert(D.active==nil)
        """)

    def test_second_guard_waits_until_native_first_seat_has_table_link(self):
        self.lua.execute("""
            a,ta=finishDiner(1);b,tb=finishDiner(2)
            assert(D.Plan(a,ta).behavior=='use_challenger' and D.Plan(b,tb).waiting)
            diceLinks[a.this.id]={dice_table={'another:table'}}
            assert(D.Plan(b,tb).waiting)
            diceLinks[a.this.id]={dice_table={'table:wuid'}}
            assert(D.Plan(b,tb).behavior=='use_opponent')
        """)

    def test_queue_timeout_does_not_consume_the_only_test_pair(self):
        self.lua.execute("""
            a,ta=finishDiner(1);clock=clock+91;assert(not D.Check())
            assert(D.active==nil and not D.used and D.last.reason=='partner_timeout')
        """)

    def test_combat_despawn_and_activity_token_changes_cancel_both_reservations(self):
        for change in ["a.soul={HasScriptContext=function() return true end}",
                       'entities[a.id]=nil',
                       'C.activityRuns[tostring(a.this.id)].token=ta+100']:
            self.setUp();self.lua.execute('a,ta=finishDiner(1);b,tb=finishDiner(2)')
            self.lua.execute(change)
            self.lua.execute('assert(not D.Check());assert(D.active==nil);assert(C.activityRuns[tostring(b.this.id)].diceScene==nil)')

    def test_reset_rearms_and_old_activity_cannot_end_new_scene(self):
        self.lua.execute("""
            a,ta=finishDiner(1);b,tb=finishDiner(2);D.Reset()
            c,tc=finishDiner(3);d,td=finishDiner(4)
            D.Leave(a,ta);assert(D.active and D.active.participants[1].name==c:GetName())
        """)

    def test_native_bt_unwinds_seats_and_stands_both_guards_at_time_limit(self):
        self.lua.execute('a,ta=finishDiner(1);b,tb=finishDiner(2);nebakovrising.Config.dice.playSeconds=5')
        g=self.lua.globals();drivers=[DiceDriver(self.lua,g.a,g.ta),DiceDriver(self.lua,g.b,g.tb)]
        finished=[False,False]
        for _ in range(60):
            self.lua.execute('clock=clock+0.5;C.ActivityHeartbeat(a.this.id,ta);C.ActivityHeartbeat(b.this.id,tb)')
            for i,d in enumerate(drivers):
                if finished[i]:continue
                try:next(d.generator)
                except StopIteration as result:self.assertTrue(result.value);finished[i]=True
            if all(finished):break
        self.assertTrue(all(finished))
        self.assertTrue(all(d.stance=='standing' for d in drivers))
        self.assertIn(('native','use_challenger'),drivers[0].events)
        self.assertIn(('native','use_opponent'),drivers[1].events)
        self.lua.execute('assert(D.active==nil and next(diceLinks[a.this.id] or {})==nil and next(diceLinks[b.this.id] or {})==nil)')

    def test_reservation_failure_eventually_times_out_and_releases_partner(self):
        self.lua.execute('a,ta=finishDiner(1);b,tb=finishDiner(2);D.active.deadline=clock+3')
        g=self.lua.globals();driver=DiceDriver(self.lua,g.a,g.ta,fail_native=True)
        for _ in range(30):
            result=driver.tick()
            if result is not None:self.assertTrue(result);break
        else:self.fail('Failed native call did not time out')
        self.lua.execute('assert(D.active==nil and C.activityRuns[tostring(b.this.id)].diceScene==nil)')

    def test_meal_bt_offers_only_after_standing_and_uses_a_distinct_dice_tree(self):
        tree=ET.parse(ROOT/'src/AI/nebakovrising_meal.xml').getroot()
        meal=next(t for t in tree if t.get('name')=='nebakovrising_meal_at_table')
        nodes=list(meal.find('Root').iter())
        finish=next(i for i,n in enumerate(nodes) if 'FinishMeal' in n.get('code',''))
        dice=next(i for i,n in enumerate(nodes) if n.tag=='Function_nebakovrising_post_meal_dice')
        self.assertLess(finish,dice)
        self.assertEqual(nodes[finish-1].tag,'Function_nebakovrising_stand')


class SpatialDiagnosticTests(unittest.TestCase):
    def test_current_line_recomputes_gain_for_moving_player_and_traces_twice_per_second(self):
        events=[];audio=voice.Audio();playback=SequentialPlayback(audio,lambda e,**k:events.append((e,k)))
        playback.lines=[Line(1,'Marek','Hello',Path('fixture.wav'),5,24000)]
        packet=voice.packet();packet['player']['position']={'x':0,'y':0,'z':0}
        packet['npcs'][0]['position']={'x':2,'y':0,'z':0}
        with patch('nebakov_voice_playback.time.monotonic',return_value=0):playback.tick(packet)
        self.assertTrue(audio.busy)
        packet['player']['position']['x']=50
        with patch('nebakov_voice_playback.time.monotonic',return_value=.1):playback.tick(packet)
        self.assertEqual(audio.gains,(0,0))
        with patch('nebakov_voice_playback.time.monotonic',return_value=.6):playback.tick(packet)
        traces=[fields for event,fields in events if event=='spatial_audio']
        self.assertEqual(len(traces),2);self.assertEqual(traces[-1]['left'],0)
        self.assertEqual(traces[-1]['distance'],48)
        self.assertEqual(len(audio.played),1)

    def test_channel_volume_is_reapplied_after_play_resets_it(self):
        calls=[]
        channel=types.SimpleNamespace(set_volume=lambda *v:calls.append(('volume',v)),play=lambda s:calls.append(('play',s)))
        pg=types.ModuleType('pygame');pg.sndarray=types.ModuleType('pygame.sndarray')
        pg.sndarray.array=lambda s:types.SimpleNamespace(ndim=2);pg.mixer=types.SimpleNamespace(Sound=lambda path:'sound')
        audio=PygameAudio.__new__(PygameAudio);audio.pg=pg;audio.channel=channel
        with patch.dict(sys.modules,{'pygame':pg,'pygame.sndarray':pg.sndarray}):
            audio.play(types.SimpleNamespace(path=Path('fixture.wav')),(.2,.4))
        self.assertEqual(calls[-2:],[('play','sound'),('volume',(.2,.4))])


if __name__=='__main__':unittest.main()
