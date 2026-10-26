"""Real Lua policies and BT branches; engine animation/pathfinding remains mocked."""
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from lupa.lua51 import LuaRuntime
import test_meal_flow as meal
from meal_bt_driver import MealBtDriver
from nebakov_voice_defaults import DEFAULT_PROFILE
from nebakov_voice_prompts import PromptProfiles
import json

ROOT=Path(__file__).resolve().parents[1]

class RoutineEquipmentTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute(meal.MOCKS)
        for file in ['CastleUtils.lua','nebakov_routine_config.lua','NpcNamesData.lua','nebakov_npc_names.lua']:
            self.lua.execute((ROOT/'src/Scripts/mods'/file).read_text(encoding='utf-8'))
        self.lua.execute("C=nebakovrising.CastleUtils;R=nebakovrising.Routines;a=diner('a');token=begin(a,'patrol')")

    def ranges(self):
        self.lua.globals().config_file=str(ROOT/'Config/routines.lua')
        self.lua.execute('settings=dofile(config_file);assert(R.Apply(settings))')

    def test_durations_use_distinct_config_ranges_without_touching_other_npcs(self):
        self.ranges()
        self.lua.execute("""
            settings.breakfast={minSeconds=3,maxSeconds=3}
            settings.eveningMeal={minSeconds=7,maxSeconds=7}
            settings.patrol={minSeconds=11,maxSeconds=11};assert(R.Apply(settings))
            assert(C.MealDuration(a)==7);records.a.mealKind=nil;assert(C.MealDuration(a)==3)
            assert(C.PatrolWaitDuration({waitMin=1,waitMax=1})==11)
            assert(nebakovrising.Config.wakeStaggerMin==5 and nebakovrising.Config.wakeStaggerMax==15)
            settings.patrol.minSeconds=15;assert(not R.Apply(settings))
            assert(C.PatrolWaitDuration({})==11)
        """)

    def inventory(self):
        self.lua.execute("""
            items={};all={};removed={};worn={}
            nebakovrising.EquipmentData={items={},weaponClasses={},slotOrder={}}
            local D=nebakovrising.EquipmentData
            for _,slot in ipairs({7,8,18,19,22,23,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45}) do
                local id='i'..slot;local class='c'..slot
                all[#all+1]=id;items[id]={class=class};D.items[class]={slot=slot};D.slotOrder[slot]=slot
            end
            all[#all+1]='sword';items.sword={class='weapon'};D.weaponClasses.weapon=true
            all[#all+1]='food';items.food={class='food'}
            ItemManager={GetItem=function(id) return items[id] end}
            a.inventory={GetInventoryTable=function() return all end}
            a.actor={UnequipInventoryItem=function(self,id) removed[id]=true;return true end,
                     EquipInventoryItem=function(self,id) worn[id]=true;return true end}
        """)

    def test_sleep_keeps_only_body_base_and_padded_leg_slots_and_deletes_nothing(self):
        self.inventory()
        self.lua.execute("""
            assert(C.UnequipSleepingArmor(a))
            assert(not removed.i35 and not removed.i36 and not removed.i41 and not removed.food)
            for _,slot in ipairs({7,8,18,19,22,23,30,31,32,33,34,37,38,39,40,42,43,44,45}) do assert(removed['i'..slot]) end
            assert(removed.sword and #all==24)
            assert(C.EquipSleepingEquipment(a));assert(worn.i8 and worn.i30 and worn.sword)
            assert(#all==24)
        """)

    def test_meal_removes_all_head_slots_and_patrol_restores_without_changing_inventory(self):
        self.inventory()
        self.lua.execute("""
            assert(C.UnequipMealHeadwear(a))
            for _,slot in ipairs({23,31,32,33,34}) do assert(removed['i'..slot]) end
            assert(not removed.i37 and not removed.i8 and not removed.sword)
            assert(C.EquipPatrolHeadwear(a));assert(worn.i32 and worn.i34);assert(#all==24)
        """)

    def test_inventory_api_failure_is_safe(self):
        self.lua.execute('assert(not C.UnequipMealHeadwear(a));assert(not C.UnequipSleepingArmor(a))')

    def test_already_standing_skips_stance_request_and_wait_action(self):
        driver=MealBtDriver(self.lua,ROOT/'src/AI/nebakovrising_meal.xml',self.lua.globals().a,self.lua.globals().token)
        driver.stance='standing'
        generator=driver.function('nebakovrising_stand',driver.token)
        with self.assertRaises(StopIteration) as result:next(generator)
        self.assertTrue(result.exception.value)
        self.assertIsNone(self.lua.eval('C.activityRuns[tostring(a.this.id)].phase'))

    def test_sitting_still_waits_for_actual_stand(self):
        driver=MealBtDriver(self.lua,ROOT/'src/AI/nebakovrising_meal.xml',self.lua.globals().a,self.lua.globals().token,blocked_standing=True)
        driver.generator=driver.function('nebakovrising_stand',driver.token)
        next(driver.generator)
        self.assertEqual(driver.stance,'sitting')
        self.assertEqual(self.lua.eval('C.activityRuns[tostring(a.this.id)].phase'),'standing')
        driver.generator.close()
        driver=MealBtDriver(self.lua,ROOT/'src/AI/nebakovrising_meal.xml',self.lua.globals().a,self.lua.globals().token)
        driver.generator=driver.function('nebakovrising_stand',driver.token)
        for _ in range(30):
            self.lua.execute('clock=clock+0.1')
            try:next(driver.generator)
            except StopIteration:break
        self.assertEqual(driver.stance,'standing')

    def test_ui_name_matches_saved_name_without_renaming_entity(self):
        self.lua.execute("""
            a.Properties={guidSharedSoulId='6e656261-0001-4b00-9000-000000000001'}
            N=nebakovrising.Names;first=N.Assign(a);assert(first~='Guard')
            assert(a:GetName()=='a' and records.a.displayName==first)
            N.pending={};a.Properties=nil
            a.soul={GetNameStringId=function() return records.a.displayNameKey end}
            assert(N.Get(a)==first)
        """)

