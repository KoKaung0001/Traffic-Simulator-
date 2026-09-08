import math
import random
import unittest
from dataclasses import replace

from traffic.demand import ACCESS, BUS_ROUTE, BUS_STOPS, weights, profile_weights, request
from traffic.network import Network
from traffic.profiles import PARAMETERS, Driver, sample_driver, vehicle_spec
from traffic.prolog import PrologRules
from traffic.simulation import Simulation, Vehicle, STEP
from traffic.supervisor import SafetySupervisor, rectangles_overlap


class BehaviourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules=PrologRules()
        cls.network=Network()

    def sim(self,scenario='Baseline'):
        return Simulation(self.rules,network=self.network,scenario=scenario)

    def test_parameter_bounds_and_independence(self):
        rng=random.Random(12)
        for kind,p in PARAMETERS['drivers'].items():
            drivers=[sample_driver(kind,rng) for _ in range(100)]
            self.assertGreater(len(set(d.reaction for d in drivers)),90)
            for d in drivers:
                for attribute,key in [('reaction','reaction'),('gap','gap'),('speed_factor','speed'),('acceleration','acceleration'),('entry_gap','entry_gap')]:
                    self.assertTrue(p[key][0]<=getattr(d,attribute)<=p[key][1])
            for vehicle in PARAMETERS['vehicles']:
                v=Vehicle(1,('01>11',),0,0,driver=drivers[0],spec=vehicle_spec(vehicle))
                self.assertEqual(v.driver.kind,kind)
                self.assertEqual(v.spec.kind,vehicle)

    def test_real_delayed_observations(self):
        sim=self.sim()
        v=Vehicle(1,('12>13',),5,0,driver=Driver(reaction=1.))
        green=('green',False,True,True,True,'signal','straight',True,True,True)
        red=('red',)+green[1:]
        sim._proposal(v,green,True)
        self.assertEqual(v.reason,'delayed_response')
        sim.elapsed=.5
        sim._proposal(v,red,True)
        self.assertEqual(v.reason,'delayed_response')
        sim.elapsed=1.
        sim._proposal(v,red,True)
        self.assertEqual(v.reason,'green_and_clear')
        sim.elapsed=1.5
        sim._proposal(v,red,True)
        self.assertEqual(v.reason,'red_signal')

    def test_prolog_controlled_behaviour_differences(self):
        obs=('red',False,True,True,True,'signal','straight',True,True,True)
        self.assertEqual(self.rules.behave(obs,'Normal'),('stop','red_signal'))
        self.assertEqual(self.rules.behave(obs,'Drunk',risk_signal=True),('proceed','signal_violation'))
        green=('green',)+obs[1:]
        self.assertEqual(self.rules.behave(green,'Newbie',larger_gap=False),('wait','waiting_for_larger_gap'))
        unsafe=list(green); unsafe[7]=False
        self.assertEqual(self.rules.behave(tuple(unsafe),'Drunk',risk_gap=True),('proceed','unsafe_gap_accepted'))
        self.assertEqual(self.rules.behave(green,'Normal',dwell=True),('wait','bus_stop_dwell'))

    def test_persistent_sampling_and_reproducibility(self):
        a,b=self.sim('Evening/night'),self.sim('Evening/night')
        self.assertEqual(a.vehicles,b.vehicles)
        for _ in range(180):
            a.step(); b.step()
        self.assertEqual(a.vehicles,b.vehicles)
        self.assertEqual(a.supervisor.events,b.supervisor.events)
        v=a.vehicles[0]
        epoch=v.epoch
        state=(v.risky_signal,v.risky_gap,v.speed_variation)
        obs=('green',False,True,True,True,'road','straight',True,True,True)
        a._proposal(v,obs,True)
        self.assertEqual(epoch,v.epoch)
        self.assertEqual(state,(v.risky_signal,v.risky_gap,v.speed_variation))

    def test_contextual_weights_and_clock(self):
        morning,night=7.5*3600,21*3600
        self.assertGreater(weights(morning)['Apartments'],weights(night)['Apartments'])
        self.assertGreater(weights(morning,True)['Offices'],weights(night,True)['Offices'])
        self.assertGreater(profile_weights('Morning commute','University',morning)['Newbie'],profile_weights('Morning commute','Offices',morning)['Newbie'])
        pub=profile_weights('Evening/night','Pub',night)
        self.assertGreater(pub['Drunk'],profile_weights('Evening/night','Offices',night)['Drunk'])
        self.assertTrue(all(weight>0 for weight in pub.values()))
        rng=random.Random(8)
        tickets=[request(rng,'Evening/night',night) for _ in range(1500)]
        self.assertTrue(any(t.vehicle=='Truck' and t.origin=='Depot' for t in tickets))
        self.assertTrue(any(t.vehicle=='Bus' and t.origin=='Terminal' for t in tickets))
        sim=self.sim('Morning commute')
        self.assertEqual(sim.clock_label,'07:30:00')
        sim.advance(2.)
        self.assertEqual(sim.clock_label,'07:30:02')
        sim.reset('Evening/night',target=20)
        self.assertEqual((sim.clock_label,sim.target,len(sim.vehicles)),('21:00:00',20,20))

    def test_long_vehicle_geometry_and_rear_clearance(self):
        net=self.network
        self.assertFalse(net.supports(BUS_ROUTE,replace(vehicle_spec('Bus'),length=12.)))
        for kind in PARAMETERS['vehicles']:
            spec=vehicle_spec(kind)
            self.assertTrue(net.supports(BUS_ROUTE,spec))
            for p in net.connectors.values():
                self.assertTrue(net.supports((p.id,),spec))
                if p.kind == 'roundabout':
                    cx,cz=net.junctions[p.junction].position
                    for i in range(math.ceil(p.length)):
                        x,z,yaw=p.pose(i)
                        t=math.radians(yaw)
                        for front in (-1,1):
                            for side in (-1,1):
                                xx=x+front*spec.length/2*math.sin(t)+side*spec.width/2*math.cos(t)
                                zz=z+front*spec.length/2*math.cos(t)-side*spec.width/2*math.sin(t)
                                self.assertGreater(math.hypot(xx-cx,zz-cz),6.)
        sim=self.sim();sim.set_target(0)
        connector='12>13|13>north'
        v=Vehicle(1,('12>13',connector,'13>north'),4.,0,index=2,permit=connector,spec=vehicle_spec('Bus'))
        sim.vehicles=[v];sim.step()
        self.assertEqual(v.permit,connector)
        v.s=5.3;sim.step()
        self.assertIsNone(v.permit)

    def test_driver_cannot_exceed_engine_acceleration_limit(self):
        sim=self.sim();sim.set_target(0)
        v=Vehicle(1,('13>north',),10,0,driver=Driver(kind='Drunk',acceleration=1.08))
        sim.vehicles=[v]
        sim.step()
        self.assertLessEqual(v.speed,v.spec.acceleration*STEP+1e-9)

    def test_bus_route_and_dwell(self):
        for a,b in zip(BUS_ROUTE,BUS_ROUTE[1:]):
            self.assertEqual(self.network.paths[a].points[-1],self.network.paths[b].points[0])
        for lane in BUS_STOPS:
            self.assertIn(lane,BUS_ROUTE)
        sim=self.sim();sim.set_target(0)
        index=BUS_ROUTE.index('00>10')
        v=Vehicle(1,BUS_ROUTE,14,0,index=index,spec=vehicle_spec('Bus'))
        sim.vehicles=[v];sim.step()
        self.assertEqual(v.dwell,PARAMETERS['bus_dwell'])
        start=v.s
        for _ in range(round(PARAMETERS['bus_dwell']/STEP)):
            sim.step()
        self.assertAlmostEqual(v.dwell,0,places=6)
        self.assertEqual(v.s,start)
        self.assertIn(index,v.serviced)
        for _ in range(60):sim.step()
        self.assertGreater(v.s,start)

    def test_spawn_clearance_and_intervention_dedup(self):
        supervisor=SafetySupervisor()
        bus=Vehicle(1,('00>10',),12,0,spec=vehicle_spec('Bus'))
        car=Vehicle(2,('00>10',),4,1)
        self.assertFalse(supervisor.spawn_clear(self.network,car,[bus]))
        car.action='proceed';car.reason='unsafe_gap_accepted'
        supervisor.record(car,'reserved_conflict')
        supervisor.record(car,'reserved_conflict')
        car.epoch+=1
        supervisor.record(car,'reserved_conflict')
        self.assertEqual(supervisor.interventions,1)
        self.assertEqual((car.action,car.executed),('proceed','wait'))
        supervisor.violation(car);supervisor.violation(car)
        self.assertEqual(supervisor.violations,1)
        sim=self.sim();sim.vehicles=[car,bus]
        # A deliberately unsafe movement proposal is intercepted, not rewritten.
        updates=sim.supervisor.movement(sim,[(car,11.,10.),(bus,12.,0.)])
        self.assertEqual(updates[0][1],car.s)
        self.assertEqual(car.action,'proceed')


if __name__ == '__main__':
    unittest.main()
