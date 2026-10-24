"""Run with Python + lupa (Lua 5.1); game APIs are mocked, not the mod logic."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

from lupa.lua51 import LuaRuntime
sys.dont_write_bytecode = True
from meal_bt_driver import MealBtDriver

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/Scripts/mods/CastleUtils.lua"

MOCKS = r"""
clock = 100
worldHour = 21
entities = {}
wuidEntities = {}
records = {}
occupants = {}
store = {health = {nebakovNpcRecords = records}}
function store:GetName() return 'nebakovrising_SaveStore' end
System = {
    GetCurrTime = function() return clock end,
    LogAlways = function() end,
    GetEntitiesByClass = function(class)
        if class == 'BasicEntity' then return {store} end
        return {}
    end,
    GetEntityIdByName = function(name) if entities[name] then return name end end,
    GetEntity = function(id) return entities[id] end,
}
XGenAIModule = {
    GetMyWUID = function(entity) return entity.this.id end,
    GetEntityByWUID = function(wuid) return wuidEntities[wuid] end,
    FindLinks = function(wuid, tag) return occupants[wuid] or {} end,
}
Calendar = {GetWorldHourOfDay = function() return worldHour end}
nebakovrising = {
    Config = {bedBehaviorEnabled = true, npcSleepStartHour = 0, npcWakeHour = 8,
        eveningMealHour = 20, eveningMealStaggerMin = 1, eveningMealStaggerMax = 1,
        activityRequestTimeout = 10, activityHeartbeatTimeout = 15,
        stanceTransitionTimeout = 20, mealSeatTimeout = 30,
        mealTargetReadyTimeout = 10, mealSeatRetryCooldown = 60},
    Roles = {Resolve = function(name) return {id = 'guard_melee', eveningMeal = true,
        patrol = {fixed = {}, roaming = {}, waitMin = 10, waitMax = 180}} end},
}
function makeEntity(name, wuid)
    local entity = {this = {id = wuid}, id = 'entity:' .. name}
    function entity:GetName() return name end
    function entity:GetWorldPos() return {x = 1, y = 2, z = 3} end
    entities[name] = entity
    wuidEntities[wuid] = entity
    return entity
end
function diner(name)
    local entity = makeEntity(name, 'npc:' .. name)
    records[name] = {managed = true, role = 'guard_melee', mealKind = 'evening'}
    return entity
