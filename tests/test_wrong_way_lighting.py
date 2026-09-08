import random
import unittest
from dataclasses import replace
from traffic.simulation import Simulation,Vehicle,STEP
from traffic.network import Network,Path
from traffic.profiles import sample_driver,Driver,VehicleSpec
from traffic.prolog import PrologRules
from traffic.overtaking import valid,base_position
from traffic.supervisor import rectangles_overlap
from traffic.lighting import daylight


class WrongWayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=PrologRules();cls.net=Network()

    def fixture(self,city=False):
        s=Simulation(self.rules,network=self.net,seed=3,mode='accident');s.reset('Evening/night',target=0)
        lane='01>02' if city else 'wrongway_test'
        if not city:
            s.network.paths[lane]=Path(lane,[(0,0),(120,0)],source='a',target='b')
            s.network.paths['reverse_test']=Path('reverse_test',[(120,5),(0,5)],source='b',target='a')
        v=Vehicle(100,(lane,),3,0,speed=2,driver=sample_driver('Drunk',random.Random(3)))
        s.vehicles=[v]
        return s,v

    def check(self,s):
        for v in s.vehicles:self.assertTrue(valid(s,v),(v.s,v.passing_state))
        for i,a in enumerate(s.vehicles):
            for b in s.vehicles[i+1:]:
                self.assertFalse(rectangles_overlap(s.pose(a),a.spec,s.pose(b),b.spec,margin=-.001))

    def test_seeded_city_wrong_way_episode_and_return(self):
        s,v=self.fixture(city=True);states=set();times=[]
        for _ in range(1500):
            old=s.pose(v);s.step();self.check(s);states.add(v.passing_state)
            self.assertLessEqual(__import__('math').dist(old[:2],s.pose(v)[:2]),max(v.speed,3)*STEP+.01)
            if v.passing_state=='wrong_way':times.append(s.elapsed)
            if s.behaviour_audit.passing['wrong_way_returns']:break
        self.assertTrue({'assess','move_out','wrong_way','return','follow'}<=states)
        self.assertGreater(times[-1]-times[0],2.)
        self.assertEqual(s.behaviour_audit.passing['wrong_way_attempts'],1)
        self.assertEqual(v.path_id,'01>02')
        self.assertFalse(s.incidents.records)
        self.assertEqual(len([key for key in v.opportunities if key[0]=='wrong_way']),1)

    def test_oncoming_response_bounded_and_contact_possible(self):
        s,v=self.fixture()
        v.driver=replace(v.driver,gap_bias=10,closing_bias=.01)
        normal=Vehicle(101,('reverse_test',),65,0,speed=8,driver=Driver(reaction=.8))
        s.vehicles.append(normal);braked=False
        for _ in range(1200):
            old=normal.speed;s.step();self.check(s)
            if not normal.crashed:
                self.assertGreaterEqual(normal.speed-old,-normal.spec.braking*STEP-1e-8)
            braked |= normal.oncoming_brake
            if normal.crashed:break
        self.assertTrue(braked)
        self.assertTrue(normal.crashed and v.crashed)
        self.assertEqual(s.incidents.involved,{100,101})

    def test_reproducible_and_pause(self):
        a,x=self.fixture();b,y=self.fixture()
        for _ in range(700):a.step();b.step()
        self.assertEqual(a.vehicles,b.vehicles)
        self.assertEqual(a.behaviour_audit.values(),b.behaviour_audit.values())
        a.paused=True;before=repr((a.vehicles,a.clock));a.advance(50)
        self.assertEqual(before,repr((a.vehicles,a.clock)))

    def test_daylight_clock_boundaries(self):
        self.assertEqual(daylight(21*3600),0)
        self.assertEqual(daylight(12*3600),1)
        self.assertEqual(daylight(0),daylight(86400))
        self.assertTrue(0<daylight(6.25*3600)<daylight(6.5*3600)<1)
        self.assertAlmostEqual(daylight(6.25*3600),daylight(17.75*3600))
        self.assertLess(abs(daylight(18*3600-1)-daylight(18*3600)),.001)


if __name__=='__main__':unittest.main()
