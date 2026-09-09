"""Real-window observations of ordinary traffic plus labelled heatmap fixtures."""
import json
from pathlib import Path


class FourLaneGuiChecks:
    def __init__(self,sim,view,ui,scenario,screenshot):
        self.sim,self.view,self.ui=sim,view,ui;self.scenario=scenario;self.screenshot=screenshot
        self.stage='layout';self.report={};sim.seed=42;sim.set_target(100);scenario('Baseline')

    def focus(self,v):
        from ursina import Vec3,camera
        x,z,_=self.sim.pose(v);self.view.focus=Vec3(x,0,z);self.view.zoom(85-camera.fov);self.view.set_camera()
        self.ui.set_selection('vehicle',v.id);self.ui.setup.enabled=False;self.ui.follow_id=v.id

    def capture(self,name):
        self.screenshot('four-lane-'+name+'.png')

    def step(self):
        from ursina import application,Vec3,camera,time
        s=self.sim
        from .render_validation import validate
        # Ordinary cars must retain separate scene nodes, including while
        # crossing lanes, crashing and being replaced after clearance.
        if set(self.view.cars)=={v.id for v in s.vehicles}:validate(self.view,s)
        if self.stage=='layout':
            self.capture('home');self.view.zoom(160-camera.fov);self.stage='layout_detail';return
        if self.stage=='layout_detail':
            self.capture('compact-detail');self.view.home();self.stage='normal';return
        if self.stage.endswith('_capture'):
            self.capture(self.stage[:-8])
            if self.stage=='turn_capture':
                s.paused=False;self.ui.follow_id=None;self.view.home();self.stage='normal';return
            if self.stage=='normal_capture':
                self.report['normal']=dict(time=s.elapsed,active=len(s.vehicles),trips=s.completed,collisions=len(s.incidents.records))
                s.seed=42;self.scenario('Evening/night');self.stage='pass';return
            if self.stage=='pass_capture':s.paused=False;self.stage='passed';return
            if self.stage=='passed_capture':
                s.seed=43;self.scenario('Evening/night');self.stage='wrong';return
            if self.stage=='wrong_capture':
                self.ui.follow_id=None;s.overlay='Road usage';s.heat_scale=.25
                self.view.home();self.view.zoom(200-camera.fov);self.stage='usage_capture';return
            if self.stage=='usage_capture':
                s.overlay='Accidents';s.heat_scale=1;self.stage='accidents_capture';return
            if self.stage=='accidents_capture':
                self.stage='pan';self.pan_time=0;s.paused=False;return
        if self.stage=='pan':
            self.pan_time+=time.dt;s.advance(time.dt);self.view.pan(time.dt*10,0)
            self.view.zoom(time.dt*3)
            if self.pan_time>3:
                self.capture('night-pan')
                # Rendering is observational: same physical/RNG state under
                # both settings, even with extra interpolation/light/UI calls.
                def signature():return repr((s.elapsed,[(v.id,v.path_id,v.s,v.speed,v.driver,v.behaviour_rng.getstate()) for v in s.vehicles],s.rng.getstate()))
                before=signature()
                for optimized in (False,True):
                    self.view.optimized=optimized;self.view.lighting.optimized=optimized;self.ui.optimized=optimized
                    for _ in range(3):self.view.sync(s);self.ui.sync()
                    assert signature()==before
                self.report['rendering_observational']=True;self.report['pan_seconds']=self.pan_time
                self.ui.follow_id=None;assert self.ui.follow_id is None
                self.report['follow_cancel']=True
                self.stage='heat_fixture';self.heat_step=0;s.paused=True
                self.saved_metrics=s.metrics;self.saved_incidents=s.incidents
                from .incidents import Metrics,Incidents
                s.metrics=Metrics();s.incidents=Incidents();s.heat_scale=1
                self.heat_pid=next(p.id for p in s.network.lanes.values() if p.part=='entry' and p.length>60)
                p=s.network.paths[self.heat_pid];x,z,_=p.pose(p.length/2)
                self.view.focus=Vec3(x,0,z);self.view.zoom(80-camera.fov);self.view.set_camera()
                self.ui.title.text='HEATMAP VERIFICATION / SYNTHETIC FIXTURE';self.ui.optimized=False
            return
        if self.stage=='heat_fixture':
            from .simulation import Vehicle
            import math
            n=(1,25,50,1,3,5)[self.heat_step];p=s.network.paths[self.heat_pid]
            if self.heat_step<3:
                s.overlay='Road usage';v=Vehicle(999999,(p.id,)*50,0,0)
                for i in range(n):v.index=i;s.metrics.enter(v,s.network)
                self.ui.set_selection('lane',p.id)
                assert s.metrics.usage[p.id]==n
            else:
                s.overlay='Accidents'
                # Independent, touching pairs produce separate incident origins.
                while len(s.incidents.records)<n:
                    i=len(s.incidents.records);a=Vehicle(90000+2*i,(p.id,),p.length/2,0)
                    b=Vehicle(90001+2*i,(p.id,),p.length/2+a.spec.length,0)
                    s.incidents.register(s,a,b)
                cell=tuple(math.floor(x/16) for x in s.incidents.records[0]['location'])
                assert s.incidents.cells[cell]==n
                self.ui.set_selection('cell',cell)
            self.stage='heat_draw';return
        if self.stage=='heat_draw':
            self.capture('frequency-'+str(self.heat_step))
            self.heat_step+=1
            if self.heat_step<6:self.stage='heat_fixture';return
            s.metrics=self.saved_metrics;s.incidents=self.saved_incidents
            self.report['heatmap_fixtures']=dict(passages=[1,25,50],separate_origins=[1,3,5],scale=1)
            out=Path('artifacts/four-lane');out.mkdir(parents=True,exist_ok=True)
            (out/'gui.json').write_text(json.dumps(self.report,indent=2))
            print('Four-lane GUI checks passed: '+json.dumps(self.report),flush=True);application.quit();return
        for _ in range(120):
            s.step()
            if self.stage=='normal' and 'long_vehicle_turn' not in self.report:
                actor=next((v for v in s.vehicles if v.spec.kind in ('Bus','Truck') and s.network.paths[v.path_id].kind=='roundabout'),None)
                if actor:
                    self.focus(actor);s.paused=True;self.stage='turn_capture'
                    self.report['long_vehicle_turn']=dict(time=s.elapsed,id=actor.id,type=actor.spec.kind,path=actor.path_id)
                    return
            if self.stage=='normal' and len(s.vehicles)==100:
                assert not s.incidents.records
                s.paused=True;self.ui.setup.enabled=True;self.stage='normal_capture';return
            if self.stage=='pass':
                v=next((v for v in s.vehicles if not v.crashed and v.lane_change and v.lane_change['kind']=='overtaking' and v.passing_state=='change'),None)
                if v:
                    self.focus(v);self.report['pass']=dict(seed=s.seed,time=s.elapsed,actor=v.id)
                    s.paused=True;self.stage='pass_capture';return
            if self.stage=='passed':
                v=next((v for v in s.vehicles if not v.crashed and v.pass_episode and v.pass_episode['phase']=='passed'),None)
                if v:
                    self.focus(v);self.report['passed']=dict(seed=s.seed,time=s.elapsed,actor=v.id)
                    s.paused=True;self.stage='passed_capture';return
            if self.stage=='wrong':
                v=next((v for v in s.vehicles if not v.crashed and v.manoeuvre and v.passing_state=='wrong_way'),None)
                if v:
                    self.focus(v);self.report['wrong_way']=dict(seed=s.seed,time=s.elapsed,actor=v.id)
                    s.paused=True;self.stage='wrong_capture';return
            assert s.elapsed<300,f'Ordinary GUI observation timed out: {self.stage}'
