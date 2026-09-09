import math,random,unittest
from collections import deque
from shapely.geometry import Polygon
from shapely.prepared import prep
from traffic.four_lane import FourLaneNetwork
from traffic.prolog import PrologRules
from traffic.simulation import Simulation
from traffic.profiles import vehicle_spec
from traffic.night import counts
from traffic.road_surface import surface

class CorrectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.net=FourLaneNetwork();cls.rules=PrologRules()

    def test_curve_surface_and_long_vehicle_clearance(self):
        paved=surface(self.net);self.assertTrue(paved.is_valid);prepared=prep(paved.buffer(.03))
        for p in self.net.connectors.values():
            for kind in ('Sedan','Truck','Bus'):
                spec=vehicle_spec(kind)
                for i in range(21):
                    x,z,yaw=p.pose(p.length*i/20);a=math.radians(yaw);f=(math.sin(a),math.cos(a));r=(f[1],-f[0])
                    poly=Polygon([(x+f[0]*a*spec.length/2+r[0]*b*spec.width/2,z+f[1]*a*spec.length/2+r[1]*b*spec.width/2) for a,b in ((-1,-1),(-1,1),(1,1),(1,-1))])
                    self.assertTrue(prepared.covers(poly),(p.id,kind,i))

    def test_bends_keep_both_lanes(self):
        for j in self.net.junctions.values():
            if not j.bend:continue
            for road in self.net.roads:
                if self.net.roads[road]['target']!=j.id:continue
                for lane in ('inner','outer'):
                    pid=self.net.segments[road,lane][-1]
                    self.assertTrue(any(q in self.net.connectors and self.net.paths[self.net.paths[q].outgoing].lane==lane for q in self.net.successors[pid]))

    def test_quota_counts_wrecks_separately_and_queues_loss(self):
        s=Simulation(self.rules,network=self.net,scenario='Evening/night',mode='accident')
        self.assertEqual(counts(s)['active'],20)
        actors=[v for v in s.vehicles if v.driver.kind=='Drunk'];traits=[v.driver for v in s.vehicles]
        actors[0].crashed=True;s._admit_demand()
        q=counts(s);self.assertEqual(q['active'],19);self.assertEqual(q['wrecks'],1);self.assertGreaterEqual(q['pending'],1)
        self.assertEqual(len(s.vehicles),40);self.assertEqual(traits,[v.driver for v in s.vehicles]);self.assertTrue(q['blocker'])
        s.set_target(10);self.assertEqual(counts(s)['target'],10)

    def test_unsafe_signal_and_roundabout_entry_can_contact(self):
        from traffic.junction_fixture import conflict
        for kind in ('signal','roundabout'):
            result=conflict(self.net,self.rules,kind)
            self.assertTrue(result['incidents'])
            self.assertTrue(any(e['unsafe'] for e in result['junction_events']))

    def test_dynamic_change_contact_prediction_has_no_handoff_jump(self):
        from traffic.network import Path
        from traffic.simulation import Vehicle
        from traffic.collisions import breaks
        s=Simulation(self.rules,network=self.net);s.reset(target=0)
        pid=s.network.segments['rNW>rw','outer'][-1];p=s.network.paths[pid]
        q=Path('ot:test',[(0,0),p.pose(12)[:2]],'lane_change');q.resume_s=12
        s.network.paths[q.id]=q
        v=Vehicle(1,(q.id,pid),q.length-.01,0)
        self.assertLess(math.dist(s.future_pose(v,q.length-.0001)[:2],s.future_pose(v,q.length+.0001)[:2]),.001)
        self.assertIn(.5,{round(t,5) for t in breaks(s,v,.02)})

if __name__=='__main__':unittest.main()
