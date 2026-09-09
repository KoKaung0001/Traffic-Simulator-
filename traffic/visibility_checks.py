"""Fresh-window regression for shared meshes, every vehicle type and lighting."""
import json,math,random
from pathlib import Path


def main():
    from ursina import Ursina,Entity,Text,Vec3,camera,application,destroy
    from panda3d.core import Filename
    from .simulation import Simulation,Vehicle,STEP
    from .prolog import PrologRules
    from .profiles import vehicle_spec
    from .rendering import CityView
    from .render_validation import validate,selection
    app=Ursina(title='Vehicle visibility verification',size=(1440,900),borderless=False,vsync=False,development_mode=False)
    s=Simulation(PrologRules(),mode='accident');s.reset(target=0)
    view=CityView(s.network,lambda *args:None)
    title=Text(text='VISIBILITY REGRESSION / DUPLICATE ASSET INSTANCES',position=(-.77,.46),scale=1.2)
    out=Path('artifacts/visibility');out.mkdir(parents=True,exist_ok=True)
    road='rNW>rw';ids=s.network.segments[road,'outer']
    for i in range(6):
        kind=('Sedan','Truck','Bus')[i//2];pid,pos=s.network.locate(road,'outer',12+i*20)
        v=Vehicle(i+1,tuple(ids),pos,1,index=ids.index(pid),spec=vehicle_spec(kind),speed=2,behaviour_rng=random.Random(i))
        s.vehicles.append(v)
    s.target=6
    cases=[(night,kind,zoom) for night in (False,True) for kind in ('Sedan','Truck','Bus') for zoom in (55,220)]
    report=dict(cases=[],ownership_checks=0,isolation=False)

    class Check(Entity):
        def __init__(self):super().__init__();self.case=0;self.frames=0;self.done=False
        def update(self):
            if self.done:return
            night,kind,zoom=cases[self.case]
            s.start_clock=(21 if night else 12)*3600-s.elapsed
            v=next(v for v in s.vehicles if v.spec.kind==kind)
            x,z,_=s.pose(v);view.focus=Vec3(x,0,z);view.zoom(zoom-camera.fov);view.set_camera()
            # Nonzero interpolation fraction makes body/light/selection drift detectable.
            if self.frames==0:
                for _ in range(6):s.step()
                s.accumulator=STEP*.4
            view.sync(s);selection(view,s,v);report['ownership_checks']+=validate(view,s)
            self.frames+=1
            if self.frames<3:return
            name=f'{"night" if night else "day"}-{kind.lower()}-{zoom}.png'
            app.win.setActive(True);app.graphicsEngine.renderFrame();app.graphicsEngine.renderFrame()
            app.win.saveScreenshot(Filename.fromOsSpecific(str(out/name)))
            report['cases'].append(dict(night=night,type=kind,zoom=zoom,active=len(s.vehicles),capture=name))
            self.case+=1;self.frames=0
            if self.case<len(cases):return
            # Destroy/hide/tint a duplicate; its sibling and the templates must survive.
            for kind in ('Sedan','Truck','Bus'):
                a,b=[v for v in s.vehicles if v.spec.kind==kind]
                first,other=view.cars[a.id],view.cars[b.id]
                body=other.model.node();lamps=other.bulbs[0].model.node()
                first.enabled=False;first.color=(1,0,0,.1)
                assert not other.isHidden() and not other.isStashed() and other.color.a==1
                first.enabled=True
                s.remove_vehicles([a.id],'population_retirement');view.sync(s);validate(view,s)
                assert other.model.node()==body and other.bulbs[0].model.node()==lamps
                # Reuse the exact same cached asset after deletion.
                c=Vehicle(100+b.id,b.route,b.s-12,1,index=b.index,spec=b.spec)
                s.vehicles.append(c);view.sync(s);validate(view,s)
            report['isolation']=True
            # Combined body/wheels, lamps and highlight share one frame even
            # on lateral links; all types use their original dimensions.
            cp=next(s.network.paths[pid] for pid in s.network.change_links.values())
            for actor in s.vehicles:
                saved=(actor.route,actor.index,actor.s)
                actor.route=(cp.id,);actor.index=0;actor.s=cp.length*.5
                s.previous_poses[actor.id]=cp.pose(actor.s-.1)
                view.sync(s);selection(view,s,actor);validate(view,s)
                actor.route,actor.index,actor.s=saved
                s.previous_poses[actor.id]=s.pose(actor)
            # Wrong-way is sedan-only, with a real continuous opposing path.
            from .four_wrong_way import install
            actor=next(v for v in s.vehicles if v.spec.kind=='Sedan')
            saved=(actor.route,actor.index,actor.s)
            actor.route=(s.network.segments[road,'inner'][-1],);actor.index=0;actor.s=0
            actor.manoeuvre=dict(road=road,route=actor.route,limit=s.network.roads[road]['length']-8)
            assert install(s,actor)
            actor.s=actor.manoeuvre['shift_end']*.7
            s.previous_poses[actor.id]=s.network.paths[actor.path_id].pose(actor.s-.1)
            view.sync(s);selection(view,s,actor);validate(view,s)
            actor.route,actor.index,actor.s=saved;actor.manoeuvre=None
            s.previous_poses[actor.id]=s.pose(actor)
            report['lateral_and_wrong_way_alignment']=True
            # Exact crash pose overrides interpolation; clearing one wreck is isolated.
            a=s.vehicles[0];a.crashed=True;a.contact_pose=s.pose(a);s.previous_poses[a.id]=(0,0,0)
            view.sync(s);selection(view,s,a);validate(view,s)
            s.remove_vehicles([a.id],'crash_clearance');view.sync(s);validate(view,s)
            report['crash_and_clearance']=True
            (out/'results.json').write_text(json.dumps(report,indent=2))
            print('VISIBILITY CHECKS PASSED '+json.dumps(report),flush=True)
            self.done=True;application.quit()
    Check();app.run()


if __name__=='__main__':main()
