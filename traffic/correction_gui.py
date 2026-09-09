"""Fresh real-window camera sweep and ordinary manoeuvre clips (12 fps)."""
import argparse,json,math
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=43);p.add_argument('--kind',choices=['lights','overtaking','wrong_way'],default='lights');a=p.parse_args()
    from ursina import Ursina,Entity,Vec3,camera,Text,application
    from .simulation import Simulation
    from .rendering import CityView
    from .prolog import PrologRules
    from .render_validation import validate
    from .night import counts
    import imageio.v2 as imageio
    import numpy as np
    app=Ursina(size=(1440,900),development_mode=False,vsync=False)
    s=Simulation(PrologRules(),scenario='Evening/night',seed=a.seed,mode='accident')
    view=CityView(s.network,lambda *args:None);title=Text(position=(-.77,.46),scale=1)
    out=Path('artifacts/correction');out.mkdir(exist_ok=True,parents=True)
    writer=imageio.get_writer(str(out/f'{a.kind}-{a.seed}.mp4'),fps=12,macro_block_size=1)
    report=dict(seed=a.seed,kind=a.kind,ordinary=True,frames=0,first=None)
    if a.kind=='lights':s.paused=True;report['initial_lights']={v.id:True for v in s.vehicles}
    class Check(Entity):
        actor=None;frames=0;done=False
        def update(self):
            if self.done:return
            if a.kind!='lights' and self.actor is None:
                for _ in range(120):
                    s.step()
                    event=next((e for e in reversed(s.lane_events) if e['kind']==a.kind and e['stage']=='attempt'),None)
                    if event:
                        self.actor=event['id'];report['first']=event['time'];break
                    if s.elapsed>=300:
                        writer.close();report['unresolved']='No ordinary attempt within 300 s';(out/f'{a.kind}-{a.seed}.json').write_text(json.dumps(report,indent=2));application.quit();self.done=True;return
                if self.actor is None:return
            if a.kind=='lights':
                t=self.frames/12
                view.focus=Vec3(115*math.sin(t*1.2),0,100*math.cos(t*1.2));view.zoom(155+65*math.sin(t*1.6)-camera.fov)
                assert s.elapsed==0
            else:
                for _ in range(5):s.step()
                v=next((v for v in s.vehicles if v.id==self.actor),None)
                if v:
                    x,z,_=s.pose(v);view.focus=Vec3(x,0,z);view.zoom(75-camera.fov)
            view.set_camera();view.sync(s);validate(view,s)
            if a.kind=='lights':
                assert all(car.bulbs[0].enabled and car.beam.enabled for car in view.cars.values())
            q=counts(s);title.text=f'{a.kind.upper()} / ordinary seed {a.seed} / {s.elapsed:.2f}s\nDrunk active {q["active"]} / wreck {q["wrecks"]} / pending {q["pending"]} / target {q["target"]}'
            if self.actor:title.text+=f'\nFollowing #{self.actor} / '+('cleared' if v is None else v.passing_state+' / '+v.passing_reason)
            app.graphicsEngine.renderFrame()
            texture=app.win.getScreenshot();arr=np.frombuffer(texture.getRamImageAs('RGB'),dtype=np.uint8).reshape(texture.getYSize(),texture.getXSize(),3)[::-1]
            writer.append_data(arr)
            self.frames+=1
            if self.frames>=144:
                writer.close();report.update(frames=self.frames,elapsed=s.elapsed,lights_unchanged=a.kind=='lights',active=len(s.vehicles))
                (out/f'{a.kind}-{a.seed}.json').write_text(json.dumps(report,indent=2));print('CLIP PASSED',report,flush=True);self.done=True;application.quit()
    Check();app.run()

if __name__=='__main__':main()
