import unittest

from traffic.signals import Signals, PHASES
from traffic.prolog import PrologRules
from traffic.simulation import Simulation, Vehicle
from traffic.network import Network
from traffic.demand import ACCESS
from traffic.verification import overlap
from traffic.simulation import STOP_MARGIN
import random
import math


class SignalTests(unittest.TestCase):
    def test_order_and_exclusion(self):
        s = Signals()
        observed = []
        for _ in range(12):
            observed.append(s.phase)
            self.assertFalse(s.light('N') == s.light('E') == 'green')
            self.assertEqual(s.light('N'), s.light('S'))
            self.assertEqual(s.light('E'), s.light('W'))
            s.step(s.remaining)
        self.assertEqual(observed, list(PHASES) * 2)

    def test_pending_boundary(self):
        s = Signals()
        s.step(12)
        s.request(5)
        self.assertEqual(s.remaining, 18)
        s.step(18)
        self.assertEqual(s.active_green, 30)
        s.step(3)
        self.assertEqual(s.active_green, 30)
        s.step(1)
        self.assertEqual(s.phase, 'EW green')
        self.assertEqual(s.remaining, 5)
        s.request(120)
        s.step(9)
        self.assertEqual(s.phase, 'NS green')
        self.assertEqual(s.remaining, 120)


class PrologTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = PrologRules()

    def test_decisions(self):
        cases = [
            (('red', False, True, True, True), ('stop', 'red_signal')),
            (('green', False, True, True, True), ('proceed', 'green_and_clear')),
            (('green', False, True, False, True), ('wait', 'exit_blocked')),
            (('green', False, True, True, False), ('brake', 'vehicle_ahead')),
            (('red', True, False, False, True), ('proceed', 'clear_intersection')),
            (('amber', False, True, True, True), ('stop', 'amber_safe_stop')),
            (('amber', False, False, True, True), ('proceed', 'amber_committed')),
            (('red', True, False, True, False), ('brake', 'vehicle_ahead')),
        ]
        for observation, expected in cases:
            with self.subTest(observation=observation):
                self.assertEqual(self.rules.decide(*observation), expected)


class CityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.network = Network()
        cls.rules = PrologRules()

    def sim(self):
        return Simulation(self.rules, network=self.network)

    def car(self, id, connector):
        p = self.network.connectors[connector]
        return Vehicle(id, (p.incoming,p.id,p.outgoing), self.network.paths[p.incoming].length-STOP_MARGIN-1, 0)

    def snapshot(self, sim):
        return [(v,v.path_id,v.s) for v in sim.vehicles]

    def test_routes_and_connections(self):
        net=self.network
        self.assertEqual(len(net.junctions),16)
        self.assertEqual(sum(j.kind == 'roundabout' for j in net.junctions.values()),2)
        self.assertEqual(len(net.junctions['00'].approaches),2)
        rng=random.Random(42)
        for source in net.portals:
            for destination in net.portals:
                if source == destination:
                    continue
                route=net.route(source,destination,rng)
                self.assertEqual(net.paths[route[0]].source,source)
                self.assertEqual(net.paths[route[-1]].target,destination)
                for a,b in zip(route,route[1:]):
                    self.assertLess(math.dist(net.paths[a].points[-1],net.paths[b].points[0]),1e-8)
                for pid in route[1::2]:
                    p=net.paths[pid]
                    self.assertNotEqual(net.paths[p.incoming].source,net.paths[p.outgoing].target)
        for p in net.connectors.values():
            a,b=net.paths[p.incoming],net.paths[p.outgoing]
            for x,y in ((a.pose(a.length)[2],p.pose(0)[2]),(p.pose(p.length)[2],b.pose(0)[2])):
                self.assertLess(abs((x-y+180)%360-180),6)

    def test_left_yields_to_oncoming(self):
        sim=self.sim()
        # At 13, north->south turns left to east; through traffic arrives south.
        left=self.car(1,'north>13|13>23')
        through=self.car(2,'12>13|13>north')
        sim.vehicles=[left,through]
        sim._decide(self.snapshot(sim))
        self.assertEqual(left.reason,'oncoming_traffic')
        self.assertIsNone(left.permit)
        self.assertIsNotNone(through.permit)

    def test_old_stopped_left_queue_receives_safe_gap(self):
        sim=self.sim()
        left=self.car(1,'north>13|13>23')
        through=self.car(2,'12>13|13>north')
        left.waiting=75
        sim.vehicles=[left,through]
        sim._decide(self.snapshot(sim))
        self.assertIsNotNone(left.permit)
        self.assertIsNone(through.permit)
        left.permit=None
        through.speed=4
        sim._decide(self.snapshot(sim))
        self.assertIsNone(left.permit)
        self.assertEqual(left.reason,'oncoming_traffic')

    def test_roundabout_yield_and_simultaneous_paths(self):
        sim=self.sim()
        paths=[p for p in self.network.connectors.values() if p.junction == '11']
        a,b=next((a,b) for a in paths for b in paths if b.id not in self.network.conflicts[a.id])
        va,vb=self.car(1,a.id),self.car(2,b.id)
        sim.vehicles=[va,vb]
        sim._decide(self.snapshot(sim))
        self.assertIsNotNone(va.permit)
        self.assertIsNotNone(vb.permit)
        # A third crossing request yields to the reserved circulating arc.
        c=next(p for p in paths if p.incoming not in (a.incoming,b.incoming) and a.id in self.network.conflicts[p.id])
        va.index,va.s=1,8
        vc=self.car(3,c.id)
        sim.vehicles=[va,vc]
        sim._decide(self.snapshot(sim))
        self.assertEqual(vc.reason,'yielding_to_circulating_vehicle')
        self.assertIsNone(vc.permit)
        # The ring part itself must progress CCW and stay outside the island.
        for p in paths:
            cx,cz=self.network.junctions['11'].position
            points=[(x-cx,z-cz) for x,z in p.points]
            self.assertGreater(min(math.hypot(x,z) for x,z in points),9.7)
            ring=[(x,z) for x,z in points if abs(math.hypot(x,z)-10)<1e-6]
            for u,v in zip(ring,ring[1:]):
                self.assertGreater(u[0]*v[1]-u[1]*v[0],0)

    def test_blocked_exit_and_commitment(self):
        sim=self.sim()
        v=self.car(1,'12>13|13>north')
        blocker=Vehicle(2,('13>north',),2,1)
        sim.vehicles=[v,blocker]
        sim._decide(self.snapshot(sim))
        self.assertEqual(v.reason,'exit_blocked')
        self.assertIsNone(v.permit)
        v.permit=v.route[1]
        sim._decide(self.snapshot(sim))
        self.assertEqual(v.reason,'clear_intersection')

    def test_global_local_boundaries(self):
        sim=self.sim()
        sim.set_local('12',15)
        sim.set_global(90)
        self.assertEqual(sim.signals['12'].requested_green,15)
        self.assertEqual(sim.signals['00'].requested_green,90)
        self.assertTrue(all(s.active_green == 30 for s in sim.signals.values()))
        for s in sim.signals.values():
            s.step(34)
        self.assertEqual(sim.signals['12'].active_green,15)
        self.assertEqual(sim.signals['00'].active_green,90)
        sim.set_local('12')
        self.assertEqual(sim.signals['12'].active_green,15)
        self.assertEqual(sim.signals['12'].requested_green,90)
        with self.assertRaises(KeyError):
            sim.set_local('11',15)

    def test_spawn_and_gradual_reduction(self):
        sim=self.sim()
        v=sim.vehicles[0]
        self.assertFalse(sim._spawn(v.path_id,v.s))
        sim.set_target(0)
        self.assertEqual(len(sim.vehicles),40)
        previous=40
        for _ in range(60*600):
            sim.step()
            self.assertLessEqual(len(sim.vehicles),previous)
            previous=len(sim.vehicles)
            if not previous:
                break
        self.assertEqual(len(sim.vehicles),0)
        self.assertEqual(sim.completed,40)
        sim.set_target(100)
        self.assertEqual(sim.pending,100)
        for _ in range(12):
            sim.step()
        self.assertGreater(len(sim.vehicles),0)
        self.assertLessEqual(len(sim.vehicles),7)
        poses=[sim.pose(v) for v in sim.vehicles]
        self.assertFalse(any(overlap(a,b) for i,a in enumerate(poses) for b in poses[i+1:]))

    def test_pause_reset_frame_independence(self):
        a,b=self.sim(),self.sim()
        for v in a.vehicles:
            self.assertEqual(v.route[0],ACCESS[v.origin].lane)
            self.assertEqual(v.route[-1],ACCESS[v.destination].lane)
        for _ in range(120):
            a.advance(1/30)
        for _ in range(576):
            b.advance(1/144)
        self.assertEqual(a.vehicles,b.vehicles)
        a.paused=True
        snapshot=repr((a.vehicles,a.signals,a.elapsed))
        a.advance(10)
        self.assertEqual(snapshot,repr((a.vehicles,a.signals,a.elapsed)))
        a.set_global(100)
        a.set_local('12',5)
        a.set_target(0)
        a.reset()
        self.assertEqual(a.vehicles,self.sim().vehicles)
        self.assertEqual((a.target,a.global_green,a.completed,a.elapsed),(40,30,0,0))
        self.assertTrue(all(s.override is None for s in a.signals.values()))


if __name__ == '__main__':
    unittest.main()

