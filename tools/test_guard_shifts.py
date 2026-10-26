"""Actual Lua shift allocator/routines; game entities and animation are mocks."""
from pathlib import Path
import math
import unittest
from lupa.lua51 import LuaRuntime
import test_meal_flow as meal
from meal_bt_driver import MealBtDriver
import test_patrol_conversations as patrol

ROOT=Path(__file__).resolve().parents[1]


class ShiftTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(meal.MOCKS)
        for name in ['CastleUtils.lua','nebakov_routine_config.lua','nebakov_shifts.lua']:
            self.lua.execute((ROOT/'src/Scripts/mods'/name).read_text('utf-8'))
        self.lua.globals().config_path=str(ROOT/'Config/routines.lua')
        self.lua.execute("""
            C=nebakovrising.CastleUtils;S=nebakovrising.Shifts;R=nebakovrising.Routines
            settings=dofile(config_path);assert(R.Apply(settings));g={};worldHour=12
            Script={SetTimerForFunction=function() end}
            nebakovrising.Utils={Log=function() end}
            nebakovrising.Roles.Resolve=function(name)
                local record=records[name]
                if record and record.role=='servant' then return {id='servant',bedPool='servant'} end
                return {id='guard_melee',bedPool='guard',eveningMeal=true,
                    patrol={fixed={'guardPoint'},roaming={},waitMin=10,waitMax=180}}
            end
            System.GetEntitiesByClass=function(class)
                if class=='BasicEntity' then return {store} end
                return g
            end
            function guard(i,shift)
                local entity=diner('nebakovrising_MeleeGuard_'..i)
                entity.dead=false;entity.actor={IsDead=function() return entity.dead end}
                local r=records[entity:GetName()];r.mealKind=nil;r.guardShift=shift
                g[i]=entity;C.bedAssignmentsByWuid[entity.this.id]={wuid='bed:'..i}
                return entity
            end
            function countNight()
                local n=0;for _,group in pairs(S.assignments) do if group=='night' then n=n+1 end end
                return n
            end
            function pair()
                guard(1,'day');guard(2,'night');S.Reconcile()
                day=g[1];night=g[2]
            end
        """)

    def test_distribution_for_all_counts_and_special_cases(self):
        for total in range(31):
            self.setUp()
            self.lua.execute(f'for i=1,{total} do guard(i) end;S.Reconcile()')
            expected=0 if total<2 else 1 if total<4 else math.ceil(total*.3)
            self.assertEqual(self.lua.eval('countNight()'),expected,total)

    def test_adding_guard_assigns_new_guard_first_and_preserves_existing_shifts(self):
        self.lua.execute("""
            guard(1,'day');guard(2,'day');guard(3,'night');S.Reconcile()
            extra=makeEntity('nebakovrising_MeleeGuard_4','npc:extra')
            assert(C.SaveManagedNpc(extra:GetName()))
            assert(S.Get(extra)=='night' and S.Get(g[1])=='day' and S.Get(g[2])=='day')
            for i=1,10 do S.Reconcile() end
            assert(S.Get(extra)=='night' and S.Get(g[3])=='night')
        """)

    def test_death_of_only_night_guard_promotes_one_day_guard(self):
        self.lua.execute("""
            guard(1,'day');guard(2,'day');guard(3,'night');S.Reconcile()
            g[3].dead=true;assert(C.RemoveManagedNpcRecord(g[3]:GetName()))
            assert(countNight()==1 and records[g[3]:GetName()]==nil)
            assert(S.Get(g[1])~=S.Get(g[2]))
        """)

    def test_loaded_dead_guard_is_excluded_even_before_death_monitor_cleanup(self):
        self.lua.execute("""
            pair();g[2].dead=true;S.Reconcile()
            assert(countNight()==0 and S.Get(g[1])=='day')
        """)

    def test_unload_and_non_guard_records_do_not_change_distribution(self):
        self.lua.execute("""
            pair();entities[night:GetName()]=nil
            servant=diner('servant');records.servant.role='servant'
            S.Reconcile();assert(countNight()==1 and S.Get(day)=='day')
            assert(S.assignments.servant==nil and records.servant.guardShift==nil)
        """)

    def test_save_load_keeps_assignments_from_persistent_records(self):
        self.lua.execute("""
            for i=1,9 do guard(i) end;S.Reconcile();before={}
            local restored={}
            for name,record in pairs(records) do
                before[name]=record.guardShift;restored[name]={}
                for key,value in pairs(record) do restored[name][key]=value end
            end
            records=restored;store.health.nebakovNpcRecords=restored
            C.ResetBedAssignments();S.assignments={};S.Reconcile()
            for name,group in pairs(before) do assert(records[name].guardShift==group and S.Get(name)==group) end
        """)

    def test_bulk_restore_defers_rebalance_until_all_legacy_npcs_are_registered(self):
        self.lua.execute("""
            C._restoreInProgress=true
            for i=1,6 do guard(i);S.Reconcile();assert(countNight()==0) end
            C._restoreInProgress=false;S.Reconcile();assert(countNight()==2)
        """)

    def test_day_and_night_sleep_boundaries_and_midnight_crossing(self):
        self.lua.execute('pair()')
        for hour,day_sleep,night_sleep in [(0,True,False),(7.99,True,False),(8,False,False),
            (10.99,False,False),(11,False,True),(18.99,False,True),(19,False,False),
            (20,False,False),(23.99,False,False)]:
            self.lua.globals().worldHour=hour
            self.assertEqual(self.lua.eval('C.IsNpcSleepTime(day.this.id)')[0],day_sleep,hour)
            self.assertEqual(self.lua.eval('C.IsNpcSleepTime(night.this.id)')[0],night_sleep,hour)

    def test_sleep_and_patrol_dispatch_are_per_guard_at_three_am(self):
        self.lua.execute("""
            pair();worldHour=3;makeEntity('guardPoint','point:1')
            assert(C.NextNpcActivity(day)=='sleep')
            assert(C.NextNpcActivity(night)=='patrol')
            assert(C.PatrolShouldStop(day) and not C.PatrolShouldStop(night))
            assert(C.AssignPatrolPoint(day.this.id)==nil)
            assert(C.AssignPatrolPoint(night.this.id)~=nil)
        """)

    def test_shift_specific_meal_windows_reset_without_false_meals_at_midnight(self):
        self.lua.execute("""
            pair();nebakovrising.Config.eveningMealStaggerMin=1
            nebakovrising.Config.eveningMealStaggerMax=1
            worldHour=0;assert(not C.ShouldStartEveningMeal(night))
            worldHour=8;assert(not C.ShouldStartEveningMeal(night));clock=clock+2
            assert(C.ShouldStartEveningMeal(night));assert(C.IsEveningMeal(night))
            assert(not C.ShouldStartEveningMeal(day))
            records[night:GetName()].eveningMealDone=true
            C.SetMealProgress(night,nil);assert(C.IsPostMealIdle(night))
            worldHour=11;assert(not C.IsPostMealIdle(night))
            worldHour=19;assert(not C.ShouldStartEveningMeal(night))
            assert(records[night:GetName()].eveningMealDone==nil)
            worldHour=20;assert(not C.ShouldStartEveningMeal(day));clock=clock+2
            assert(C.ShouldStartEveningMeal(day))
        """)

    def test_night_meal_bt_idles_then_releases_for_sleep_at_eleven(self):
        self.lua.execute("""
            pair();worldHour=8;seats(2)
            makeEntity(C.mealFireplaceSelector,'fireplace')
            C.EnsureNpcHasMealBowl=function() return 'bowl:night' end
            records[night:GetName()].mealKind='evening'
            token=collect(night);R.ranges.eveningMeal={minSeconds=1,maxSeconds=1}
        """)
        g=self.lua.globals()
        driver=MealBtDriver(self.lua,ROOT/'src/AI/nebakovrising_meal.xml',g.night,g.token)
        reached_idle=False
        for _ in range(65):
            self.assertIsNone(driver.tick())
            if self.lua.eval("C.activityRuns[tostring(night.this.id)].phase=='evening_idle'"):
                reached_idle=True;break
        self.assertTrue(reached_idle)
        self.assertEqual(driver.stance,'standing')
        self.lua.execute('worldHour=11')
        for _ in range(15):
            result=driver.tick()
            if result is not None:
                self.assertTrue(result);break
        else:self.fail('Night meal did not yield to 11:00 sleep')
        self.lua.execute('C.FinishNpcActivity(night.this.id,token);assert(C.NextNpcActivity(night)=="sleep")')

    def test_wake_batches_are_separate_and_other_shift_sleep_does_not_reset_them(self):
        self.lua.execute("""
            guard(1,'day');guard(2,'day');guard(3,'night');guard(4,'night');S.Reconcile()
            for i=1,4 do C.activityRuns[tostring(g[i].this.id)]={kind='sleep'} end
            worldHour=8;C.AssignWakeUpSlots('day')
            local one,two=tostring(g[1].this.id),tostring(g[2].this.id)
            assert(C.npcWakeSlots[one] and C.npcWakeSlots[two])
            assert(math.min(C.npcWakeSlots[one],C.npcWakeSlots[two])==clock)
            local gap=math.abs(C.npcWakeSlots[one]-C.npcWakeSlots[two]);assert(gap>=5 and gap<=15)
            worldHour=12;assert(C.IsNpcSleepTime(g[3].this.id));assert(C.wakeBatches.day)
            worldHour=19;C.AssignWakeUpSlots('night')
            local three,four=tostring(g[3].this.id),tostring(g[4].this.id)
            assert(math.min(C.npcWakeSlots[three],C.npcWakeSlots[four])==clock)
            assert(math.abs(C.npcWakeSlots[three]-C.npcWakeSlots[four])>=5)
            worldHour=0;C.IsNpcSleepTime(g[1].this.id)
            assert(not C.wakeBatches.day and C.wakeBatches.night)
            worldHour=8;C.AssignWakeUpSlots('day');assert(C.wakeBatches.day)
        """)

    def test_promotion_wakes_new_night_guard_instead_of_leaving_castle_empty(self):
        self.lua.execute("""
            guard(1,'day');guard(2,'day');guard(3,'night');S.Reconcile();worldHour=3
            for i=1,2 do C.activityRuns[tostring(g[i].this.id)]={kind='sleep'} end
            g[3].dead=true;C.RemoveManagedNpcRecord(g[3]:GetName())
            local promoted=S.Get(g[1])=='night' and g[1] or g[2]
            assert(not C.IsNpcSleepTime(promoted.this.id))
            assert(C.npcWakeSlots[tostring(promoted.this.id)]==clock)
        """)

    def test_bad_shift_config_rejected_atomically_and_custom_hours_apply(self):
        self.lua.execute("""
            assert(nebakovrising.Config.shiftSchedules.night.sleepHour==11)
            settings.shifts.night.sleepHour=19;settings.patrol.minSeconds=1
            assert(not R.Apply(settings));assert(R.ranges.patrol.minSeconds==10)
            settings.shifts.night.sleepHour=10;assert(R.Apply(settings))
            assert(nebakovrising.Config.shiftSchedules.night.sleepHour==10)
            settings.shifts.night.wakeHour=0/0;assert(not R.Apply(settings))
        """)

    def test_policy_queries_do_not_scan_sleepers_or_schedule_wake_waves(self):
        self.lua.execute("""
            pair();worldHour=3
            C.GetSleepingNpcWuids=function() error('Unexpected full NPC scan') end
            assert(not C.IsNpcSleepTime(night.this.id,true))
            assert(not C.PatrolShouldStop(night));assert(not C.IsPostMealIdle(night))
            assert(not C.ShouldStartEveningMeal(night))
            assert(C.NextNpcActivity(night)=='patrol')
            assert(next(C.npcWakeSlots)==nil and next(C.wakeBatches)==nil)
        """)

    def test_wake_breakfast_replaces_interrupted_previous_meal_without_stale_callbacks(self):
        self.lua.execute("""
            pair();worldHour=19
            local record=records[night:GetName()]
            record.mealKind='evening';record.eveningMealDone=true
            record.mealStage='eating';record.mealCollected=true;record.mealEaten=true
            token=begin(night,'sleep')
            assert(not C.StartBreakfast(night,token-1));assert(record.mealKind=='evening')
            assert(C.StartBreakfast(night,token));assert(record.mealKind=='breakfast')
            assert(not record.eveningMealDone and not record.mealCollected and not record.mealEaten)
            assert(record.mealStage=='walking_to_cauldron')
            R.ranges.breakfast={minSeconds=2,maxSeconds=2}
            assert(C.MealDuration(night)==2)
        """)

    def test_only_on_duty_shift_restores_patrol_point_reservations(self):
        self.lua.execute("""
            pair();worldHour=3
            records[day:GetName()].patrolSelector='dayPoint'
            records[night:GetName()].patrolSelector='nightPoint'
            assert(C.ReservePatrolPoints()==1)
            assert(C.patrolOwners.dayPoint==nil and C.patrolOwners.nightPoint==night:GetName())
        """)

    def test_day_guard_keeps_patrolling_during_night_shift_breakfast_overlap(self):
        self.lua.execute("""
            pair();worldHour=19.5
            assert(not C.IsNpcSleepTime(day.this.id,true))
            assert(not C.IsNpcSleepTime(night.this.id,true))
            assert(not C.PatrolShouldStop(day) and not C.ShouldStartEveningMeal(day))
            assert(C.NextNpcActivity(day)=='patrol')
        """)

    def test_meal_and_conversation_sleep_checks_always_pass_npc_identity(self):
        for relative in ['AI/nebakovrising_meal.xml','Scripts/mods/nebakov_conversations.lua']:
            self.assertNotIn('IsNpcSleepTime()', (ROOT/'src'/relative).read_text())

    def test_main_loads_shifts_and_registers_diagnostic_command(self):
        source=(ROOT/'src/Scripts/mods/nebakovrising.lua').read_text()
        self.assertIn('Scripts/mods/nebakov_shifts.lua',source)
        self.assertIn('nebakovrising_shift_status',source)


