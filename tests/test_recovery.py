import unittest
from copy import deepcopy
from traffic.simulation import Simulation,Vehicle
from traffic.network import Network,Path
from traffic.prolog import PrologRules
from traffic.demand import ACCESS


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=PrologRules();cls.net=Network()

    def sim(self):
        s=Simulation(self.rules,network=self.net,mode='accident',clearance=1)
        s.reset(target=0)
        s.network.paths['clearance_test']=Path('clearance_test',[(0,0),(1000,0)])
        return s

    def test_clearance_members_only_idempotent_and_site_reused(self):
        s=self.sim()
        a,b=[Vehicle(i,('clearance_test',),x,0) for i,x in ((1,100),(2,104.4))]
        s.vehicles=[a,b];s.incidents.register(s,a,b)
        c=Vehicle(3,('clearance_test',),108.8,0)
        s.vehicles.append(c);s.elapsed=.5;s.incidents.register(s,b,c)
        self.assertEqual(c.incident,a.incident)
        self.assertEqual(s.incidents.records[0]['clear_at'],1.5)
        s.elapsed=1.6;s.incidents.clear(s);s.incidents.clear(s)
        self.assertEqual(len(s.removals),3)
        self.assertEqual(s.completed,0)
        history=deepcopy(s.incidents.records)
        for vid in range(4,8):
            v=Vehicle(vid,('clearance_test',),80,0,speed=6)
            s.vehicles=[v]
            for _ in range(400):s.step();s.incidents.clear(s)
            self.assertIn(v,s.vehicles)
            self.assertGreater(v.s,110)
            self.assertIsNone(v.incident)
        self.assertEqual(s.incidents.records,history)
        self.assertEqual(len(s.incidents.cells),1)
        self.assertFalse(s.incidents.active_ids)

    def test_wreck_at_route_end_cannot_be_completed(self):
        s=self.sim();a=Vehicle(1,('clearance_test',),1000,0)
        b=Vehicle(2,('clearance_test',),995.6,0)
        s.vehicles=[a,b];s.incidents.register(s,a,b)
        s.step();self.assertIn(a,s.vehicles);self.assertEqual(s.completed,0)
        s.elapsed=2;s.incidents.clear(s)
        self.assertEqual({r['reason'] for r in s.removals},{'crash_clearance'})

    def test_non_member_with_stale_incident_reference_is_not_removed(self):
        s=self.sim();a,b=[Vehicle(i,('clearance_test',),x,0) for i,x in ((1,100),(2,104.4))]
        s.vehicles=[a,b];s.incidents.register(s,a,b)
        c=Vehicle(3,('clearance_test',),20,0,incident=1)
        s.vehicles.append(c);s.elapsed=2;s.incidents.clear(s)
        self.assertEqual(s.vehicles,[c])

    def test_capacity_target_30_to_100_and_reversal(self):
        s=self.sim()
        # Seven independent, long entry corridors isolate admission capacity
        # from the compact city's signal/curb bottlenecks. No forced admissions.
        for i,a in enumerate(ACCESS.values()):
            s.network.paths[a.lane]=Path(a.lane,[(0,20*i),(2000,20*i)])
        original=s._make_vehicle
        def make(ticket):
            v=original(ticket)
            if v:v.route=(ACCESS[ticket.origin].lane,);v.end_s=1900
            return v
        s._make_vehicle=make
        for i in range(30):
            lane=list(ACCESS.values())[i%7].lane
            v=Vehicle(i+1,(lane,),100+(i//7)*20,0,speed=8,end_s=1900)
            s.vehicles.append(v)
        s.next_id=31;s.set_target(100)
        for _ in range(9000):
            s.step()
            self.assertLessEqual(len(s.vehicles)+len(s.queued),100)
            if len(s.vehicles)==100:break
        self.assertEqual(len(s.vehicles),100)
        self.assertFalse(s.incidents.records)
        s.set_target(20);self.assertFalse(s.queued)
        # Finish real trips at their explicitly declared destinations.
        for v in s.vehicles[:80]:v.end_s=v.s;v.speed=0
        s.step();self.assertEqual(len(s.vehicles),20)
        s.set_target(100)
        for _ in range(9000):
            s.step()
            if len(s.vehicles)==100:break
        self.assertEqual(len(s.vehicles),100)

    def test_blocked_entry_recovers_and_pause_reset(self):
        s=self.sim();a,b=[Vehicle(i,('clearance_test',),x,0) for i,x in ((1,14),(2,18.4))]
        s.vehicles=[a,b];s.incidents.register(s,a,b)
        candidate=Vehicle(3,('clearance_test',),14,0)
        s.queued.append(candidate);s.set_target(3);s._admit_demand()
        self.assertNotIn(candidate,s.vehicles)
        self.assertIn('Wreck',s.spawn_status)
        s.paused=True;s.advance(10);s.step()
        self.assertEqual(s.elapsed,0)
        s.paused=False;s.elapsed=2;s.incidents.clear(s)
        s.set_target(1);s._admit_demand()
        self.assertIn(candidate,s.vehicles)
        s.reset(target=0)
        self.assertFalse(s.queued or s.removals or s.incidents.active_ids)
        self.assertEqual(s.elapsed,0)


if __name__=='__main__':unittest.main()

