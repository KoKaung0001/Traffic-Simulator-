"""Repeatable before/after corner close-ups from the actual renderer."""
import sys
from pathlib import Path

def main():
    from ursina import Ursina,Entity,Vec3,camera,application
    from panda3d.core import Filename
    from .simulation import Simulation
    from .prolog import PrologRules
    from .rendering import CityView
    app=Ursina(size=(1440,900),development_mode=False,vsync=False)
    s=Simulation(PrologRules());s.reset(target=0);s.paused=True
    view=CityView(s.network,lambda *a:None)
    out=Path('artifacts/correction');out.mkdir(exist_ok=True,parents=True)
    targets=['00','11','22','rNW','rSE']
    class Capture(Entity):
        i=0
        def update(self):
            key=targets[self.i//3];x,z=s.network.nodes[key]
            view.focus=Vec3(x,0,z);view.zoom(65-camera.fov);view.set_camera();view.sync(s)
            if self.i%3==2:
                app.graphicsEngine.renderFrame()
                app.win.saveScreenshot(Filename.fromOsSpecific(str(out/f'corner-{sys.argv[1]}-{key}.png')))
            self.i+=1
            if self.i==len(targets)*3:print('CORNERS CAPTURED',flush=True);application.quit()
    Capture();app.run()

if __name__=='__main__':main()