class RoutineSourceTests(unittest.TestCase):
    def test_bed_and_chair_use_native_animation_entry_instead_of_object_origin_move(self):
        bed=ET.parse(ROOT/'src/AI/nebakovrising_walk_to_bed.xml').getroot()
        self.assertFalse(any(n.get('destinationSpecification')=='$bedPos' for n in bed.iter('Move')))
        lying=next(n for n in bed.iter('StanceElement') if n.get('stance')=='lying')
        self.assertTrue(any('UnequipSleepingArmor' in n.get('code','') for n in lying.iter('ExecuteLua')))
        patrol=ET.parse(ROOT/'src/AI/nebakovrising_patrol.xml').getroot()
        parent={child:p for p in patrol.iter() for child in p}
        move=next(patrol.iter('Move'));p=move
        while p in parent:
            p=parent[p]
            if p.tag=='IfCondition' and p.get('condition')=="$pointKind ~= 'sit'":break
        else:self.fail('Explicit object-origin Move must exclude benches')

    def test_headwear_is_removed_before_both_kettle_moves(self):
        root=ET.parse(ROOT/'src/AI/nebakovrising_walk_to_bed.xml').getroot()
        count=0
        for sequence in root.iter('Sequence'):
            children=list(sequence)
            for i,n in enumerate(children):
                if n.tag=='ExecuteLua' and 'UnequipMealHeadwear' in n.get('code',''):
                    self.assertTrue(any(m.get('destinationSpecification')=='$mealPos' for c in children[i+1:] for m in c.iter('Move')))
                    count+=1
        self.assertEqual(count,2)

    def test_all_mod_character_names_have_localization_and_prompt_identity(self):
        table=ET.parse(ROOT/'localization_src/text__nebakovrising.xml').getroot()
        labels={r[0].text:r[2].text for r in table}
        self.assertEqual(len(labels),50)
        names=ET.parse(ROOT/'src/libs/tables/skald/skald_character__nebakovrising.xml').getroot()
        for c in names.iter('skald_character'):
            if c.get('skald_character_name').startswith('char_nebakov_'):
                self.assertIn(c.get('ui_name_string_name'),labels)
                self.assertNotIn('dump',labels[c.get('ui_name_string_name')])
        with tempfile.TemporaryDirectory(dir=ROOT/'tools') as temp:
            folder=Path(temp)
            (folder/'patrol-daily-talk.json').write_text(json.dumps(DEFAULT_PROFILE),encoding='utf-8')
            packet={'director':{'behavior':'patrol','profile_id':'patrol-daily-talk',
                'context':{'guard_a_name':'Jan','guard_b_name':'Petr'}}}
            prepared=PromptProfiles(folder).prepare(packet)
            self.assertIn('Jan (speaker label Marek)',prepared['text'])
            self.assertIn('Hey, Petr!',prepared['text'])

if __name__=='__main__':unittest.main()
