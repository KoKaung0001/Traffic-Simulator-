import math,random,unittest
from traffic.four_lane import FourLaneNetwork
from traffic.simulation import Simulation,Vehicle,STEP
from traffic.prolog import PrologRules
from traffic.profiles import vehicle_spec,Driver
from traffic import lane_changes as lc
from traffic.four_wrong_way import install,valid
from traffic.collisions import contact,movement
from traffic.heatmaps import level
from traffic.incidents import Metrics


class FourLaneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.net=FourLaneNetwork();cls.rules=PrologRules()

    def sim(self):
        s=Simulation(self.rules,network=self.net,mode='accident');s.vehicles=[];s.queued.clear();s.target=0
        return s

    def actor(self,s,pid,position=0,speed=6,kind='Sedan'):
        v=Vehicle(len(s.vehicles)+1,(pid,),position,0,speed=speed,spec=vehicle_spec(kind),behaviour_rng=random.Random(42))
        s.vehicles.append(v);return v

    def test_compact_four_lane_and_connected_routes(self):
        n=self.net;self.assertEqual(n.grid,(-96,-32,32,96));self.assertEqual(n.road_width,14)
        for road in n.roads:
            self.assertIn((road,'inner'),n.segments);self.assertIn((road,'outer'),n.segments)
        for a,successors in n.successors.items():
            for b in successors:self.assertLess(math.dist(n.paths[a].points[-1],n.paths[b].points[0]),1e-8)
        for origin,a in n.access.items():
            if origin.endswith('exit'):continue
            for destination,b in n.access.items():
                if destination.endswith('gate'):continue
                if a.lane==b.lane:continue
                route=n.trip_route(origin,destination,random.Random(1))
                self.assertEqual(route[0],a.lane);self.assertEqual(route[-1],b.lane)

    def test_movement_policy_and_conflicts(self):
        n=self.net
        for p in n.connectors.values():
            a,b=n.paths[p.incoming],n.paths[p.outgoing]
            if p.turn=='left':self.assertEqual(a.lane,'inner')
            if p.turn=='right':self.assertEqual(a.lane,'outer')
            if p.kind=='signal' and p.turn=='straight':self.assertEqual(a.lane,b.lane)
            if p.kind=='signal' and p.turn=='right':self.assertEqual(b.lane,'outer')
            self.assertIn(p.id,n.conflicts[p.id])
            for q in n.conflicts[p.id]:self.assertIn(p.id,n.conflicts[q])

    def test_long_vehicle_envelopes_and_taper_continuity(self):
        s=self.sim();n=s.network
        for kind in ('Sedan','Truck','Bus'):
            spec=vehicle_spec(kind);self.assertTrue(n.supports(tuple(n.paths),spec))
            for p in n.paths.values():
                if not hasattr(p,'road'):continue
                v=Vehicle(1,(p.id,),0,0,spec=spec)
                for i in range(41):
                    v.s=p.length*i/40;self.assertTrue(valid(s,v),(kind,p.id,v.s))
        for road,r in n.roads.items():
            if r['merge']:self.assertEqual(n.point(road,r['length'],'inner'),n.point(road,r['length'],'outer'))
            if r['split']:self.assertEqual(n.point(road,0,'inner'),n.point(road,0,'outer'))

    def test_relative_speed_rear_gap_and_both_lane_occupancy(self):
        s=self.sim();n=s.network;pid=next(iter(n.change_links.values()));p=n.paths[pid]
        v=self.actor(s,pid,p.length/2,5);road,_,pos=lc.coordinate(s,v)
        rear_pid,rs=n.locate(road,p.lane,pos-14);rear=self.actor(s,rear_pid,rs,15)
        lc.build_index(s);self.assertEqual(len(lc.occupants(s,v)),2)
        self.assertFalse(lc.target_gaps(s,v,road,p.lane,pos)[0])
        rear.speed=2;self.assertTrue(lc.target_gaps(s,v,road,p.lane,pos)[0])
        s.vehicles.remove(rear);lc.build_index(s)
        self.assertTrue(lc.target_gaps(s,v,road,p.lane,pos)[0])

    def test_competing_changes_have_one_owner(self):
        s=self.sim();n=s.network
        pid=next(pid for pid in n.change_links.values() if not lc.protected(s,n.paths[pid]));p=n.paths[pid]
        other=n.paths[n.change_links[p.road,p.lane]]
        for cp in (p,other):
            v=self.actor(s,cp.incoming,n.paths[cp.incoming].length-8,3)
            v.route=(cp.incoming,cp.id,cp.outgoing);v.destination=next(iter(n.access))
        lc.build_index(s);lc.decide_all(s)
        self.assertLessEqual(sum(v.change_grant is not None for v in s.vehicles),1)
        for v in s.vehicles:v.s-=30
        s.vehicles[0].change_grant=pid;s.vehicles[0].lane_change=dict(kind='planned',risky=False,token=())
        lc.build_index(s);lc.decide_all(s)
        self.assertIsNone(s.vehicles[1].change_grant)

    def test_lane_change_full_sweep_can_contact(self):
        s=self.sim();n=s.network;pid=next(iter(n.change_links.values()));p=n.paths[pid]
        v=self.actor(s,pid,0,10)
        target=n.segments[p.road,p.lane][1];w=self.actor(s,target,n.paths[target].length*.6,0)
        self.assertIsNotNone(contact(s,v,p.length,w,0))
        movement(s,[(v,p.length,10),(w,w.s,0)])
        self.assertTrue(v.crashed and w.crashed);self.assertEqual(len(s.incidents.records),1)

    def test_roundabout_merge_owner_and_clearance(self):
        s=self.sim();n=s.network;road=next(k for k,r in n.roads.items() if r['merge']);r=n.roads[road]
        a=self.actor(s,n.segments[road,'inner'][0],1,3)
        b=self.actor(s,n.segments[road,'outer'][0],0,3)
        self.assertTrue(math.isinf(lc.merge_limit(s,a)));self.assertTrue(math.isfinite(lc.merge_limit(s,b)))
        s.vehicles.remove(a);self.assertTrue(math.isinf(lc.merge_limit(s,b)))

    def test_roundabout_departure_sees_other_destination_lane_queue(self):
        s=self.sim();n=s.network;road='22>32'
        inner=n.segments[road,'inner'][0];outer=n.segments[road,'outer'][0]
        lead=self.actor(s,inner,5,0)
        cp=next(p for p in n.connectors.values() if p.outgoing==outer)
        follower=self.actor(s,cp.id,cp.length-1,6);follower.route=(cp.id,outer)
        lc.build_index(s)
        self.assertLess(lc.following_gap(s,follower,[]),2)
        self.assertTrue(math.isfinite(lc.following_gap(s,follower,[],preferred=False)))

    def test_wrong_way_crossing_continuity_and_contact(self):
        s=self.sim();n=s.network
        road=next(k for k,r in n.roads.items() if r['length']>=150 and not r['merge'] and not r['split'])
        pid=n.segments[road,'inner'][-1];v=self.actor(s,pid,0,6)
        before=s.pose(v);v.manoeuvre=dict(road=road,route=v.route,limit=n.roads[road]['length']-8)
        self.assertTrue(install(s,v));self.assertLess(math.dist(before[:2],s.pose(v)[:2]),1e-8)
        p=n.paths[v.path_id]
        for i in range(101):v.s=p.length*i/100;self.assertTrue(valid(s,v))
        v.s=0
        opposite='>'.join(reversed(road.split('>')));op=n.references[opposite,'inner']
        point=p.pose(v.manoeuvre['shift_end']+6)
        distance=min(range(math.floor(op.length)),key=lambda t:math.dist(op.pose(t)[:2],point[:2]))
        other_pid,local=n.locate(opposite,'inner',distance);w=self.actor(s,other_pid,local,0)
        self.assertIsNotNone(contact(s,v,p.length,w,0))

    def test_heat_counts_and_fixed_colour_progression(self):
        n=self.net;pid=next(iter(n.lanes));v=Vehicle(1,(pid,)*60,0,0);m=Metrics()
        for i in range(50):
            v.index=i;m.enter(v,n);m.enter(v,n)
        self.assertEqual(m.usage[pid],50)
        self.assertEqual([level(x,'Road usage',1) for x in (0,1,25,50)],[0,1,2,3])
        self.assertEqual([level(x,'Accidents',1) for x in (0,1,3,5)],[0,1,2,3])
        self.assertEqual(level(50,'Road usage',2),2);self.assertEqual(m.usage[pid],50)

    def test_interpolation_observational_and_wraps_heading(self):
        s=self.sim();pid=next(iter(s.network.lanes));v=self.actor(s,pid,5)
        current=s.pose(v);s.previous_poses[v.id]=(current[0]-1,current[1]-2,current[2]+359)
        s.accumulator=STEP/2;before=(v.s,s.rng.getstate(),s.elapsed)
        visual=s.visual_pose(v);self.assertAlmostEqual(visual[0],current[0]-.5)
        self.assertAlmostEqual((visual[2]-current[2]+180)%360-180,-.5)
        self.assertEqual(before,(v.s,s.rng.getstate(),s.elapsed))

    def test_entry_backlog_independent_from_active_deficit(self):
        s=self.sim();s.target=1
        original=s.supervisor.spawn_reason
        s.supervisor.spawn_reason=lambda net,v,others:'Occupied entry'
        s._admit_demand()
        self.assertGreater(len(s.queued),s.pending);self.assertEqual(len(s.vehicles),0)
        waiting={v.id:v.driver for v in s.queued}
        s.supervisor.spawn_reason=original;s._admit_demand()
        self.assertEqual(len(s.vehicles),1);self.assertEqual(s.pending,0)
        self.assertGreater(len(s.queued),0)
        for v in s.queued:self.assertIs(v.driver,waiting[v.id])

    def test_steady_following_and_delayed_braking_on_real_lane(self):
        from dataclasses import replace
        from collections import deque
        for impaired in (False,True):
            s=self.sim();n=s.network
            pid=next(p.id for p in n.lanes.values() if p.part=='entry' and p.length>60 and not p.merge and not p.split)
            a=self.actor(s,pid,5,8);b=self.actor(s,pid,18,0)
            b.spec=replace(b.spec,cruise=0)
            if impaired:
                a.driver=Driver(kind='Drunk',subgroup='higher_risk',reaction=1.5,braking=.55,gap=1.,speed_factor=1.2)
                a.next_behaviour=100;a.perception=deque([(-2.,0,50.,0.,None)])
            for _ in range(150):s.step()
            self.assertEqual(bool(s.incidents.records),impaired)
            if impaired:
                record=s.incidents.records[0]
                self.assertTrue(record['vehicles'][a.id]['pre_history'])
                s.elapsed=record['clear_at'];s.incidents.clear(s)
                self.assertEqual(s.vehicles,[]);self.assertEqual(s.incidents.active,0)

    def test_normal_passing_physically_clears_slow_leader(self):
        from dataclasses import replace
        s=self.sim();n=s.network
        cp=next(n.paths[pid] for (road,lane),pid in n.change_links.items()
                if lane=='outer' and n.roads[road]['length']>=150 and not lc.protected(s,n.paths[pid]))
        a=self.actor(s,cp.incoming,n.paths[cp.incoming].length-10,6)
        zone=n.segments[cp.road,'outer'][1];b=self.actor(s,zone,3,2)
        b.spec=replace(b.spec,cruise=2)
        b.route=(zone,cp.incoming.replace(':entry',':exit'))
        a.route=tuple(n.segments[cp.road,'outer'])
        a.destination='East exit';a.opportunities={}
        for _ in range(1200):s.step()
        self.assertGreater(s.lane_counts['overtaking/completion'],0)
        self.assertFalse(s.incidents.records)

    def test_normal_return_and_bus_reroute_preserves_stops(self):
        s=self.sim();n=s.network
        cp=next(n.paths[pid] for (road,lane),pid in n.change_links.items() if lane=='inner' and not lc.protected(s,n.paths[pid]))
        a=self.actor(s,cp.incoming,n.paths[cp.incoming].length-8,4)
        a.route=tuple(n.segments[cp.road,'inner']);a.destination='East exit'
        for _ in range(600):s.step()
        self.assertEqual(s.lane_counts['return/attempt'],1)
        self.assertEqual(s.lane_counts['return/completion'],1)
        self.assertFalse(s.incidents.records)
        s=self.sim();n=s.network
        bus=self.actor(s,n.bus_route[0],0,0,'Bus');bus.route=n.bus_route;bus.destination='Terminal'
        next_stop=next(i for i in range(1,len(bus.route)) if bus.route[i] in n.bus_stops)
        suffix=bus.route[next_stop:]
        self.assertTrue(lc.reroute(s,bus));self.assertEqual(bus.route[-len(suffix):],suffix)

    def test_wrong_way_return_is_continuous(self):
        s=self.sim();n=s.network
        road=next(k for k,r in n.roads.items() if r['length']>=150 and not r['merge'] and not r['split'])
        pid=n.segments[road,'inner'][-1];v=self.actor(s,pid,0,3)
        v.manoeuvre=dict(road=road,route=v.route,limit=n.roads[road]['length']-8)
        self.assertTrue(install(s,v));v.s=v.manoeuvre['shift_end']+3;before=s.pose(v)
        self.assertTrue(install(s,v,True));self.assertLess(math.dist(before[:2],s.pose(v)[:2]),1e-8)
        p=n.paths[v.path_id]
        for i in range(101):v.s=p.length*i/100;self.assertTrue(valid(s,v))
        self.assertLess(math.dist(p.points[-1],n.paths[pid].points[-1]),1e-8)


if __name__=='__main__':unittest.main()
