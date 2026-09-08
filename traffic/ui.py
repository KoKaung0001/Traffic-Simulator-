from collections import Counter
from textwrap import fill
import math
from traffic.demand import SCENARIOS
from ursina import Entity, Text, Button, Slider, camera, color, mouse, window


class Interface:
    def __init__(self, sim, reset, home, scenario):
        self.sim, self.selected = sim, None
        self.suppress = False
        self.setup = Entity(parent=camera.ui,z=-.3,enabled=False)
        Entity(parent=self.setup,model='quad',origin=(-.5,.5),position=(-.015,.30,.1),scale=(.34,.67),color=color.hex('#203742'),collider='box')
        Text(parent=self.setup,text='SCENARIO / resets run',y=.275,scale=.9,color=color.hex('#ffdc8c'))
        for i,name in enumerate(SCENARIOS):
            Button(parent=self.setup,text=name,position=(.15,.215-i*.06),scale=(.30,.045),color=color.hex('#42666c'),on_click=lambda name=name:scenario(name))
        Text(parent=self.setup,text='Scenario keeps your target.',y=-.09,scale=.75,color=color.hex('#a5c6c9'))
        self.mode_button=Button(parent=self.setup,text='',position=(.15,-.17),scale=(.30,.045),color=color.hex('#42666c'),on_click=lambda:self.switch_mode(scenario))
        self.mix=Text(parent=self.setup,y=-.21,scale=.65,color=color.hex('#edf2e5'))
        self.header = Entity(parent=camera.ui, model='quad', color=color.hex('#203742'), y=.415, z=-.1, scale=(window.aspect_ratio,.17), collider='box')
        self.title = Text(parent=camera.ui,text='CROSSING / CITY',y=.478,z=-.2,scale=1.25,color=color.hex('#ffdc8c'))
        self.summary = Text(parent=camera.ui,y=.435,z=-.2,scale=.76,color=color.hex('#edf2e5'))
        self.pause = Button(parent=camera.ui,text='Pause',y=.459,z=-.2,scale=(.12,.045),color=color.hex('#42666c'),on_click=self.toggle)
        self.reset_button = Button(parent=camera.ui,text='Reset',y=.396,z=-.2,scale=(.12,.045),color=color.hex('#42666c'),on_click=reset)
        self.home_button = Button(parent=camera.ui,text='Home view',y=.396,z=-.2,scale=(.16,.045),color=color.hex('#42666c'),on_click=home)
        self.setup_button=Button(parent=camera.ui,text='Run setup',y=.459,z=-.2,scale=(.16,.045),color=color.hex('#42666c'),on_click=self.toggle_setup)
        self.root = Entity(parent=camera.ui,z=-.2)
        self.controls = Entity(parent=self.root,model='quad',origin=(-.5,.5),position=(-.015,.31,.1),scale=(.34,.23),color=color.hex('#203742'),collider='box')
        self.label('SIGNAL EXPERIMENT',.285,1,'#ffdc8c')
        self.population_label=Text(parent=self.setup,y=.025,scale=.9,color=color.hex('#edf2e5'))
        self.population = Slider(parent=self.setup,min=0,max=100,default=40,step=1,dynamic=True,position=(.01,-.035),scale=.56,text='')
        self.population.on_value_changed = lambda: self.sim.set_target(self.population.value)
        self.global_label = self.label('',.24)
        self.slider = Slider(parent=self.root,min=5,max=120,default=30,step=1,dynamic=True,position=(.01,.17),scale=.56,text='')
        self.slider.on_value_changed = lambda: self.sim.set_global(self.slider.value)
        self.label('WASD pan / wheel zoom\nSpace pause / R reset / H home',.115,.76,'#a5c6c9')
        self.selection_panel = Entity(parent=self.root,model='quad',origin=(-.5,.5),position=(-.015,-.09,.1),scale=(.34,.39),color=color.hex('#203742'),collider='box')
        self.inspector = self.label('',-.11,.83)
        Entity(parent=self.root,model='quad',origin=(-.5,.5),position=(-.015,.075,.1),
               scale=(.34,.16),color=color.hex('#203742'),collider='box')
        for i,name in enumerate(('None','Road usage','Accidents')):
            Button(parent=self.root,text=name,position=(.04+i*.113,.04),scale=(.108,.035),text_size=.7,color=color.hex('#42666c'),on_click=lambda name=name:setattr(self.sim,'overlay',name))
        self.legend=self.label('',.01,.65)
        for i,tint in enumerate(('#42666c','#b9b551','#e67946','#ce4144')):
            Entity(parent=self.root,model='quad',position=(.035+i*.075,-.066),scale=(.065,.009),color=color.hex(tint))
        self.local = Slider(parent=self.root,min=5,max=120,default=30,step=1,dynamic=True,position=(.01,-.36),scale=.56,text='')
        self.local.on_value_changed = self.request_local
        self.use_global = Button(parent=self.root,text='Use global timing',position=(.15,-.431),scale=(.29,.045),color=color.hex('#42666c'),on_click=self.remove_override)
        self.sync()

    def switch_mode(self,scenario):
        self.sim.mode='supervised' if self.sim.mode=='accident' else 'accident'
        scenario(self.sim.scenario)

    def label(self, text, y, scale=.91, tint='#edf2e5'):
        return Text(parent=self.root,text=text,position=(0,y),scale=scale,color=color.hex(tint))

    def toggle_setup(self):
        self.setup.enabled=not self.setup.enabled

    def toggle(self):
        self.sim.paused = not self.sim.paused

    def blocks_pointer(self):
        return (any(s.knob.dragging for s in (self.slider,self.population,self.local))
                or mouse.y > .325 or (self.setup.enabled and mouse.x > window.aspect_ratio/2-.37 and -.38<mouse.y<.31) or (mouse.x < -window.aspect_ratio/2+.365 and mouse.y < .32))

    def select(self, kind, key):
        if self.blocks_pointer():
            return
        self.set_selection(kind,key)

    def set_selection(self, kind, key):
        self.selected = (kind,key)
        if kind == 'junction' and key in self.sim.signals:
            self.suppress=True
            self.local.value=self.sim.signals[key].requested_green
            self.suppress=False
        self.sync()

    def request_local(self):
        if not self.suppress and self.selected and self.selected[0] == 'junction' and self.selected[1] in self.sim.signals:
            self.sim.set_local(self.selected[1],self.local.value)

    def remove_override(self):
        if self.selected and self.selected[1] in self.sim.signals:
            self.sim.set_local(self.selected[1])
            self.suppress=True
            self.local.value=self.sim.global_green
            self.suppress=False

    def reset_controls(self):
        self.selected=None
        self.population.value=40
        self.slider.value=30
        self.suppress=True
        self.local.value=30
        self.suppress=False

    def sync(self):
        left=-window.aspect_ratio/2+.03
        self.header.scale_x=window.aspect_ratio
        self.title.x=self.summary.x=left
        self.root.x=left
        self.setup.x=window.aspect_ratio/2-.34
        self.setup_button.x=window.aspect_ratio/2-.25
        self.pause.x=self.reset_button.x=window.aspect_ratio/2-.085
        self.home_button.x=window.aspect_ratio/2-.25
        self.pause.text='Resume' if self.sim.paused else 'Pause'
        types=Counter(v.spec.kind for v in self.sim.vehicles)
        drivers=Counter(v.driver.kind for v in self.sim.vehicles)
        self.mix.text=(f'Sedan {types["Sedan"]} / Truck {types["Truck"]} / Bus {types["Bus"]}\n'
                       f'Normal {drivers["Normal"]} / Newbie {drivers["Newbie"]} / Drunk {drivers["Drunk"]}\n'
                       f'Pending {self.sim.pending} / tickets {len(self.sim.queued)}\n'
                       +fill(self.sim.spawn_status,38)+'\n'
                       +('Paused: resume to admit.' if self.sim.paused else
                         'Blocked? Wait for clearance or lower target.' if self.sim.pending else 'All requested vehicles admitted.'))
        m=self.sim.metrics.values(self.sim)
        rate=m['accidents_per_1000_vehicle_km']
        rate='N/A' if rate is None else f'{rate:.1f}'
        self.summary.text=(f'{self.sim.clock_label} | {self.sim.elapsed:.1f}s | {self.sim.scenario} | {self.sim.mode}\n'
            f'Active {m["active"]}/{m["target"]} ({m["on_road"]} on road + {m["wrecks"]} wrecks) | Pending {self.sim.pending} | Trips {m["completed"]}\n'
            f'Accidents {m["accidents"]} | Active incidents {m["active_incidents"]} | Involved {m["involved"]} | {rate} / 1000 veh-km\n'
            f'Distance {m["distance_km"]:.2f} veh-km | Wait {m["waiting_vehicle_s"]:.0f} veh-s ({m["waiting_fraction"]:.0%}) | Dwell {m["bus_dwell_vehicle_s"]:.0f} veh-s\n'
            f'Safety {self.sim.supervisor.interventions} | Signal attempts {self.sim.supervisor.violations} | Wait includes red/wrecks; excludes bus dwell')
        self.mode_button.text=f'Mode: {self.sim.mode} / reset'
        if self.sim.overlay=='None':
            self.legend.text='Overlay off | cumulative since reset'
        elif self.sim.overlay=='Road usage':
            self.legend.text=f'Lane entries | since reset ({self.sim.elapsed:.0f}s)\nFixed bins: 0 / 1-24 / 25-49 / 50+\nInitial entries included; no connectors'
        else:
            self.legend.text=f'Incidents / 16m cell | since reset ({self.sim.elapsed:.0f}s)\nFixed bins: 0 / 1-2 / 3-4 / 5+\nZero is transparent; origins persist'
        self.population_label.text=f'Target population: {self.sim.target}'
        pending=sum(s.active_green != s.requested_green for s in self.sim.signals.values())
        self.global_label.text=f'Global green: {self.sim.global_green:.0f}s\nPending at {pending} signals'
        self.local.enabled=self.use_global.enabled=False
        if not self.selected:
            self.inspector.text='SELECT & INSPECT\n\nClick a vehicle or junction.\nGold outline marks selection.'
            return
        kind,key=self.selected
        if kind == 'vehicle':
            v=next((v for v in self.sim.vehicles if v.id == key),None)
            if v:
                reason=fill(v.reason.replace('_',' '),31)
                safety=fill(v.intervention.replace('_',' ') or 'None',31)
                bus=f'\nBus: {v.stop_status}' if v.spec.kind == 'Bus' else ''
                fmt=lambda n:f'{n:.1f}' if math.isfinite(n) else 'clear'
                control=fill(v.control_reason.replace('_',' '),34) if v.driver.kind!='Normal' else 'normal safety control'
                self.inspector.text=(f'{v.spec.kind} #{v.id} / {v.driver.kind}\nRisk: {v.driver.subgroup}\n{v.origin} > {v.destination}\n'
                                     f'Speed {v.speed:.1f} / desired {v.desired_speed:.1f} m/s\n'
                                     f'Gap actual / seen: {fmt(v.actual_gap)} / {fmt(v.perceived_gap)} m\n'
                                     f'Reaction {v.driver.reaction:.2f}s | Preferred {v.driver.gap:.1f}m\n'
                                     f'Episode: {v.episode}\nProlog: {v.action}\n{reason}\n'
                                     f'Control: {control}\nExecuted: {v.executed}\n'
                                     f'Passing: {v.passing_state}\nSafety: {safety}{bus}')
                if v.incident is not None:
                    r=self.sim.incidents.records[v.incident-1]
                    self.inspector.text+=(f'\nIncident #{r["id"]} | {len(r["vehicles"])} vehicles\n'
                        f'Start {r["start"]:.1f}s / clear {r["clear_at"]:.1f}s')
            else:
                removal=next((r for r in reversed(self.sim.removals) if r['id']==key),None)
                self.inspector.text=(f'VEHICLE #{key}\n'+
                    (f'{removal["reason"].replace("_"," ")}\nAt {removal["time"]:.1f}s\nDestination: {removal["destination"]}'
                     if removal else 'Not active in this run.')+'\nSelect another vehicle.')

        elif kind == 'incident':
            r=self.sim.incidents.records[key-1] if key<=len(self.sim.incidents.records) else None
            if r:
                details='\n'.join(f'#{vid} {data["type"]} / {data["profile"]}' for vid,data in list(r['vehicles'].items())[:5])
                self.inspector.text=(f'INCIDENT #{key}\nStart {r["start"]:.1f}s\nLocation {r["location"][0]:.1f}, {r["location"][1]:.1f} m\n'
                    f'Clear at {r["clear_at"]:.1f}s\n{details}\nPhysical contact recorded.\nSelect a wreck for its actions.')
        elif key not in self.sim.signals:
            self.inspector.text=f'ROUNDABOUT {key}\n\nCounterclockwise circulation\nYield to circulating traffic\nNo signal timing controls'
        else:
            s=self.sim.signals[key]
            mode='Global' if s.override is None else 'Local override'
            pending=f'{s.requested_green:.0f}s next green' if s.requested_green != s.active_green else 'None'
            self.inspector.text=f'JUNCTION {key} / {mode}\n{s.phase}\nRemaining: {s.remaining:.1f}s\nActive green: {s.active_green:.0f}s\nPending: {pending}\nLocal green: {self.local.value:.0f}s'
            self.local.enabled=self.use_global.enabled=True
