import unittest
from traffic.simulation import Simulation,Vehicle
from traffic.network import Network
from traffic.prolog import PrologRules
from traffic.supervisor import SafetySupervisor
from traffic.demand import GATES,route_between
from traffic import overtaking
import random


class CapacityFunnelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=PrologRules();cls.net=Network(gates=True,peripheral=True)

    def test_compact_centre_preserved_and_belt_connected(self):
        self.assertEqual(len(self.net.junctions),24)
        self.assertEqual(self.net.grid,(-96,-32,32,96))
        original=Network()
        for key,node in original.junctions.items():
            self.assertEqual(self.net.junctions[key].position,node.position)
        for key,path in original.lanes.items():
            if path.source in original.junctions and path.target in original.junctions:
                self.assertEqual(self.net.lanes[key].points,path.points)
        for name in GATES:
            route=route_between(self.net,name,'University',random.Random(42))
            self.assertEqual(route[0],self.net.access[name].lane)
            for a,b in zip(route,route[1:]):
                self.assertEqual(self.net.paths[a].points[-1],self.net.paths[b].points[0])

    def test_distant_reservation_not_whole_lane_spawn_veto(self):
        net=self.net;cp='01>02|02>12'
        a=Vehicle(1,(cp,'02>12'),0,0,speed=6,permit=cp)
        candidate=Vehicle(2,('02>12',),14,0)
        sup=SafetySupervisor()
        self.assertTrue(sup.spawn_clear(net,candidate,[a]))
        a.s=net.paths[cp].length-1;a.speed=12
        self.assertFalse(sup.spawn_clear(net,candidate,[a]))

    def test_ordinary_normal_reaches_100(self):
        from traffic.supervisor import rectangles_overlap
        from traffic.collisions import pairs
        s=Simulation(self.rules,network=self.net,mode='accident');s.set_target(100)
        for _ in range(36000):
            s.step()
            for i,j in pairs(s,[(v,v.s,0) for v in s.vehicles]):
                a,b=s.vehicles[i],s.vehicles[j]
                self.assertFalse(rectangles_overlap(s.pose(a),a.spec,s.pose(b),b.spec,margin=-.001))
            self.assertLessEqual(len(s.vehicles)+len(s.queued),100)
            if len(s.vehicles)==100:break
        self.assertEqual(len(s.vehicles),100)
        self.assertGreater(s.completed,0)
        self.assertFalse(s.incidents.records)
        self.assertEqual({v.driver.kind for v in s.vehicles},{'Normal'})

    def test_funnel_is_observational(self):
        s=Simulation(self.rules,network=self.net,scenario='Evening/night',mode='accident')
        v=next(v for v in s.vehicles if v.driver.kind=='Drunk')
        before=s.rng.getstate();traits=v.driver
        for _ in range(10):s.flow_audit.inspect(s,v)
        self.assertEqual(before,s.rng.getstate());self.assertIs(v.driver,traits)
        self.assertEqual(s.flow_audit.funnel['wrong_way/drunk_route_encounters'],1)

    def test_access_zone_is_local_and_mirrored(self):
        from traffic.demand import Access
        s=Simulation(self.rules,network=self.net,mode='accident')
        self.assertIsNone(overtaking.road_window(s,'rNW>rw',40))
        s.network.access={name:a for name,a in s.network.access.items() if a.lane not in ('rNW>rw','rw>rNW')}
        s.network.access['Test']=Access('Test','rNW>rw',14)
        self.assertIsNone(overtaking.road_window(s,'rNW>rw',14))
        self.assertEqual(overtaking.road_window(s,'rNW>rw',35),(28.,160.))
        self.assertEqual(overtaking.road_window(s,'rw>rNW',35),(0.,132.))
        self.assertIsNone(overtaking.road_window(s,'rw>rNW',146))
        self.assertIsNone(overtaking.road_window(s,'west>rw',20))

    def test_ordinary_night_selects_and_completes_overtake(self):
        s=Simulation(self.rules,network=self.net,mode='accident',scenario='Evening/night',seed=42)
        s.set_target(100)
        for _ in range(7200):
            s.step()
            if s.behaviour_audit.passing['completions']:break
        self.assertGreater(s.behaviour_audit.passing['attempts'],0)
        self.assertGreater(s.behaviour_audit.passing['completions'],0)

    def test_ordinary_night_executes_and_returns_wrong_way(self):
        s=Simulation(self.rules,network=self.net,mode='accident',scenario='Evening/night',seed=42)
        s.set_target(100)
        for _ in range(10800):
            s.step()
            self.assertTrue(all(overtaking.valid(s,v) for v in s.vehicles))
            if s.behaviour_audit.passing['wrong_way_returns']:break
        self.assertGreater(s.behaviour_audit.passing['wrong_way_episodes'],0)
        self.assertGreater(s.behaviour_audit.passing['wrong_way_returns'],0)


if __name__=='__main__':unittest.main()
