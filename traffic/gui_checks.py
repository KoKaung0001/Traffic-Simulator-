"""Actual renderer checks and captures for recovery, manoeuvres and clock lighting."""
import json
import random
import time
from pathlib import Path
from .simulation import Vehicle
from .profiles import sample_driver
from .overtaking import valid


class RecoveryGuiChecks:
    def __init__(self,sim,view,ui,scenario,screenshot,app):
        self.sim,self.view,self.ui=sim,view,ui
        self.scenario,self.screenshot,self.app=scenario,screenshot,app
        self.report={};self.samples=[]

    def focus(self,v):
        from ursina import Vec3,camera
        x,z,_=self.sim.pose(v);self.view.focus=Vec3(x,0,z)
        self.view.zoom(80-camera.fov);self.view.set_camera()
        self.ui.set_selection('vehicle',v.id)

    def step(self,frame):
        s,v,u=self.sim,self.view,self.ui
        if frame==20:
            self.scenario('Evening/night');s.paused=True
            self.lights=len(v.street_bulbs);self.report['streetlights']=self.lights
        elif frame==35:
            assert v.lighting.day==0 and v.lighting.sun.color.r==0
            self.screenshot('recovery-night-overview.png')
            u.set_selection('vehicle',s.vehicles[0].id);self.focus(s.vehicles[0])
            self.report['night_sun_intensity']=v.lighting.sun.color.r
        elif frame==50:
            self.screenshot('recovery-night-detail.png')
            self.scenario('Baseline');s.paused=True
        elif frame==65:
            assert v.lighting.day==1 and len(v.street_bulbs)==self.lights
            self.screenshot('recovery-day.png')
            self.scenario('Evening/night');v.clear_cars();s.seed=3;s.reset('Evening/night',target=0)
            a=Vehicle(100,('01>02',),3,0,speed=2,driver=sample_driver('Drunk',random.Random(3)))
            s.vehicles=[a];self.actor=a
            for _ in range(1000):
                s.step();assert valid(s,a)
                if a.passing_state=='wrong_way':break
            assert a.passing_state=='wrong_way'
            s.paused=True;self.focus(a)
        elif frame==80:
            self.screenshot('recovery-wrong-way.png')
            s.paused=False
            for _ in range(1000):
                s.step();assert valid(s,self.actor)
                if s.behaviour_audit.passing['wrong_way_returns']:break
            assert s.behaviour_audit.passing['wrong_way_returns']==1
            s.paused=True
        elif frame==95:
            self.screenshot('recovery-wrong-way-return.png')
            self.report['seeded_manoeuvres']=dict(s.behaviour_audit.passing)
            v.clear_cars();s.reset(target=0)
            a=Vehicle(1,('01>02',),12,0);b=Vehicle(2,('01>02',),16.4,0)
            s.vehicles=[a,b];s.incidents.register(s,a,b);s.paused=True
            self.focus(a);s.overlay='Accidents'
        elif frame==110:
            self.screenshot('recovery-incident-heatmap.png')
            s.elapsed=s.incidents.records[0]['clear_at']+.1;s.incidents.clear(s);s.incidents.clear(s)
            s.ticks=round(s.elapsed*60)
            assert not s.vehicles
            self.cleared_history=json.dumps(s.incidents.records)
            a=Vehicle(3,('01>02',),5,0,speed=4);s.vehicles=[a];self.actor=a
            s.paused=False
            for _ in range(130):s.step()
            assert a in s.vehicles and a.s>16.4 and not a.crashed
            assert json.dumps(s.incidents.records)==self.cleared_history
            s.paused=True;self.focus(a)
        elif frame==125:
            self.screenshot('recovery-cleared-traversal.png')
            self.report['cleared_site_traversal']=True
            s.seed=42;s.set_target(40);self.scenario('Evening/night');u.population.value=100
            assert s.target==100
            s.paused=False
            start=time.perf_counter()
            for _ in range(3600):s.step()
            self.report['target100_60s_wall_s']=time.perf_counter()-start
            self.report['target100']=dict(s.metrics.values(s),pending=s.pending,queued=len(s.queued),
                admitted=len(s.behaviour_audit.admitted),blocking=s.spawn_status)
            s.paused=True;v.home();u.setup.enabled=True
        elif frame==140:
            self.screenshot('recovery-population100.png')
            u.setup.enabled=False
        elif 145<=frame<175:
            start=time.perf_counter();self.app.graphicsEngine.renderFrame()
            self.samples.append(time.perf_counter()-start)
        elif frame==175:
            self.report['render_target100_ms']=1000*sum(self.samples)/len(self.samples)
            self.samples=[];self.scenario('Evening/night');s.paused=True
        elif 180<=frame<210:
            start=time.perf_counter();self.app.graphicsEngine.renderFrame()
            self.samples.append(time.perf_counter()-start)
        elif frame==210:
            self.report['render40_ms']=1000*sum(self.samples)/len(self.samples)
            self.report['render40_active']=len(s.vehicles)
            self.report['paused_clock']=s.clock
            assert s.clock==21*3600
            assert len(v.street_bulbs)==self.lights
            Path('artifacts/recovery-gui.json').write_text(json.dumps(self.report,indent=2))
            print('Recovery/night GUI checks passed:',json.dumps(self.report),flush=True)
            from ursina import application
            application.quit()
