"""Real stand/weapon selection BTs; physical animation and hand nodes are mocks."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import test_patrol_conversations as patrol
from meal_bt_driver import MealBtDriver
from nebakov_voice_defaults import ensure_defaults
from nebakov_voice_prompts import PromptProfiles


class WeaponDriver(patrol.ConversationDriver):
    def __init__(self,lua,entity,token,left,right,loaded=False):
        super().__init__(lua,entity,token)
        self.left,self.right,self.loaded=left,right,loaded
        self.stance='standing';self.held=None

    def node(self,node,data):
        tag=node.tag
        if tag=='GetWeaponsFromWeaponSet':
            data.setWeapons[0],data.setWeapons[1]=self.left,self.right
            return True
        if tag=='GetItemType':
            slot=0 if node.get('WUID').endswith('[0]') else 1
            data.itemType={'crossbow':'crossbow_light','gun':'rifle','sword':'sword_short'}.get(data.setWeapons[slot],'torch')
            return True
        if tag=='IsWeaponLoaded':
            branch=node.find('Then' if self.loaded else 'Else')
            return (yield from self.sequence(branch,data)) if branch is not None else True
        if tag=='LoadWeaponAction':
            self.events.append(('load',self.held));self.loaded=True
            yield
            return True
        if tag=='HandContentElement':
            slot=0 if node.get('item').endswith('[0]') else 1
            self.held=node.get('hand'),data.setWeapons[slot]
            self.events.append(('draw',self.held))
            try:return (yield from self.sequence(node.find('Exec'),data))
            finally:self.events.append(('release',self.held));self.held=None
        if tag=='ExactMove':
            self.events.append(('align',self.held))
            yield
            return True
        return (yield from super().node(node,data))


class LeanRangedTests(unittest.TestCase):
    def setUp(self):patrol.LuaDirectorTests.setUp(self)

    def test_lean_with_standing_base_stance_cannot_take_fast_path(self):
        g=self.lua.globals()
        self.lua.execute('C.RequireStandingReset(a);assert(records[a:GetName()].needsStandingReset)')
        driver=MealBtDriver(self.lua,patrol.ROOT/'src/AI/nebakovrising_meal.xml',g.a,g.ta,blocked_standing=True)
        driver.stance='standing'  # The precise case that formerly bypassed unlean.
        driver.generator=driver.function('nebakovrising_stand',g.ta)
        for _ in range(10):
            self.lua.execute('clock=clock+0.1');next(driver.generator)
        self.assertTrue(self.lua.eval('C.NeedsStandingReset(a)'))
        self.assertEqual(self.lua.eval('C.activityRuns[tostring(a.this.id)].phase'),'standing')
        driver.generator.close()
        driver=MealBtDriver(self.lua,patrol.ROOT/'src/AI/nebakovrising_meal.xml',g.a,g.ta)
        driver.stance='standing';driver.generator=driver.function('nebakovrising_stand',g.ta)
        for _ in range(20):
            self.lua.execute('clock=clock+0.1')
            try:next(driver.generator)
            except StopIteration as result:
                self.assertTrue(result.value);break
        else:self.fail('Native standing acknowledgement did not finish')
        self.assertFalse(self.lua.eval('C.NeedsStandingReset(a)'))
        self.assertEqual(self.lua.eval('C.activityRuns[tostring(a.this.id)].phase'),'standing_ready')

    def test_recovery_survives_interrupted_activity_and_only_current_token_can_clear_it(self):
        self.lua.execute("C.RequireStandingReset(a);a._nebakovNeedsStandingReset=nil;assert(C.NeedsStandingReset(a));assert(not C.StandingConfirmed(a,ta+999));assert(C.NeedsStandingReset(a));C.FinishNpcActivity(a.this.id,ta);ta=begin(a,'patrol');assert(C.NeedsStandingReset(a));assert(C.StandingConfirmed(a,ta));assert(not C.NeedsStandingReset(a))")

    def test_existing_lean_link_forces_recovery_even_without_saved_marker(self):
        self.lua.execute("occupants[a.this.id]={'lean_point'};assert(C.NeedsStandingReset(a))")

    def weapon_scenario(self,left,right,loaded=False,kind='guard'):
        g=self.lua.globals();driver=WeaponDriver(self.lua,g.a,g.ta,left,right,loaded)
        root=ET.parse(patrol.ROOT/'src/AI/nebakovrising_patrol.xml').getroot()
        reset=next(n for n in root.iter('ExecuteLua') if 'data.hasHandgonne = false' in n.get('code',''))
        select=next(n for n in root.iter('IfCondition') if n.get('condition')=='$needCrossbow')
        choice=next(n for n in root.iter('IfElseCondition') if n.get('condition')=='$hasCrossbow')
        logic=ET.Element('Sequence')
        for n in [reset,select,choice]:logic.append(deepcopy(n))
        data=self.lua.table(activityToken=g.ta,needCrossbow=True,pointKind=kind,pointWuid='guard_spot',
                            pointPos=self.lua.table(x=3,y=0,z=0),waitSeconds=2,elapsed=0,patrolActive=True,
                            setWeapons=self.lua.table(),itemType='')
        driver.generator=driver.node(logic,data);held_samples=[]
        for _ in range(100):
            self.lua.execute('clock=clock+0.1;C.ActivityHeartbeat(a.this.id,ta)')
            try:next(driver.generator)
            except StopIteration as result:
                self.assertTrue(result.value);break
            if data.elapsed<2 and self.lua.eval('C.activityRuns[tostring(a.this.id)].phase')=='patrol_wait':
                held_samples.append(driver.held)
        else:self.fail('Guard wait did not finish')
        return driver,held_samples

    def test_handgonne_is_held_in_right_hand_throughout_guard_wait_without_loading(self):
        driver,samples=self.weapon_scenario(None,'gun')
        self.assertTrue(samples)
        self.assertTrue(all(s==('Right','gun') for s in samples))
        self.assertFalse(any(e[0]=='load' for e in driver.events))
        self.assertIsNone(driver.held)

    def test_crossbow_still_loads_once_and_is_held_in_left_hand(self):
        driver,samples=self.weapon_scenario('crossbow',None)
        self.assertTrue(samples)
        self.assertTrue(all(s==('Left','crossbow') for s in samples))
        self.assertEqual([e for e in driver.events if e[0]=='load'],[('load',('Left','crossbow'))])

    def test_loaded_crossbow_is_not_loaded_again(self):
        driver,_=self.weapon_scenario('crossbow',None,True)
        self.assertFalse(any(e[0]=='load' for e in driver.events))

    def test_handgonne_takes_precedence_without_loading_an_old_crossbow(self):
        driver,samples=self.weapon_scenario('crossbow','gun')
        self.assertTrue(samples)
        self.assertTrue(all(s==('Right','gun') for s in samples))
        self.assertFalse(any(e[0]=='load' for e in driver.events))

    def test_other_right_hand_weapon_is_not_treated_as_handgonne(self):
        driver,samples=self.weapon_scenario(None,'sword')
        self.assertTrue(samples)
        self.assertFalse(any(e[0]=='draw' for e in driver.events))

    def test_every_lean_entry_marks_recovery_before_starting_animation(self):
        root=ET.parse(patrol.ROOT/'src/AI/nebakovrising_patrol.xml').getroot()
        parents={child:p for p in root.iter() for child in p}
        for node in root.iter('UnstanceAction'):
            if node.get('unstance')!='LeaningBack':continue
            sequence=list(parents[node]);previous=sequence[sequence.index(node)-1]
            self.assertIn('RequireStandingReset',previous.get('code',''))


class ClosingPromptTests(unittest.TestCase):
    def test_all_context_profiles_request_a_topic_specific_final_fourth_line(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            root=ensure_defaults(temp)
            for behavior in ['patrol','meal','idle']:
                text=PromptProfiles(root/'prompts').prepare({'director':{'behavior':behavior,
                    'profile_id':behavior+'-daily-talk','context':{'guard_a_name':'Jan','guard_b_name':'Petr'}}})['text']
                self.assertIn('final (fourth) line',text)
                self.assertIn('tied to the current topic',text)
                self.assertIn('no unanswered question',text)
                self.assertIn('game controls their activity',text)

if __name__=='__main__':unittest.main()
