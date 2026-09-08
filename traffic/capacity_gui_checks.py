"""Capture ordinary seeded runs, accelerating fixed steps without constructing actors."""
import json
from pathlib import Path


class CapacityGuiChecks:
    def __init__(self,sim,view,ui,scenario,screenshot,layout_only=False):
        self.sim,self.view,self.ui=sim,view,ui
        self.scenario,self.screenshot=scenario,screenshot
        self.stage='layout';self.report={};self.layout_only=layout_only
        sim.seed=42;sim.set_target(100);scenario('Baseline')

    def step(self):
        from ursina import Vec3,camera,application
        s=self.sim
        if self.stage=='layout':
            self.screenshot('compact-centre-home.png')
            self.view.zoom(170-camera.fov);self.view.set_camera();self.stage='detail';return
        if self.stage=='detail':
            self.screenshot('compact-centre-detail.png')
            self.view.home();self.view.zoom(490-camera.fov);self.stage='belt';return
        if self.stage=='belt':
            self.screenshot('compact-outer-belt.png');self.view.home()
            if self.layout_only:
                print('Compact centre and outer belt GUI captures completed.',flush=True)
                application.quit()
            self.stage='normal';return
        if self.stage=='normal_capture':
            assert len(self.view.cars)==100
            self.screenshot('compact-normal-100.png')
            s.seed=42;self.scenario('Evening/night');self.stage='night'
            return
        if self.stage=='night_capture':
            assert self.view.lighting.day==0
            self.screenshot('compact-natural-wrong-way.png')
            output=Path('artifacts/capacity-final');output.mkdir(parents=True,exist_ok=True)
            self.report['streetlights']=len(self.view.street_bulbs)
            (output/'gui.json').write_text(json.dumps(self.report,indent=2))
            print('Ordinary GUI checks passed: 100 Normal vehicles and natural seed-42 wrong-way movement.',flush=True)
            application.quit();return
        for _ in range(120):
            s.step()
            if self.stage=='normal' and len(s.vehicles)==100:
                self.report['normal']=dict(time=s.elapsed,active=100,completed=s.completed)
                s.paused=True;self.ui.setup.enabled=True;self.stage='normal_capture';return
            if self.stage=='night':
                actor=next((v for v in s.vehicles if not v.crashed and v.manoeuvre_mode=='wrong_way'
                            and v.passing_state=='wrong_way'),None)
                if actor:
                    self.report['night']=dict(time=s.elapsed,seed=s.seed,actor=actor.id,
                        active=len(s.vehicles),manoeuvres=dict(s.behaviour_audit.passing))
                    s.paused=True;self.ui.setup.enabled=False
                    x,z,_=s.pose(actor);self.view.focus=Vec3(x,0,z)
                    self.view.zoom(80-camera.fov);self.view.set_camera()
                    self.ui.set_selection('vehicle',actor.id);self.stage='night_capture';return
            assert s.elapsed<600,'Ordinary GUI run did not reach its observation'