end
function seats(count)
    local list = {}
    for i = 1, count do
        local name = 'seat' .. i
        list[#list + 1] = name
        makeEntity(name, 'slot:' .. i)
    end
    nebakovrising.CastleUtils.mealBenchSelectors = list
end
function begin(entity, kind)
    local castle = nebakovrising.CastleUtils
    assert(castle.RequestNpcActivity(entity, kind))
    return castle.BeginNpcActivity(entity.this.id, kind)
end
function collect(entity)
    local castle = nebakovrising.CastleUtils
    local token = begin(entity, 'meal_walk')
    assert(castle.SetMealProgress(entity, 'meal_pending', token))
    assert(castle.OnMealCollected(entity, token))
    return token
end
"""


class MealFlowTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(MOCKS)
        self.lua.execute(SOURCE.read_text(encoding="utf-8"))
        self.lua.execute("C = nebakovrising.CastleUtils; seats(10)")

    def run_lua(self, code):
        self.lua.execute(code)

    def test_reservation_happens_in_collection_without_scheduler_handoff(self):
        self.run_lua("""
            a = diner('a'); b = diner('b')
            ta = collect(a)
            assert(records.a.mealBenchSelector == 'seat1')
            assert(C.GetBedWalkState(a.this.id) ~= 'eating')
            assert(C.NextNpcActivity(a) == nil)
            tb = collect(b)
            assert(records.b.mealBenchSelector == 'seat2')
            assert(records.a.mealBenchSelector == 'seat1')
        """)

    def test_later_caller_cannot_overtake_waiting_diner(self):
        self.run_lua("""
            seats(1)
            owner = diner('owner'); towner = collect(owner)
            a = diner('a'); collect(a)
            b = diner('b'); collect(b)
            assert(records.a.mealQueueOrder < records.b.mealQueueOrder)
            C.OnMealEaten(owner, towner); C.FinishMeal(owner, towner)
            assert(C.GetMealBench(b.this.id) == nil)
            assert(records.a.mealBenchSelector == 'seat1')
            assert(C.GetMealBench(a.this.id) ~= nil)
        """)

    def test_thirteen_diners_use_ten_seats_and_released_seats_advance_queue(self):
        self.run_lua("""
            diners = {}; tokens = {}
            for i = 1, 13 do diners[i] = diner('npc' .. i); tokens[i] = collect(diners[i]) end
            for i = 1, 10 do assert(records['npc' .. i].mealBenchSelector) end
            for i = 11, 13 do assert(not records['npc' .. i].mealBenchSelector) end
            for i = 1, 3 do
                assert(C.OnMealEaten(diners[i], tokens[i]))
                assert(C.FinishMeal(diners[i], tokens[i]))
            end
            C.GetMealBench(diners[13].this.id)
            for i = 11, 13 do
                assert(records['npc' .. i].mealBenchSelector)
                assert(records['npc' .. i].mealCollected)
            end
        """)

    def test_timeout_skips_failed_seat_then_cooldown_expires(self):
        self.run_lua("""
            seats(2); a = diner('a'); collect(a)
            C.RetryMealBench(a.this.id, 'seat_timeout')
            C.GetMealBench(a.this.id)
            assert(records.a.mealBenchSelector == 'seat2')
            C.RetryMealBench(a.this.id, 'seat_failed')
            assert(C.GetMealBench(a.this.id) == nil)
            clock = clock + 61
            assert(C.GetMealBench(a.this.id) ~= nil)
            assert(records.a.mealBenchSelector == 'seat1')
            assert(records.a.mealCollected)
        """)

    def test_eating_animation_failure_does_not_blacklist_valid_seat(self):
        self.run_lua("""
            seats(1); a = diner('a'); collect(a)
            C.RetryMealBench(a.this.id, 'eat_failed')
            assert(C.GetMealBench(a.this.id) ~= nil)
            assert(records.a.mealCollected)
        """)

    def test_missing_saved_target_reassigned_after_streaming_grace(self):
        self.run_lua("""
            a = diner('a'); collect(a)
            entities.seat1 = nil
            assert(C.GetMealBench(a.this.id) == nil)
            assert(records.a.mealBenchSelector == 'seat1')
            clock = clock + 11
            assert(C.GetMealBench(a.this.id) ~= nil)
            assert(records.a.mealBenchSelector == 'seat2')
        """)

    def test_foreign_occupant_and_duplicate_wuid_are_not_assigned(self):
        self.run_lua("""
            foreign = makeEntity('foreign', 'npc:foreign')
            occupants['slot:1'] = {foreign.this.id}
            alias = makeEntity('seat_alias', 'slot:2')
            C.mealBenchSelectors = {'seat1', 'seat2', 'seat_alias', 'seat3'}
            a = diner('a'); collect(a)
            b = diner('b'); collect(b)
            assert(records.a.mealBenchSelector == 'seat2')
            assert(records.b.mealBenchSelector == 'seat3')
        """)

    def test_release_without_runtime_assignment_and_death_cleanup(self):
        self.run_lua("""
            a = diner('a'); collect(a)
            C.mealBenchAssignments.a = nil
            assert(C.ReleaseMealBenchForNpc('a'))
            assert(C.mealBenchOwners.seat1 == nil)
            C.GetMealBench(a.this.id)
            C.patrolOwners.post = 'a'; C.patrolAssignments.a = {}
            assert(C.RemoveManagedNpcRecord('a'))
            assert(records.a == nil and C.mealBenchOwners.seat1 == nil)
            assert(C.patrolOwners.post == nil and C.patrolAssignments.a == nil)
            assert(C.activityRuns[a.this.id] == nil)
        """)

    def test_save_reload_preserves_food_order_and_resolves_current_wuid(self):
        self.run_lua("""
            a = diner('a'); collect(a)
            b = diner('b'); collect(b)
            order = records.a.mealQueueOrder
            C.ResetBedAssignments(); C.ReserveMealBenches()
            C.ReserveMealBenches()
            makeEntity('seat1', 'slot:new1')
            local seat, wuid = C.GetMealBench(a.this.id)
            assert(wuid == 'slot:new1')
            assert(records.a.mealCollected and records.a.mealQueueOrder == order)
            assert(records.b.mealBenchSelector == 'seat2')
        """)

    def test_request_acknowledgement_timeout_and_stale_cleanup(self):
        self.run_lua("""
            a = diner('a'); records.a.mealStage = 'meal_ready'; records.a.mealCollected = true
            assert(C.NextNpcActivity(a) == 'meal_table')
            assert(C.GetBedWalkState(a.this.id) == 'meal_table_requested')
            old = C.activityRuns[a.this.id].token
            clock = clock + 11
            assert(C.NextNpcActivity(a) == 'meal_table')
            token = C.BeginNpcActivity(a.this.id, 'meal_table')
            assert(token > old)
            assert(C.BeginNpcActivity(a.this.id, 'meal_table') == 0)
            assert(not C.FailNpcActivity(a, old))
            assert(not C.FinishNpcActivity(a.this.id, old))
            assert(not C.SetMealProgress(a, 'meal_pending', old))
            assert(C.OwnsNpcActivity(a.this.id, token))
        """)

    def test_long_patrol_does_not_resubmit_or_release_before_standing(self):
        self.run_lua("""
            worldHour = 19; a = diner('a'); token = begin(a, 'patrol')
            C.patrolOwners.post = 'a'; C.patrolAssignments.a = {selector = 'post'}
            for i = 1, 30 do
                clock = clock + 1
                assert(C.ActivityHeartbeat(a.this.id, token))
                assert(C.NextNpcActivity(a) == nil)
            end
            records.a.mealStage = 'meal_pending'
            assert(C.PatrolShouldStop(a))
            assert(C.GetBedWalkState(a.this.id) == 'patrol_exiting')
            assert(C.patrolOwners.post == 'a')
            assert(C.ReleasePatrolAfterStanding(a.this.id, token))
            C.FinishNpcActivity(a.this.id, token)
            assert(C.NextNpcActivity(a) == 'meal_walk')
        """)

    def test_completed_evening_meal_idles_then_sleeps(self):
        self.run_lua("""
            a = diner('a'); token = collect(a)
            assert(C.OnMealEaten(a, token))
            assert(C.HasEatenMeal(a))
            C.FinishMeal(a, token); C.FinishNpcActivity(a.this.id, token)
            assert(records.a.eveningMealDone and records.a.mealStage == nil)
            assert(C.NextNpcActivity(a) == 'evening_idle')
            token = C.BeginNpcActivity(a.this.id, 'evening_idle')
            worldHour = 0; C.bedAssignmentsByWuid[a.this.id] = {wuid = 'bed'}
            assert(not C.IsPostMealIdle(a))
            C.FinishNpcActivity(a.this.id, token)
            assert(C.NextNpcActivity(a) == 'sleep')
        """)

    def test_legacy_food_confirmation_and_eaten_records(self):
        self.run_lua("""
            a = diner('a'); records.a.mealStage = 'eating'
            assert(C.NextNpcActivity(a) == 'meal_walk')
            assert(records.a.mealStage == 'meal_pending')
            b = diner('b'); records.b.mealStage = 'eating'; records.b.mealCollected = true
            records.b.eveningMealDone = true
            assert(C.HasEatenMeal(b))
            assert(C.NextNpcActivity(b) == 'meal_table')
        """)

    def test_legacy_eaten_marker_survives_daily_evening_flag_reset(self):
        self.run_lua("""
            a = diner('a'); records.a.mealStage = 'eating'; records.a.mealCollected = true
            records.a.eveningMealDone = true
            worldHour = 9
            assert(C.NextNpcActivity(a) == 'meal_table')
            assert(records.a.eveningMealDone == nil)
            assert(C.HasEatenMeal(a))
        """)

    def test_seat_timeout_excludes_normal_eating_duration(self):
        self.run_lua("""
            a = diner('a'); token = collect(a)
            C.SetActivityPhase(a, token, 'seating', 30)
            clock = clock + 31; assert(C.MealSeatTimedOut(a.this.id, token))
            C.SetActivityPhase(a, token, 'seated', 20)
            clock = clock + 21; assert(C.MealSeatTimedOut(a.this.id, token))
            C.SetActivityPhase(a, token, 'eating', 10)
            clock = clock + 11
            assert(not C.MealSeatTimedOut(a.this.id, token))
            assert(C.ActivityPhaseExpired(a.this.id, token))
        """)

    def driver(self, **kwargs):
        self.run_lua("""
            a = diner('a'); token = collect(a)
            makeEntity(C.mealFireplaceSelector, 'fireplace')
            C.EnsureNpcHasMealBowl = function() return 'bowl:a' end
        """)
        g = self.lua.globals()
        return MealBtDriver(self.lua, ROOT / "src/AI/nebakovrising_meal.xml", g.a, g.token, **kwargs)

    def test_bt_finishes_meal_stands_releases_and_idles_until_bedtime(self):
        driver = self.driver()
        driver.until(lambda: self.lua.eval("records.a.mealStage == nil and records.a.eveningMealDone == true"))
        self.assertIn(("release", "standing"), driver.events)
        self.assertTrue(self.lua.eval("C.mealBenchOwners.seat1 == nil"))
        driver.until(lambda: self.lua.eval("C.GetBedWalkState(a.this.id) == 'evening_idle'"))
        for _ in range(10):
            self.assertIsNone(driver.tick())
        self.assertEqual(driver.stance, "standing")
        self.run_lua("worldHour = 0")
        for _ in range(20):
            result = driver.tick()
            if result is not None:
                self.assertTrue(result)
                break
        else:
            self.fail("Evening idle did not end at bedtime")
        self.assertEqual(sum("onNPCEating" in event[0] for event in driver.events), 1)

    def test_bt_times_out_blocked_seat_and_eats_at_alternative(self):
        self.run_lua("seats(2)")
        driver = self.driver(blocked_seats={"slot:1"})
        driver.until(lambda: self.lua.eval("records.a.mealBenchSelector == 'seat2'"))
        self.assertTrue(self.lua.eval("records.a.mealCollected"))
        self.assertEqual(driver.stance, "standing")
        driver.until(lambda: self.lua.eval("records.a.mealStage == nil and records.a.eveningMealDone == true"))
        self.assertIn(("release", "standing"), driver.events)
        driver.generator.close()

    def test_bt_bowl_acquisition_is_covered_by_seating_timeout(self):
        driver = self.driver(blocked_bowl=True)
        driver.until(lambda: self.lua.eval("C.mealBenchAttempts.a ~= nil and C.mealBenchAttempts.a.seat1 ~= nil"))
        self.assertEqual(driver.stance, "standing")
        self.assertTrue(self.lua.eval("records.a.mealCollected and not records.a.mealEaten"))
        driver.generator.close()

    def test_bt_failed_standing_keeps_reservation_for_safe_recovery(self):
        driver = self.driver(blocked_standing=True)
        for _ in range(80):
            result = driver.tick()
            if result is not None:
                self.assertFalse(result)
                break
        else:
            self.fail("Standing transition did not time out")
        self.assertFalse(any(event[0] == "release" for event in driver.events))
        self.assertTrue(self.lua.eval("C.mealBenchOwners.seat1 == 'a'"))

    def test_bt_resume_eaten_meal_releases_without_eating_again(self):
        driver = self.driver()
        self.run_lua("C.OnMealEaten(a, token)")
        driver.until(lambda: self.lua.eval("records.a.mealStage == nil"))
        self.assertFalse(any("onNPCEating" in event[0] for event in driver.events))
        self.assertIn(("release", "standing"), driver.events)
        driver.generator.close()

    def test_restore_reconciles_duplicate_physical_slot(self):
        self.run_lua("""
            makeEntity('seat_alias', 'slot:1')
            C.mealBenchSelectors = {'seat1', 'seat_alias', 'seat2'}
            a = diner('a'); collect(a)
            b = diner('b'); collect(b)
            records.b.mealBenchSelector = 'seat_alias'
            C.ResetBedAssignments(); C.ReserveMealBenches()
            assert(records.a.mealBenchSelector == 'seat1')
            assert(records.b.mealBenchSelector == nil)
            C.GetMealBench(b.this.id)
            assert(records.b.mealBenchSelector == 'seat2')
        """)

    def test_bt_waiting_for_seat_exits_safely_at_bedtime(self):
        self.run_lua("seats(1); owner = diner('owner'); collect(owner)")
        driver = self.driver()
        driver.until(lambda: self.lua.eval("records.a.mealStage == 'waiting_for_seat'"))
        self.run_lua("worldHour = 0")
        for _ in range(30):
            result = driver.tick()
            if result is not None:
                self.assertTrue(result)
                break
        else:
            self.fail("Seat queue did not yield to sleep")
        self.assertTrue(self.lua.eval("C.mealBenchOwners.seat1 == 'owner' and records.a.mealStage == nil"))
        self.assertFalse(any("onNPCEating" in event[0] for event in driver.events))

    def test_bt_breakfast_returns_without_evening_idle(self):
        driver = self.driver()
        self.run_lua("worldHour = 9; records.a.mealKind = nil")
        for _ in range(160):
            result = driver.tick()
            if result is not None:
                self.assertTrue(result)
                break
        else:
            self.fail("Breakfast did not return")
        self.assertTrue(self.lua.eval("records.a.mealStage == nil and not C.IsPostMealIdle(a)"))
        self.assertEqual(driver.stance, "standing")

    def test_bt_movement_deadline_expires_despite_liveness_heartbeat(self):
        driver = self.driver()
        self.run_lua("C.SetActivityPhase(a, token, 'moving', 2)")
        driver.generator.close()
        driver.generator = driver.function("nebakovrising_activity_deadline", driver.token)
        for _ in range(20):
            result = driver.tick()
            if result is not None:
                self.assertFalse(result)
                break
        else:
            self.fail("Movement deadline never expired")
        self.assertTrue(self.lua.eval("C.OwnsNpcActivity(a.this.id, token)"))

    def test_bt_patrol_stop_observes_request_during_blocked_work(self):
        driver = self.driver()
        self.run_lua("records.a.mealStage = nil; C.activityRuns[a.this.id].kind = 'patrol'")
        driver.generator.close()
        driver.generator = driver.function("nebakovrising_patrol_stop", driver.token)
        for _ in range(4):
            self.assertIsNone(driver.tick())
        self.run_lua("records.a.mealStage = 'meal_pending'")
        for _ in range(10):
            result = driver.tick()
            if result is not None:
                self.assertTrue(result)
                break
        else:
            self.fail("Patrol stop did not observe meal request")
        self.assertTrue(self.lua.eval("C.GetBedWalkState(a.this.id) == 'patrol_exiting'"))

    def test_sleep_cancels_stalled_seating_without_waiting_for_timeout(self):
        self.run_lua("""
            a = diner('a'); token = collect(a)
            C.SetActivityPhase(a, token, 'seating', 30)
            assert(not C.MealSeatTimedOut(a.this.id, token))
            worldHour = 0
            assert(C.MealSeatTimedOut(a.this.id, token))
        """)


class SourceContractTests(unittest.TestCase):
    def test_xml_and_lua51_syntax(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        check = lua.eval("function(code) local f, e = loadstring(code); return f ~= nil, e end")
        for p in (ROOT / "src/Scripts").rglob("*.lua"):
            ok, error = check(p.read_text(encoding="utf-8"))
            self.assertTrue(ok, f"{p}: {error}")
        for p in (ROOT / "src").rglob("*.xml"):
            root = ET.parse(p).getroot()
            for node in root.iter("ExecuteLua"):
                ok, error = check(node.get("code", ""))
                self.assertTrue(ok, f"{p}: {error}")

    def test_continuous_collection_and_actual_eating_state(self):
        root = ET.parse(ROOT / "src/AI/nebakovrising_walk_to_bed.xml").getroot()
        collections = 0
        for parent in root.iter():
            for i, child in enumerate(list(parent)):
                if child.tag == "ExecuteLua" and "OnMealCollected" in child.get("code", ""):
                    collections += 1
                    self.assertEqual(list(parent)[i + 1].tag, "Function_nebakovrising_meal_at_table")
        self.assertEqual(collections, 2)
        self.assertFalse(list(root.iter("AddInterrupt")))
        switch = ET.parse(ROOT / "src/AI/npc/basic/switch/switch.xml").getroot()
        self.assertFalse(any("SetMealProgress(entity, 'eating'" in n.get("code", "") for n in switch.iter("ExecuteLua")))
        common = ET.parse(ROOT / "src/AI/nebakovrising_meal.xml").getroot()
        self.assertFalse(any(n.get("stance") == "sitting" for n in common.find("BehaviorTree[@name='nebakovrising_post_meal_idle']").iter("StanceElement")))
        self.assertNotIn("1000000", (ROOT / "src/AI/nebakovrising_meal.xml").read_text())

    def test_functions_registered_and_moves_require_standing(self):
        templates = ET.parse(ROOT / "src/libs/tables/ai/smartEntity/SmartEntity__so_interrupt__nebakovrising.xml").getroot()
        registered = {n.get("Name") for n in templates.iter("SmartBehaviorTemplate")}
        labels = set()
        for p in (ROOT / "src/AI").glob("nebakovrising*.xml"):
            root = ET.parse(p).getroot()
            parents = {child: parent for parent in root.iter() for child in parent}
            for n in root.iter():
                if n.tag.startswith("Function_nebakovrising_"):
                    self.assertIn(n.tag.removeprefix("Function_"), registered)
                    self.assertNotIn(n.get("nodeLabel"), labels)
                    labels.add(n.get("nodeLabel"))
                if n.tag == "Move":
                    ancestors = []
                    at = n
                    while at in parents:
                        at = parents[at]
                        ancestors.append(at)
                    self.assertTrue(any(a.tag == "StanceElement" and a.get("stance") == "standing" for a in ancestors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
