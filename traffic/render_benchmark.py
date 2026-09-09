"""Real-window frame measurements. Traffic and collision detection stay active."""
import argparse
import json
import math
import platform
from copy import deepcopy
from pathlib import Path
from time import perf_counter


def distribution(values):
    values=sorted(values)
    def percentile(q):return values[min(len(values)-1,round((len(values)-1)*q))] if values else None
    return dict(median=percentile(.5),p95=percentile(.95),p99=percentile(.99))


def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=('before','after'),default='before')
    p.add_argument('--seconds',type=float,default=8);p.add_argument('--shadow-probe',action='store_true')
    p.add_argument('--heat-probe',action='store_true')
    a=p.parse_args()
    from ursina import Ursina,Entity,time,application,Vec3,window
    from panda3d.core import ClockObject
    from .simulation import Simulation
    from .prolog import PrologRules
    from .rendering import CityView
    from .ui import Interface
    app=Ursina(title='Four-lane frame benchmark',size=(1440,900),borderless=False,vsync=False,development_mode=False)
    ClockObject.getGlobalClock().setMode(ClockObject.M_normal)
    window.fps_counter.enabled=False
    sim=Simulation(PrologRules(),mode='accident')
    ui=Interface(sim,lambda:None,lambda:view.home(),lambda name:None)
    view=CityView(sim.network,ui.select)
    view.optimized=a.phase=='after';view.lighting.optimized=view.optimized;ui.optimized=view.optimized
    cases=[dict(night=night,target=target,pan=pan) for night in (False,True) for target in (40,100) for pan in (False,True)]
    if a.shadow_probe:cases=[dict(night=n,target=100,pan=True,force_shadows=shadow) for n in (False,True) for shadow in (True,False)]
    if a.heat_probe:cases=[dict(night=n,target=100,pan=True,overlay='Road usage') for n in (False,True)]
    gsg=app.win.getGsg()
    hardware=dict(cpu=platform.processor(),platform=platform.platform(),renderer=gsg.getDriverRenderer(),
                  vendor=gsg.getDriverVendor(),driver=gsg.getDriverVersion(),resolution=[1440,900],vsync=False,frame_limit=0)

    class Probe(Entity):
        def __init__(self):
            super().__init__();self.results=[];self.number=-1;self.warmed={};self.done=False;self.next_case()
            sort=next(task for task in app.taskMgr.getTasks() if task.getName()=='igLoop').getSort()
            app.taskMgr.add(self.before_draw,'profile-before-draw',sort=sort-1)
            app.taskMgr.add(self.after_draw,'profile-after-draw',sort=sort+1)

        def before_draw(self,task):self.draw_start=perf_counter();return task.cont
        def after_draw(self,task):
            if sim.timings.enabled:sim.timings.values['render_submit']+=(perf_counter()-self.draw_start)*1000
            return task.cont

        def next_case(self):
            self.number+=1
            if self.number==len(cases):
                output=Path('artifacts/four-lane');output.mkdir(parents=True,exist_ok=True)
                name=('shadows-' if a.shadow_probe else 'heat-' if a.heat_probe else 'frames-')+a.phase+'.json'
                (output/name).write_text(json.dumps(dict(hardware=hardware,phase=a.phase,seconds_per_case=a.seconds,cases=self.results),indent=2))
                self.done=True;print(json.dumps(self.results),flush=True);application.quit();return
            self.case=cases[self.number];view.clear_cars();sim.reset('Baseline',target=self.case['target'])
            view.lighting.forced_shadows=self.case.get('force_shadows')
            ui.population.value=sim.target;view.home();self.stage='warm';self.frames=[];self.costs=[];self.populations=[]
            self.previous=None
            if self.case['target'] in self.warmed:
                saved=self.warmed[self.case['target']]
                sim.__dict__.update(deepcopy(saved.__dict__,{id(saved):sim,id(saved.rules):saved.rules}))

        def update(self):
            if self.done:return
            now=perf_counter()
            if self.stage=='warm':
                for _ in range(120):
                    if len(sim.vehicles)==sim.target and sim.elapsed>=2:break
                    sim.step()
                view.sync(sim);ui.sync()
                if view.optimized:
                    from .render_validation import validate
                    validate(view,sim)
                if len(sim.vehicles)==sim.target and sim.elapsed>=2:
                    if sim.target not in self.warmed:self.warmed[sim.target]=deepcopy(sim,{id(sim.rules):sim.rules})
                    sim.start_clock=(21*3600 if self.case['night'] else 12*3600)-sim.elapsed
                    sim.overlay=self.case.get('overlay','None')
                    self.stage='settle';self.start=now;sim.accumulator=0
                if sim.ticks%1800==0:print(f'Warm {sim.elapsed:.0f}s: {len(sim.vehicles)} active',flush=True)
                assert sim.elapsed<600,'Could not reach benchmark population with ordinary safe admissions'
                return
            if self.previous is not None and self.stage=='measure':
                self.frames.append((now-self.previous)*1000);self.costs.append(sim.timings.take());self.populations.append(len(sim.vehicles))
            self.previous=now
            sim.advance(time.dt)
            if self.case['pan']:
                t=now-self.start;view.focus=Vec3(math.sin(t*.7)*45,0,math.cos(t*.5)*35)
                view.set_camera();view.zoom((240+40*math.sin(t*.6))-__import__('ursina').camera.fov)
            view.sync(sim)
            with sim.timings.measure('ui'):ui.sync()
            if self.stage=='settle' and now-self.start>=1:
                self.stage='measure';self.start=now;self.previous=None;sim.timings.enabled=True;sim.timings.take()
            elif self.stage=='measure' and now-self.start>=a.seconds:
                if view.optimized:
                    from .render_validation import validate
                    validate(view,sim)
                keys=set().union(*(row.keys() for row in self.costs))
                result=dict(**self.case,samples=len(self.frames),frame_ms=distribution(self.frames),
                    median_fps=1000/distribution(self.frames)['median'],actual_population=dict(min=min(self.populations),max=max(self.populations)),
                    cpu_ms={key:distribution([row.get(key,0.) for row in self.costs]) for key in sorted(keys)},
                    shadows=view.lighting.sun.shadows,clock=sim.clock_label,collisions=len(sim.incidents.records),
                    owned_body_nodes=len({car.model.node() for car in view.cars.values()}))
                self.results.append(result);print(json.dumps(result),flush=True);sim.timings.enabled=False;self.next_case()
    Probe();app.run()


if __name__=='__main__':main()