class ShiftConversationTests(unittest.TestCase):
    def setUp(self):
        fixture=patrol.LuaDirectorTests();fixture.setUp();self.lua=fixture.lua
        self.lua.execute((ROOT/'src/Scripts/mods/nebakov_shifts.lua').read_text('utf-8'))
        self.lua.execute("""
            S=nebakovrising.Shifts
            local old=nebakovrising.Roles.Resolve
            nebakovrising.Roles.Resolve=function(name) local role=old(name);role.bedPool='guard';return role end
            c=diner('guard_c');d=diner('guard_d');c.pos={x=5,y=0,z=0};d.pos={x=11,y=0,z=0}
            tc=begin(c,'patrol');td=begin(d,'patrol');D.SetPatrolPose(c,tc,'guard');D.SetPatrolPose(d,td,'guard')
            records.guard_a.guardShift='day';records.guard_b.guardShift='day'
            records.guard_c.guardShift='night';records.guard_d.guardShift='night';S.Reconcile()
        """)

    def test_at_three_am_only_night_pair_can_start_a_conversation(self):
        self.lua.execute("""
            worldHour=3;assert(not D.IsEligible(a) and not D.IsEligible(b))
            assert(D.IsEligible(c) and D.IsEligible(d));assert(D.TryStart(true))
            for _,p in ipairs(D.active.participants) do assert(S.Get(p.name)=='night') end
        """)

    def test_at_noon_only_day_pair_can_start_a_conversation(self):
        self.lua.execute("""
            worldHour=12;assert(D.IsEligible(a) and D.IsEligible(b))
            assert(not D.IsEligible(c) and not D.IsEligible(d));assert(D.TryStart(true))
            for _,p in ipairs(D.active.participants) do assert(S.Get(p.name)=='day') end
        """)


if __name__=='__main__':unittest.main()
