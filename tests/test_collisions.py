import math
import unittest
from types import SimpleNamespace
from traffic.collisions import movement,contact
from traffic.incidents import Incidents,Metrics
from traffic.network import Path,Network
from traffic.simulation import Vehicle,Simulation,STEP
from traffic.profiles import vehicle_spec
from traffic.prolog import PrologRules
from traffic.supervisor import rectangles_overlap


def fixture():
    paths={
        'east':Path('east',[(-100,0),(100,0)]),
        'north':Path('north',[(0,-100),(0,100)]),
        'near':Path('near',[(-100,3),(100,3)]),
        'far':Path('far',[(-100,12),(100,12)]),
        'bend':Path('bend',[(-100,0),(0,0),(0,100)]),
    }
    sim=SimpleNamespace(network=SimpleNamespace(paths=paths),elapsed=0.,incidents=Incidents(2),vehicles=[])
    sim.future_pose=lambda v,s:Simulation.future_pose(sim,v,s)
    sim.pose=lambda v:paths[v.path_id].pose(v.s)
    return sim


def car(i,path,s,kind='Sedan'):
    return Vehicle(i,(path,),s,0,spec=vehicle_spec(kind),speed=10.)


def commit(sim,updates):
    result=movement(sim,updates)
    for v,s,speed in result: v.s,v.speed=s,speed
    return result


class ContactTests(unittest.TestCase):
    def test_crossing_swept_fast_no_tunnelling(self):
        s=fixture(); a,b=car(1,'east',70),car(2,'north',70)
        s.vehicles=[a,b]
        commit(s,[(a,130,1000),(b,130,1000)])
        self.assertTrue(a.crashed and b.crashed)
        self.assertAlmostEqual(a.s,96.9,places=6)
        self.assertFalse(rectangles_overlap(s.pose(a),a.spec,s.pose(b),b.spec,margin=-1e-6))
        self.assertEqual(len(s.incidents.records),1)

    def test_rear_end_long_vehicle(self):
        for kind in ('Sedan','Truck','Bus'):
            s=fixture(); a,b=car(1,'east',60),car(2,'east',90,kind)
            commit(s,[(a,130,100),(b,90,0)])
            self.assertAlmostEqual(b.s-a.s,(a.spec.length+b.spec.length)/2,places=6)
            self.assertTrue(a.crashed and b.crashed)

    def test_near_miss_and_close_following(self):
        s=fixture(); a,b=car(1,'east',70),car(2,'near',80)
        commit(s,[(a,130,100),(b,130,90)])
        self.assertFalse(a.crashed or b.crashed)
        b=car(3,'east',a.s+4.41)
        self.assertIsNone(contact(s,a,0,b,0))

    def test_polyline_turn_breaks(self):
        s=fixture(); a,b=car(1,'bend',60),car(2,'north',125)
        commit(s,[(a,160,500),(b,125,0)])
        self.assertTrue(a.crashed)
        self.assertLess(a.s,125)

    def test_persistent_pileup_separate_nearby(self):
        s=fixture(); a,b=car(1,'east',80),car(2,'east',90)
        s.vehicles=[a,b]
        commit(s,[(a,100,100),(b,90,0)])
        for _ in range(10): commit(s,[(a,a.s,0),(b,b.s,0)])
        self.assertEqual(len(s.incidents.records),1)
        c=car(3,'east',70);s.vehicles.append(c);s.elapsed=1
        commit(s,[(a,a.s,0),(b,b.s,0),(c,100,100)])
        self.assertEqual(c.incident,a.incident)
        self.assertEqual(len(s.incidents.involved),3)
        d,e=car(4,'far',80),car(5,'far',90)
        s.vehicles.extend([d,e])
        commit(s,[(d,100,100),(e,90,0)])
        self.assertEqual(len(s.incidents.records),2)
        self.assertEqual(sum(s.incidents.cells.values()),2)
        s.elapsed=2;s.incidents.clear(s)
        self.assertEqual(len(s.vehicles),5) # Last contact extended clearance to t=3.
        s.elapsed=3;s.incidents.clear(s)
        self.assertFalse(s.vehicles)
        self.assertEqual(sum(s.incidents.cells.values()),2)

    def test_simultaneous_component_independent_of_pair_order(self):
        s=fixture()
        a,b,c,d=[car(i,'east',p) for i,p in enumerate((60,70,80,90),1)]
        # Array order would enumerate A-B and D-C before the connecting B-C edge.
        commit(s,[(a,80,100),(b,84.4,100),(d,93.2,100),(c,88.8,100)])
        self.assertEqual(len(s.incidents.records),1)
        self.assertEqual(len(s.incidents.involved),4)
        self.assertEqual({v.incident for v in (a,b,c,d)},{1})

    def test_usage_once_and_zero_exposure(self):
        s=fixture(); s.metrics=Metrics(); s.target=0;s.completed=0
        self.assertIsNone(s.metrics.values(s)['accidents_per_1000_vehicle_km'])
        a=car(1,'east',20)
        for _ in range(100):s.metrics.enter(a,s.network)
        self.assertEqual(s.metrics.usage['east'],1)
        a.route=('east','east');a.index=1;s.metrics.enter(a,s.network)
        self.assertEqual(s.metrics.usage['east'],2)
        s.metrics.distance=1000
        self.assertEqual(s.metrics.values(s)['accidents_per_1000_vehicle_km'],0)


