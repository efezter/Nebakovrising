"""24-hour eligibility and real BT holds without Move/Turn/Stand for nearby actors."""
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import json

import test_patrol_conversations as patrol
from nebakov_voice_defaults import DEFAULT_SETTINGS, ensure_defaults
from nebakov_voice_config import encode_settings, load_config
from nebakov_voice_receiver import decode_packet, MARKER
from nebakov_voice_prompts import PromptProfiles


class StationaryTests(unittest.TestCase):
    def setUp(self):
        patrol.LuaDirectorTests.setUp(self)
        self.settings=dict(DEFAULT_SETTINGS)
        csv,profile=encode_settings(self.settings)
        self.lua.globals().nebakovrising.ConversationConfig.Apply(csv,profile)
        self.lua.execute('b.pos={x=4.5,y=0,z=0}')

    def tick(self,drivers):
        self.lua.execute('clock=clock+0.1;C.ActivityHeartbeat(a.this.id,ta);C.ActivityHeartbeat(b.this.id,tb);D.Receive("peer",D.peer.seq+1,"heartbeat_ready",B.session,"")')
        for driver in drivers:
            try:next(driver.generator)
            except StopIteration: self.fail('Held activity ended before conversation cleanup')

    def receiver(self,entity,token,stance):
        driver=patrol.ConversationDriver(self.lua,entity,token)
        driver.stance=stance
        driver.generator=driver.function('nebakovrising_receiver_conversation',token)
        return driver

    def test_both_seated_patrol_guards_hold_through_generation_and_speak_without_moving(self):
        self.lua.execute("D.SetPatrolPose(a,ta,'sit');D.SetPatrolPose(b,tb,'sit');assert(D.TryStart(true));assert(D.active.inPlace);assert(D.ReceiverRequested(a.this.id,ta) and D.ReceiverRequested(b.this.id,tb));assert(not D.HasRequest(a.this.id,ta) and not D.HasRequest(b.this.id,tb))")
        g=self.lua.globals()
        drivers=[self.receiver(g.a,g.ta,'sitting'),self.receiver(g.b,g.tb,'sitting')]
        for _ in range(100):self.tick(drivers)
        self.lua.execute("assert(D.active.phase=='preparing_audio' and not D.active.arrived);assert(D.Receive('peer',D.peer.seq+1,'audio_ready',B.session,D.active.id));assert(D.active.arrived and D.active.phase=='waiting_audio');assert(D.Receive('peer',D.peer.seq+1,'playing',B.session,D.active.id))")
        for line in range(1,5):
            self.lua.globals().line=line
            self.lua.execute("assert(D.Receive('peer',D.peer.seq+1,'line_start',B.session,D.active.id,line,1000))")
            self.tick(drivers)
            self.lua.execute("assert(D.Receive('peer',D.peer.seq+1,'line_end',B.session,D.active.id,line,0))")
        for driver in drivers:
            self.assertEqual(driver.stance,'sitting')
            self.assertFalse(any(e[0] in {'move','turn','turn_started'} for e in driver.events))
        self.lua.execute("assert(D.Receive('peer',D.peer.seq+1,'finished',B.session,D.active.id));assert(C.activityRuns[tostring(a.this.id)].conversationId==nil);assert(C.activityRuns[tostring(b.this.id)].conversationId==nil)")

    def test_nearby_generation_failure_releases_both_patrol_tokens(self):
        self.lua.execute("assert(D.TryStart(true));assert(D.active.inPlace);D.Cancel('generation_failed');assert(not D.ReceiverRequested(a.this.id,ta));assert(C.OwnsNpcActivity(a.this.id,ta) and C.OwnsNpcActivity(b.this.id,tb));assert(D.IsEligible(a) and D.IsEligible(b))")

    def test_sleeping_walking_unknown_phase_and_native_motion_are_ineligible(self):
        for change in ["C.activityRuns[tostring(a.this.id)].phase='moving'",
                       "C.activityRuns[tostring(a.this.id)].socialStationary=false",
                       "C.activityRuns[tostring(a.this.id)].kind='sleep';C.activityRuns[tostring(a.this.id)].phase='sleeping'",
                       "a.GetVelocity=function() return {x=.5,y=0,z=0} end",
                       "a.GetVelocity=function() error('API failure') end"]:
            self.setUp();self.lua.execute(change)
            self.assertFalse(self.lua.eval('D.IsEligible(a)'))
            self.assertEqual(self.lua.eval('D.TryStart(true)'),(False,'two_eligible_patrol_npcs_required'))

    def test_started_motion_during_generation_cancels_without_forcing_a_meeting(self):
        self.lua.execute("assert(D.TryStart(true));a.GetVelocity=function() return {x=1,y=0,z=0} end;assert(not D.CheckActive());assert(D.active==nil);assert(C.activityRuns[tostring(b.this.id)].conversationId==nil)")

    def test_despawn_releases_both_holds_even_when_entity_cannot_be_resolved(self):
        self.lua.execute("assert(D.TryStart(true));entities[a.id]=nil;entities[a:GetName()]=nil;assert(not D.CheckActive());assert(D.active==nil);assert(C.activityRuns[tostring(a.this.id)].conversationId==nil);assert(C.activityRuns[tostring(b.this.id)].conversationId==nil)")

    def test_far_stationary_guards_keep_existing_approach_flow(self):
        self.lua.execute("b.pos.x=9;assert(D.TryStart(true));assert(not D.active.inPlace);assert(not D.ReceiverRequested(a.this.id,ta));assert(D.Receive('peer',D.peer.seq+1,'audio_ready',B.session,D.active.id));assert(D.HasRequest(a.this.id,ta) and D.HasRequest(b.this.id,tb))")

    def test_in_place_works_when_prepare_before_meeting_setting_is_false(self):
        self.lua.execute("nebakovrising.Config.conversations.prepareBeforeMeeting=false;assert(D.TryStart(true));assert(D.active.phase=='preparing_audio');D.Prepare(a,ta);D.Prepare(b,tb);assert(D.Receive('peer',D.peer.seq+1,'audio_ready',B.session,D.active.id));assert(D.active.arrived)")

    def test_evening_meal_holds_remaining_eating_time_and_uses_meal_profile(self):
        self.lua.execute("""
            worldHour=21
            C.FinishNpcActivity(a.this.id,ta);C.FinishNpcActivity(b.this.id,tb)
            ta=begin(a,'meal_table');tb=begin(b,'meal_walk')
            C.SetMealProgress(a,'eating',ta);C.SetMealProgress(b,'eating',tb)
            C.SetActivityPhase(a,ta,'eating',12);C.SetActivityPhase(b,tb,'eating',8)
            D.SetPatrolPose(a,ta,'sit');D.SetPatrolPose(b,tb,'sit')
            assert(D.TryStart(true));assert(D.active.behavior=='meal' and D.active.profileId=='meal-daily-talk')
            assert(C.activityRuns[tostring(a.this.id)].deadline==nil)
        """)
        g=self.lua.globals();drivers=[self.receiver(g.a,g.ta,'sitting'),self.receiver(g.b,g.tb,'sitting')]
        for _ in range(150):self.tick(drivers)
        self.lua.execute("assert(not C.ActivityPhaseExpired(a.this.id,ta));D.Cancel('test');assert(math.abs(C.activityRuns[tostring(a.this.id)].deadline-clock-12)<0.001);assert(math.abs(C.activityRuns[tostring(b.this.id)].deadline-clock-8)<0.001)")
        for driver in drivers:self.assertEqual(driver.stance,'sitting')
        packet=patrol.LuaDirectorTests.packet(self)
        self.assertEqual(decode_packet(MARKER+json.dumps(packet).encode())['director']['behavior'],'meal')

    def test_far_diners_are_never_forced_out_of_their_seats(self):
        self.lua.execute("""
            worldHour=21;b.pos.x=9
            for _,e in ipairs({a,b}) do
                local r=C.activityRuns[tostring(e.this.id)]
                r.kind='meal_table';C.SetMealProgress(e,'eating',r.token)
                C.SetActivityPhase(e,r.token,'eating',12);D.SetPatrolPose(e,r.token,'sit')
            end
            local ok,reason=D.TryStart(true);assert(not ok and reason=='no_compatible_stationary_pair')
        """)

    def test_actual_meal_tree_keeps_both_seats_and_resumes_eating_timer_after_speech(self):
        from meal_bt_driver import MealBtDriver
        self.lua.execute("""
            worldHour=21;C.FinishNpcActivity(a.this.id,ta);C.FinishNpcActivity(b.this.id,tb)
            ta=begin(a,'meal_table');tb=begin(b,'meal_table');seats(2)
            makeEntity(C.mealFireplaceSelector,'fireplace')
            C.EnsureNpcHasMealBowl=function() return 'bowl' end
            C.SetMealProgress(a,'meal_ready',ta);C.SetMealProgress(b,'meal_ready',tb)
            C.MealDuration=function() return 4 end
        """)
        g=self.lua.globals()
        drivers=[MealBtDriver(self.lua,patrol.ROOT/'src/AI/nebakovrising_meal.xml',e,t) for e,t in [(g.a,g.ta),(g.b,g.tb)]]
        for _ in range(50):
            self.tick(drivers)
            if self.lua.eval('D.IsEligible(a) and D.IsEligible(b)'):break
        self.lua.execute('assert(D.TryStart(true));savedA=records[a:GetName()].mealBenchSelector;savedB=records[b:GetName()].mealBenchSelector')
        for _ in range(100):self.tick(drivers)
        self.lua.execute("assert(not C.HasEatenMeal(a) and not C.HasEatenMeal(b));assert(records[a:GetName()].mealBenchSelector==savedA and records[b:GetName()].mealBenchSelector==savedB);assert(D.Receive('peer',D.peer.seq+1,'audio_ready',B.session,D.active.id));assert(D.active.arrived);assert(D.Receive('peer',D.peer.seq+1,'playing',B.session,D.active.id));assert(D.Receive('peer',D.peer.seq+1,'finished',B.session,D.active.id))")
        self.assertTrue(all(d.stance=='sitting' for d in drivers))
        for _ in range(100):
            self.tick(drivers)
            if self.lua.eval('C.HasEatenMeal(a) and C.HasEatenMeal(b)'):break
        self.assertTrue(self.lua.eval('C.HasEatenMeal(a) and C.HasEatenMeal(b)'))

    def test_evening_idle_is_eligible_after_twenty_but_sleep_is_not(self):
        self.lua.execute("""
            worldHour=22
            for _,e in ipairs({a,b}) do
                local r=C.activityRuns[tostring(e.this.id)]
                records[e:GetName()].eveningMealDone=true
                r.kind='evening_idle';C.SetActivityPhase(e,r.token,'evening_idle');D.SetPatrolPose(e,r.token,'guard')
            end
            assert(D.TryStart(true));assert(D.active.behavior=='idle')
            worldHour=0;assert(not D.CheckActive());assert(D.active==nil)
        """)

    def test_old_hour_settings_are_ignored_and_new_profiles_render_actual_activities(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            root=ensure_defaults(temp)
            path=root/'conversations.json';legacy=json.loads(path.read_text())
            legacy.update(patrolStartHour=8,patrolEndHour=20);legacy.pop('nearbyDistance')
            path.write_text(json.dumps(legacy))
            settings=load_config(path)
            self.assertEqual(settings['nearbyDistance'],2)
            self.assertNotIn('patrolStartHour',settings)
            for behavior in ['meal','idle']:
                prepared=PromptProfiles(root/'prompts').prepare({'director':{'behavior':behavior,
                    'profile_id':behavior+'-daily-talk','context':{
                    'guard_a_name':'Jan','guard_b_name':'Petr','guard_a_activity':'meal','guard_b_activity':'idle','hour':21}}})
                self.assertIn('Jan',prepared['text']);self.assertIn('meal and idle',prepared['text'])


if __name__=='__main__':unittest.main()
