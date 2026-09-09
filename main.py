"""Run from any working directory using the existing parent virtual environment."""
import argparse
import sys

from traffic.prolog import PrologRules
from traffic.simulation import Simulation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-test', action='store_true', help='Exercise GUI callbacks, capture overview/detail/resized views and exit.')
    parser.add_argument('--smoke-m4',action='store_true')
    parser.add_argument('--smoke-behaviour',action='store_true')
    parser.add_argument('--smoke-recovery',action='store_true')
    parser.add_argument('--smoke-capacity',action='store_true',help='Capture ordinary Normal population 100 and a natural night wrong-way manoeuvre.')
    parser.add_argument('--smoke-layout',action='store_true',help='Capture restored central proportions and outer belt without advancing traffic.')
    parser.add_argument('--mode',choices=('supervised','accident'),default='accident')
    parser.add_argument('--clearance',type=float,default=45)
    parser.add_argument('--block-spacing',type=float,default=None,help='Override configured grid spacing; 64 restores compact geometry.')
    parser.add_argument('--compact-only',action='store_true',help='Use the original compact roads with improved gate admission, without the outer belt.')
    parser.add_argument('--population',type=int,default=40)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--fps',type=int,default=144,help='Frame cap; 0 is uncapped. This is a limit, not a performance claim.')
    parser.add_argument('--vsync',action='store_true',help='Synchronize presentation to the display refresh rate.')
    parser.add_argument('--lighting',choices=('performance','quality'),default='performance',help='Quality adds daytime sun shadows; both use street irradiance and eight headlights.')
    parser.add_argument('--scenario',choices=('Baseline','Morning commute','Evening/night'),default='Baseline')
    args = parser.parse_args()
    if not 0<=args.population<=100:parser.error('Population must be 0..100')
    if args.fps<0:parser.error('FPS must be nonnegative')
    if args.block_spacing not in (None,64.):parser.error('The compact block spacing is fixed at 64 m.')
    try:
        rules = PrologRules()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    from ursina import Ursina, Entity, held_keys, time, window, application
    from traffic.rendering import CityView
    from traffic.ui import Interface
    app = Ursina(title='Crossing City | AI Traffic Lab', borderless=False, size=(1440, 900), vsync=args.vsync, development_mode=False)
    from panda3d.core import ClockObject
    clock=ClockObject.getGlobalClock()
    clock.setMode(ClockObject.M_limited if args.fps else ClockObject.M_normal)
    if args.fps:clock.setFrameRate(args.fps)
    window.color = __import__('ursina').color.hex('#c6ddd8')
    window.exit_button.visible = False
    window.fps_counter.enabled = False
    from traffic.network import Network
    from traffic.four_lane import FourLaneNetwork
    net=FourLaneNetwork(peripheral=False) if args.compact_only or args.block_spacing is not None else None
    if args.smoke_recovery or args.smoke_behaviour or args.smoke_m4 or args.smoke_test:net=Network()
    sim = Simulation(rules,mode=args.mode,clearance=args.clearance,network=net,seed=args.seed,scenario=args.scenario)
    if args.population!=40:sim.reset(target=args.population)

    def reset():
        view.clear_cars()
        sim.reset()
        ui.reset_controls()
        view.home()
        view.sync(sim)

    def scenario(name):
        target=sim.target
        view.clear_cars()
        sim.reset(name,target=target)
        ui.reset_controls()
        ui.population.value=target
        ui.setup.enabled=False
        view.home()
        view.sync(sim)

    def home():
        ui.follow_id=None;view.home()
    ui = Interface(sim, reset, home,scenario)
    ui.population.value=sim.target
    view = CityView(sim.network, ui.select)
    view.lighting.quality=args.lighting=='quality'
    view.sync(sim)

    def screenshot(name):
        from pathlib import Path
        from panda3d.core import Filename
        destination = Path(__file__).parent / 'artifacts'
        destination.mkdir(exist_ok=True)
        if sys.platform=='win32':
            import ctypes
            hwnd=app.win.getWindowHandle().getIntHandle()
            ctypes.windll.user32.ShowWindow(hwnd,9)
        # Windows may deactivate the drawable when this automated window is
        # covered. Explicit rendering makes captures useful in that case.
        app.win.setActive(True)
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()
        app.win.saveScreenshot(Filename.fromOsSpecific(str(destination / name)))

    def inspect_when(predicate):
        sim.paused=False
        for _ in range(60*300):
            v=next((v for v in sim.vehicles if predicate(v)),None)
            if v:
                sim.paused=True
                x,z,_=sim.pose(v)
                view.focus=__import__('ursina').Vec3(x,0,z)
                view.zoom(95-__import__('ursina').camera.fov)
                view.set_camera()
                view.sync(sim)
                ui.set_selection('vehicle',v.id)
                return
            sim.step()
        raise AssertionError('Visual smoke fixture did not reach the requested state')

    if args.smoke_recovery:
        from traffic.gui_checks import RecoveryGuiChecks
        recovery_checks=RecoveryGuiChecks(sim,view,ui,scenario,screenshot,app)
    if args.smoke_capacity or args.smoke_layout:
        if args.smoke_capacity:
            from traffic.four_gui_checks import FourLaneGuiChecks
            capacity_checks=FourLaneGuiChecks(sim,view,ui,scenario,screenshot)
        else:
            from traffic.capacity_gui_checks import CapacityGuiChecks
            capacity_checks=CapacityGuiChecks(sim,view,ui,scenario,screenshot,layout_only=True)

    class Controller(Entity):
        frames = 0

        def update(self):
            if not (args.smoke_capacity or args.smoke_layout):sim.advance(time.dt)
            if not ui.blocks_pointer():
                dx = held_keys['d'] + held_keys['right arrow'] - held_keys['a'] - held_keys['left arrow']
                dz = held_keys['w'] + held_keys['up arrow'] - held_keys['s'] - held_keys['down arrow']
                if dx or dz:
                    ui.follow_id=None
                    view.pan(dx * time.dt * 50, dz * time.dt * 50)
            if ui.follow_id is not None:
                actor=next((v for v in sim.vehicles if v.id==ui.follow_id),None)
                if actor:
                    x,z,_=sim.visual_pose(actor);view.focus=__import__('ursina').Vec3(x,0,z);view.set_camera()
            view.sync(sim)
            with sim.timings.measure('ui'):ui.sync()
            view.show_selection(sim, ui.selected)
            if view.last_aspect != window.aspect_ratio:
                view.fit()
            self.frames += 1
            if args.smoke_recovery:recovery_checks.step(self.frames)
            if args.smoke_capacity or args.smoke_layout:capacity_checks.step()
            if args.smoke_behaviour:
                if self.frames==20:
                    assert sim.mode=='accident'
                    scenario('Evening/night')
                    for _ in range(1200):sim.step()
                    v=next(v for v in sim.vehicles if v.driver.kind=='Drunk')
                    sim.paused=True
                    x,z,_=sim.pose(v)
                    view.focus=__import__('ursina').Vec3(x,0,z)
                    view.zoom(95-__import__('ursina').camera.fov);view.set_camera()
                    ui.set_selection('vehicle',v.id)
                elif self.frames==40:
                    screenshot('driver-revision-inspector.png')
                    from traffic.simulation import Vehicle
                    from traffic.profiles import Driver,VehicleSpec
                    view.clear_cars();sim.reset(target=0)
                    a=Vehicle(1,('01>02',),3,0,speed=2,driver=Driver(kind='Drunk',subgroup='higher_risk',
                        reaction=0,gap=.7,speed_factor=1.4,overtake=1))
                    b=Vehicle(2,('01>02',),10.3,0,speed=.5,spec=VehicleSpec(cruise=.5))
                    sim.vehicles=[a,b]
                    for v in sim.vehicles:
                        sim.metrics.enter(v,sim.network);sim.behaviour_audit.admit(v)
                    from traffic.overtaking import base_position,valid
                    for _ in range(300):
                        sim.step()
                        assert all(valid(sim,v) for v in sim.vehicles)
                        if a.manoeuvre and base_position(sim,a)[2]>2.5:break
                    assert a.passing_state=='move_out'
                    sim.paused=True
                    x,z,_=sim.pose(a)
                    view.focus=__import__('ursina').Vec3(x,0,z)
                    view.zoom(65-__import__('ursina').camera.fov);view.set_camera()
                    ui.set_selection('vehicle',a.id)
                elif self.frames==60:
                    screenshot('driver-revision-pass.png')
                    sim.paused=False
                    for _ in range(600):
                        sim.step()
                        if sim.behaviour_audit.passing['completions']:break
                    assert sim.behaviour_audit.passing['completions']==1
                    assert not sim.incidents.records
                    sim.paused=True
                elif self.frames==80:
                    screenshot('driver-revision-return.png')
                    print('Behaviour GUI passed: accident mode, individual traits/perception, actual-city lane change and return.')
                    application.quit()
            if args.smoke_m4:
                if self.frames==20:
                    sim.mode='accident'
                    scenario('Evening/night')
                    sim.set_global(15)
                    ui.slider.value=15
                    for signal in sim.signals.values():signal.active_green=15
                    for _ in range(60*30):sim.step()
                    assert sim.incidents.active>0
                    sim.paused=True
                    r=next(r for r in sim.incidents.records if r['cleared'] is None)
                    self.incident_id=r['id']
                    view.focus=__import__('ursina').Vec3(r['location'][0],0,r['location'][1])
                    view.zoom(85-__import__('ursina').camera.fov)
                    view.set_camera()
                    ui.set_selection('incident',r['id'])
                elif self.frames==40:
                    screenshot('milestone4-incident.png')
                    r=sim.incidents.records[self.incident_id-1]
                    ui.set_selection('vehicle',next(iter(r['vehicles'])))
                elif self.frames==55:
                    screenshot('milestone4-wreck.png')
                    sim.overlay='Road usage'
                    view.home()
                elif self.frames==75:
                    screenshot('milestone4-usage.png')
                    sim.overlay='Accidents'
                    ui.set_selection('incident',self.incident_id)
                elif self.frames==95:
                    screenshot('milestone4-accidents.png')
                    window.size=(1000,720)
                    view.home()
                elif self.frames==115:
                    screenshot('milestone4-resized.png')
                    assert sim.elapsed==30
                    reset()
                    assert not sim.incidents.records and sim.overlay=='None'
                    sim.paused=True
                    sim.overlay='Accidents'
                elif self.frames==135:
                    screenshot('milestone4-zero.png')
                    print('Milestone 4 GUI smoke passed: natural incident, wreck inspector, overlays, resize, pause/reset, zero map.')
                    application.quit()
            if args.smoke_test:
                if self.frames == 20:
                    ui.pause.on_click()
                    self.frozen = repr((sim.vehicles, sim.signals, sim.elapsed))
                elif self.frames == 30:
                    assert self.frozen == repr((sim.vehicles, sim.signals, sim.elapsed))
                    ui.slider.value = 120
                    assert all(s.requested_green == 120 for s in sim.signals.values())
                    assert all(s.active_green == 30 for s in sim.signals.values())
                    ui.set_selection('junction', '12')
                    ui.local.value = 15
                    assert sim.signals['12'].override == 15
                    ui.slider.value = 90
                    assert sim.signals['12'].requested_green == 15
                    ui.remove_override()
                    assert sim.signals['12'].requested_green == 90
                    ui.set_selection('junction', '11')
                    assert not ui.local.enabled
                elif self.frames == 40:
                    reset()
                    assert not sim.paused and sim.elapsed == 0
                    assert sim.global_green == ui.slider.value == 30
                    assert all(s.override is None for s in sim.signals.values())
                    assert len(view.cars) == len(sim.vehicles) == 40
                    assert view.home_mode
                elif self.frames == 100:
                    ui.set_selection('junction', '12')
                elif self.frames == 120:
                    screenshot('milestone3.png')
                    view.zoom(-240)
                    view.focus = __import__('ursina').Vec3(-32,0,-32)
                    view.set_camera()
                    ui.set_selection('junction','11')
                elif self.frames == 145:
                    screenshot('milestone3-detail.png')
                    window.size=(1000,720)
                    view.home()
                    ui.set_selection('junction','12')
                elif self.frames == 175:
                    screenshot('milestone3-resized.png')
                    assert abs(window.aspect_ratio-1000/720)<.01
                    assert ui.root.x >= -window.aspect_ratio/2
                    assert ui.pause.x+.06 <= window.aspect_ratio/2
                    window.size=(1440,900)
                    inspect_when(lambda v:v.spec.kind == 'Truck' and sim.network.paths[v.path_id].kind == 'roundabout' and 5<v.s<sim.network.paths[v.path_id].length-5)
                elif self.frames == 185:
                    screenshot('milestone3-truck-turn.png')
                    inspect_when(lambda v:v.spec.kind == 'Bus' and v.dwell>1)
                elif self.frames == 195:
                    screenshot('milestone3-bus-stop.png')
                    ui.population.value=20
                    scenario('Morning commute')
                    assert sim.target == len(sim.vehicles) == 20
                    assert sim.clock_label == '07:30:00'
                    assert sim.supervisor.interventions == sim.supervisor.violations == 0
                    ui.setup.enabled=True
                elif self.frames == 210:
                    screenshot('milestone3-scenario.png')
                    print('GUI smoke passed: signals, reset, resize, truck roundabout turn, bus dwell, scenario and target preservation.')
                    application.quit()

        def input(self, key):
            if key == 'space':
                ui.toggle()
            elif key == 'r':
                reset()
            elif key == 'h':
                home()
            elif key=='escape':ui.follow_id=None
            elif not ui.blocks_pointer() and key in ('scroll up', 'scroll down'):
                ui.follow_id=None
                view.zoom(-12 if key == 'scroll up' else 12)

    Controller()
    app.run()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