class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules=PrologRules();cls.net=Network()

    def test_wreck_queue_pause_clearance_reset(self):
        s=Simulation(self.rules,network=self.net,mode='accident',clearance=2)
        s.reset(target=0)
        lane=next(p for p in s.network.lanes.values() if p.length>28)
        a,b,c=(Vehicle(i,(lane.id,),pos,0) for i,pos in ((1,20),(2,24.4),(3,10)))
        s.vehicles=[a,b,c]
        s.incidents.register(s,a,b)
        s.paused=True;s.advance(10);s.step()
        self.assertEqual(s.elapsed,0);self.assertEqual(len(s.vehicles),3)
        s.paused=False
        for _ in range(119):s.step()
        self.assertEqual(len(s.vehicles),3)
        self.assertFalse(c.crashed)
        self.assertLess(c.s,a.s-4.4)
        for _ in range(3):s.step()
        self.assertEqual(s.vehicles,[c])
        self.assertEqual(s.incidents.active,0)
        old=c.s
        for _ in range(60):s.step()
        self.assertGreater(c.s,old)
        s.reset(target=0)
        self.assertFalse(s.incidents.records or s.metrics.usage)
        self.assertEqual(s.metrics.distance,0)

    def test_explicit_risk_can_enter_conflict_but_normal_cannot(self):
        # Controlled Prolog output isolates mode policy from episode sampling.
        s=Simulation(self.rules,network=self.net,mode='accident')
        s.reset(target=0)
        cp=next(p for p in s.network.connectors.values() if p.kind=='signal')
        a=Vehicle(1,(cp.incoming,cp.id,cp.outgoing),s.network.paths[cp.incoming].length-2.7,0)
        b=Vehicle(2,(cp.id,cp.outgoing),2,0,permit=cp.id)
        s.vehicles=[a,b]
        def propose(v,*args):v.action='proceed';v.reason='unsafe_gap_accepted'
        s._proposal=propose
        s._decide([(v,v.path_id,v.s) for v in s.vehicles])
        self.assertEqual(a.permit,cp.id)
        a.permit=None;s.mode='supervised'
        s._decide([(v,v.path_id,v.s) for v in s.vehicles])
        self.assertIsNone(a.permit)

    def test_accident_mode_spawn_still_rejects_wreck(self):
        s=Simulation(self.rules,network=self.net,mode='accident')
        s.reset(target=0)
        lane=next(iter(s.network.lanes))
        wreck=Vehicle(1,(lane,),10,0,crashed=True,incident=1,spec=vehicle_spec('Bus'))
        candidate=Vehicle(2,(lane,),14,0)
        self.assertFalse(s.supervisor.spawn_clear(s.network,candidate,[wreck]))


if __name__=='__main__':unittest.main()
