import math
import random
import unittest
from dataclasses import replace
from collections import deque
from traffic.simulation import Simulation,Vehicle,STEP
from traffic.network import Network,Path
from traffic.prolog import PrologRules
from traffic.profiles import Driver,VehicleSpec,sample_driver
from traffic import overtaking,behaviour
from traffic.supervisor import rectangles_overlap


class DriverRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=PrologRules();cls.net=Network()

    def sim(self):
        s=Simulation(self.rules,network=self.net,mode='accident');s.reset(target=0)
        s.network.paths['test']=Path('test',[(0,0),(100,0)],source='fixture_a',target='fixture_b')
        s.network.paths['fixture_b>fixture_a']=Path('fixture_b>fixture_a',[(100,5),(0,5)],source='fixture_b',target='fixture_a')
        return s

    def seed_perception(self,v,gap=50):
        clear=('green',False,True,True,True,'road','straight',True,True,True)
        v.history=deque([(-2.,v.index,clear,True)])
        v.perception=deque([(-2.,v.index,gap,0.,None)])
        v.next_behaviour=100

    def assert_geometry(self,s):
        for v in s.vehicles:self.assertTrue(overtaking.valid(s,v),(v.path_id,v.s,v.passing_state))
        for i,a in enumerate(s.vehicles):
            for b in s.vehicles[i+1:]:
                self.assertFalse(rectangles_overlap(s.pose(a),a.spec,s.pose(b),b.spec,margin=-.001))

    def test_personalities_stable_and_configured_majority(self):
        rng=random.Random(22)
        drunk=[sample_driver('Drunk',rng) for _ in range(1000)]
        self.assertTrue(700<sum(d.subgroup=='higher_risk' for d in drunk)<800)
        self.assertGreater(len(set(d.speed_factor for d in drunk)),900)
        newbies=[sample_driver('Newbie',rng) for _ in range(100)]
        self.assertGreater(sum(d.subgroup=='cautious' for d in newbies),50)
        s=self.sim();v=Vehicle(1,('test',),5,0,driver=drunk[0]);s.vehicles=[v]
        saved=v.driver
        for _ in range(120):s.step()
        self.assertIs(v.driver,saved)

    def test_red_opportunity_not_rerolled(self):
        s=self.sim();v=Vehicle(1,('test',),5,0,driver=Driver(kind='Drunk',signal_risk=0))
        obs=('red',False,True,True,True,'signal','straight',True,True,True)
        s._proposal(v,obs,True)
        v.driver=replace(v.driver,signal_risk=1.)
        for t in (1,10,20,50):s.elapsed=t;s._proposal(v,obs,True)
        self.assertFalse(v.risky_signal)
        self.assertEqual(len([k for k in v.opportunities if k[0]=='signal']),1)

    def test_cautious_stop_does_not_creep_into_false_commitment(self):
        s=self.sim();first='02>12';cp='02>12|12>22'
        a=Vehicle(1,(first,cp,'12>22'),s.network.paths[first].length-2.7,0,
                  driver=Driver(kind='Newbie',subgroup='cautious',reaction=.7,gap=4.))
        s.vehicles=[a]
        for _ in range(600):s.step()
        self.assertIsNone(a.permit)
        self.assertEqual(a.index,0)
        self.assertLess(a.s+a.spec.length/2,s.network.paths[first].length)
        self.assertFalse(any(e['reason']=='late_signal_entry' for e in s.behaviour_audit.events.values()))

    def test_late_braking_rear_end_and_newbie_overshoot(self):
        for profile,episode in (('Drunk','steady'),('Newbie','pedal_overshoot')):
            s=self.sim()
            driver=Driver(kind=profile,subgroup='higher_risk' if profile=='Drunk' else 'unsteady',
                          reaction=1.5,braking=.55 if profile=='Drunk' else 1.,gap=1.,speed_factor=1.2)
            a=Vehicle(1,('test',),5,0,speed=8,driver=driver,episode=episode)
            b=Vehicle(2,('test',),18,0,spec=VehicleSpec(cruise=0))
            self.seed_perception(a);s.vehicles=[a,b]
            accelerated=False
            for _ in range(150):
                old=a.speed;s.step()
                if not a.crashed:self.assertLessEqual(a.speed-old,a.spec.acceleration*STEP+1e-8)
                accelerated |= a.speed>8.1
                self.assert_geometry(s)
                if a.crashed:break
            self.assertTrue(a.crashed and b.crashed,profile)
            if profile=='Newbie':self.assertTrue(accelerated)
            self.assertEqual(len(s.incidents.records),1)
            for _ in range(20):s.step()
            self.assertEqual(len(s.incidents.records),1)
            # Same initial physical danger with Normal's retained protection.
            safe=self.sim();a=Vehicle(1,('test',),5,0,speed=8)
            b=Vehicle(2,('test',),18,0,spec=VehicleSpec(cruise=0));safe.vehicles=[a,b]
            for _ in range(150):safe.step()
            self.assertFalse(safe.incidents.records)

    def test_late_braking_command_uses_perception(self):
        self.assertEqual(self.rules.drive('proceed',False,2,8,10,2,False,False),('brake','late_braking'))
        self.assertEqual(self.rules.drive('proceed',False,100,0,10,2,False,False),('proceed','perceived_clear'))

    def test_insufficient_braking_reaches_physical_contact(self):
        s=self.sim()
        a=Vehicle(1,('test',),5,0,speed=10,driver=Driver(kind='Drunk',braking=.5,gap=1.))
        b=Vehicle(2,('test',),24.4,0,spec=VehicleSpec(cruise=0));s.vehicles=[a,b]
        s.step()
        self.assertEqual(a.control_reason,'late_braking')
        self.assertLess(a.speed,10)
        for _ in range(240):
            s.step()
            if a.crashed:break
        self.assertTrue(a.crashed)

    def test_signal_violation_crossing_contact(self):
        s=self.sim()
        first='02>12';cp='02>12|12>22';cross='11>12|12>13'
        self.assertEqual(s.signals['12'].light(s.network.paths[cp].approach),'red')
        a=Vehicle(1,(first,cp,'12>22'),s.network.paths[first].length-1,0,speed=10,
                  driver=Driver(kind='Drunk',signal_risk=1.,reaction=0.))
        b=Vehicle(2,(cross,'12>13'),0,0,speed=6,permit=cross)
        s.vehicles=[a,b];s.step()
        self.assertEqual(a.reason,'signal_violation')
        self.assertEqual(a.permit,cp)
        for _ in range(240):
            s.step();self.assert_geometry(s)
            if a.crashed:break
        self.assertTrue(a.crashed and b.crashed)

    def test_roundabout_heading_boundary_stops_at_first_angular_contact(self):
        from traffic.collisions import movement
        s=self.sim()
        a=Vehicle(123,('21>11|11>10',),42.15551453527116,0,speed=6)
        b=Vehicle(107,('01>11|11>21',),6.861727164354087,0,speed=4.521180674203406)
        s.vehicles=[a,b]
        updates=movement(s,[(a,a.s+.1,6),(b,b.s+4.554*STEP,4.554)])
        for v,pos,speed in updates:v.s,v.speed=pos,speed
        self.assertTrue(a.crashed and b.crashed)
        self.assert_geometry(s)
        self.assertIsNotNone(a.contact_pose)
        frozen=s.pose(a)
        for _ in range(30):s.step()
        self.assertEqual(s.pose(a),frozen)

    def passing_fixture(self,oncoming=False):
        s=self.sim()
        d=Driver(kind='Drunk',subgroup='higher_risk',reaction=.8,gap=1.,speed_factor=1.4,
                 overtake=1.,gap_bias=2. if oncoming else 1.,closing_bias=.1 if oncoming else 1.)
        a=Vehicle(1,('test',),4,0,speed=8,driver=d)
        b=Vehicle(2,('test',),18,0,speed=2,spec=VehicleSpec(cruise=2))
        self.seed_perception(a);s.vehicles=[a,b]
        if oncoming:s.vehicles.append(Vehicle(3,('fixture_b>fixture_a',),55,0,speed=12,spec=VehicleSpec(cruise=12)))
        return s,a

    def test_safe_overtaking_and_misjudged_oncoming_contact(self):
        for oncoming in (False,True):
            s,a=self.passing_fixture(oncoming);states=set();max_side=0
            for _ in range(600):
                s.step();states.add(a.passing_state)
                if a.manoeuvre:max_side=max(max_side,overtaking.base_position(s,a)[2])
                self.assert_geometry(s)
                if a.crashed or s.behaviour_audit.passing['completions']:break
            self.assertIn('move_out',states)
            if oncoming:
                self.assertTrue(a.crashed)
                self.assertIn(3,s.incidents.involved)
                self.assertTrue(any(e['reason']=='overtaking_gap_misjudged' for e in s.behaviour_audit.events.values()))
            else:
                self.assertEqual(s.behaviour_audit.passing['completions'],1,states)
                self.assertFalse(s.incidents.records)
                self.assertGreater(max_side,4.9)
                self.assertEqual(a.path_id,'test')
                self.assertAlmostEqual(s.pose(a)[1],0)

    def test_passing_excludes_access_and_non_sedans(self):
        s,a=self.passing_fixture()
        self.assertTrue(overtaking.excluded(s,'02>12'))
        a.spec=VehicleSpec(kind='Truck',length=7.2,width=2.3)
        for _ in range(60):s.step()
        self.assertFalse(a.manoeuvre)

    def test_safe_pass_on_existing_city_segment(self):
        s=self.sim()
        a=Vehicle(1,('01>02',),3,0,speed=2,driver=Driver(kind='Drunk',subgroup='higher_risk',
                  reaction=0,gap=.7,speed_factor=1.4,overtake=1))
        b=Vehicle(2,('01>02',),10.3,0,speed=.5,spec=VehicleSpec(cruise=.5));s.vehicles=[a,b]
        for _ in range(600):
            s.step();self.assert_geometry(s)
            if s.behaviour_audit.passing['completions']:break
        self.assertEqual(s.behaviour_audit.passing['completions'],1)
        self.assertFalse(s.incidents.records)

    def test_abort_returns_on_an_explicit_path(self):
        s,a=self.passing_fixture()
        injected=False
        for _ in range(600):
            if a.passing_state=='pass' and overtaking.corridor(s,a)[-1]:
                a.oncoming_history=deque([(s.elapsed-2,1.,20.)])
                injected=True
            s.step();self.assert_geometry(s)
            if s.behaviour_audit.passing['aborts']:break
        self.assertTrue(injected)
        self.assertEqual(s.behaviour_audit.passing['aborts'],1)
        self.assertFalse(s.incidents.records)
        self.assertAlmostEqual(s.pose(a)[1],0.)

    def test_same_seed_reproduces_motion_and_audit(self):
        a,b=self.passing_fixture(True)[0],self.passing_fixture(True)[0]
        for _ in range(180):a.step();b.step()
        self.assertEqual(a.vehicles,b.vehicles)
        self.assertEqual(a.incidents.records,b.incidents.records)
        self.assertEqual(a.behaviour_audit.values(),b.behaviour_audit.values())


if __name__=='__main__':unittest.main()
