"""Execute the actual patrol sit/lean subtree while the other guard approaches."""
import unittest
import xml.etree.ElementTree as ET

import test_patrol_conversations as patrol
from nebakov_voice_defaults import DEFAULT_SETTINGS
from nebakov_voice_config import encode_settings


class ReceiverDriver(patrol.ConversationDriver):
    def node(self,node,data):
        if node.tag=='UnstanceAction' and node.get('unstance')=='LeaningBack':
            self.stance='lean'
            yield
            return True
        return (yield from super().node(node,data))


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        patrol.LuaDirectorTests.setUp(self)
        self.settings=dict(DEFAULT_SETTINGS)
        csv,profile=encode_settings(self.settings)
        self.assertTrue(self.lua.globals().nebakovrising.ConversationConfig.Apply(csv,profile))

    def tick(self,drivers):
        self.lua.execute('clock=clock+0.1;C.ActivityHeartbeat(a.this.id,ta);C.ActivityHeartbeat(b.this.id,tb);D.Receive("peer",D.peer.seq+1,"heartbeat_ready",B.session,"")')
        for d in drivers:
            try: next(d.generator)
            except StopIteration: self.fail('Patrol pose ended during conversation')

    def scenario(self,kind,crossbow=False):
        root=ET.parse(patrol.ROOT/'src/AI/nebakovrising_patrol.xml').getroot()
        nodes=list(root.iter('StanceElement')) if kind=='sit' else list(root.iter('AddLinkElement'))
        nodes=[n for n in nodes if (n.get('stance')=='sitting' if kind=='sit' else n.get('tag')=="'leaningObject'")]
        self.assertEqual(len(nodes),2)
        g=self.lua.globals()
        anchor=ReceiverDriver(self.lua,g.a,g.ta)
        data=self.lua.table(activityToken=g.ta,pointKind=kind,pointWuid='bench',elapsed=0,waitSeconds=1,patrolActive=True)
        anchor.generator=anchor.node(nodes[0 if crossbow else 1],data)
        for _ in range(15):
            self.tick([anchor])
            if self.lua.eval('C.activityRuns[tostring(a.this.id)].socialPose~=nil'):break
        self.assertEqual(self.lua.eval('C.activityRuns[tostring(a.this.id)].socialPose'),kind)
        self.lua.execute("assert(D.TryStart(true));assert(D.Receive('peer',D.peer.seq+1,'audio_ready',B.session,D.active.id));assert(D.active.participants[1].name==a:GetName());assert(D.ReceiverRequested(a.this.id,ta));assert(not D.HasRequest(a.this.id,ta))")
        mover=patrol.ConversationDriver(self.lua,g.b,g.tb)
        pose='sitting' if kind=='sit' else 'lean'
        initial_dir=(g.a.GetDirectionVector(g.a).x,g.a.GetDirectionVector(g.a).y)
        for _ in range(120):
            self.tick([anchor,mover]);self.assertEqual(anchor.stance,pose)
            if self.lua.eval('D.active.arrived==true'):break
        self.assertTrue(self.lua.eval('D.active.arrived==true'))
        # The original one-second wait has expired, but the receiver still owns
        # its exact stance/link and patrol token throughout the conversation.
        self.assertGreater(self.lua.eval('clock'),100+1)
        self.assertEqual(data.elapsed,0)
        self.assertFalse(any(e[0] in {'move','turn','turn_started'} for e in anchor.events))
        self.assertTrue(any(e[0]=='turn' for e in mover.events))
        self.assertEqual((g.a.GetDirectionVector(g.a).x,g.a.GetDirectionVector(g.a).y),initial_dir)
        self.lua.execute("assert(D.Receive('peer',D.peer.seq+1,'playing',B.session,D.active.id))")
        for i in range(1,5):
            self.lua.globals().line=i
            self.lua.execute("assert(D.Receive('peer',D.peer.seq+1,'line_start',B.session,D.active.id,line,1000))")
            self.tick([anchor,mover]);self.assertEqual(anchor.stance,pose)
            self.lua.execute("assert(D.Receive('peer',D.peer.seq+1,'line_end',B.session,D.active.id,line,0))")
        self.lua.execute("assert(D.Receive('peer',D.peer.seq+1,'finished',B.session,D.active.id));assert(C.activityRuns[tostring(a.this.id)].conversationId==nil);assert(C.OwnsNpcActivity(a.this.id,ta));assert(C.activityRuns[tostring(a.this.id)].socialPose~=nil)")
        self.assertEqual(anchor.stance,pose)
        self.assertEqual(len(g.a.faceStarts),2)

    def test_seated_receiver_keeps_patrol_stance_and_speaks(self): self.scenario('sit')
    def test_leaning_receiver_keeps_link_and_speaks(self): self.scenario('lean')
    def test_crossbow_seated_receiver_keeps_stance(self): self.scenario('sit',True)
    def test_crossbow_leaning_receiver_keeps_link(self): self.scenario('lean',True)

    def test_changed_pose_before_audio_commit_is_revalidated(self):
        self.lua.execute("D.SetPatrolPose(a,ta,'sit');assert(D.TryStart(true));D.SetPatrolPose(a,ta,'guard');assert(D.Receive('peer',D.peer.seq+1,'audio_ready',B.session,D.active.id));assert(not D.active.participants[1].preservePose);assert(D.HasRequest(a.this.id,ta))")

    def test_receiver_interruption_cancels_and_releases_social_reservation(self):
        self.lua.execute("D.SetPatrolPose(a,ta,'lean');assert(D.TryStart(true));assert(D.Receive('peer',D.peer.seq+1,'audio_ready',B.session,D.active.id));D.ActivityEnded(a.this.id,ta);assert(D.active==nil);assert(C.activityRuns[tostring(a.this.id)].conversationId==nil)")

    def test_posture_loss_or_combat_cancels_without_forcing_stand(self):
        for change,reason in [("D.SetPatrolPose(a,ta,nil)",'receiver_posture_changed'),('a.combat=true','participant_unavailable')]:
            self.setUp()
            self.lua.execute("D.SetPatrolPose(a,ta,'sit');assert(D.TryStart(true));assert(D.Receive('peer',D.peer.seq+1,'audio_ready',B.session,D.active.id));"+change+";assert(not D.CheckActive());assert(D.active==nil)")
            self.assertEqual(self.lua.eval('D.last.reason'),reason)

    def test_interval_starts_at_completion_without_additional_default_cooldowns(self):
        self.lua.execute("""
            nebakovrising.Config.conversations.randomMinSeconds=20
            nebakovrising.Config.conversations.randomMaxSeconds=50
            assert(nebakovrising.Config.conversations.cooldownSeconds==0)
            assert(nebakovrising.Config.conversations.npcCooldownSeconds==0)
            assert(D.TryStart(true));D.nextRandom=clock-10
            D.Finish('playback_finished',true)
            assert(D.nextRandom>=clock+20 and D.nextRandom<=clock+50)
            assert(D.nextAllowed==clock and D.cooldowns[a:GetName()]==clock)
            clock=D.nextRandom-0.1
            C.ActivityHeartbeat(a.this.id,ta);C.ActivityHeartbeat(b.this.id,tb)
            D.Receive('peer',D.peer.seq+1,'heartbeat_ready',B.session,'')
            local serial=D.attemptSerial;D.Tick({generation=D.generation});assert(D.attemptSerial==serial)
            clock=clock+0.2;D.Tick({generation=D.generation})
            assert(D.active~=nil and D.lastAttempt.started)
        """)


if __name__=='__main__':unittest.main()
