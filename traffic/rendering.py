"""Procedural assets. All scene geometry uses the simulation's metre scale."""
from ursina import Entity, color, Vec3, AmbientLight, DirectionalLight, camera, scene
from ursina.models.procedural.cylinder import Cylinder
import math
from copy import deepcopy
from .demand import ACCESS, BUS_STOPS

PALETTE = ['#ef705d', '#5eaaca', '#f4c65b', '#9a83cb', '#f4ece0', '#65b99d']


def cube(parent=None, pos=(0, 0, 0), scale=(1, 1, 1), tint='#ffffff', **kwargs):
    return Entity(parent=parent or scene, model='cube', position=pos, scale=scale,
                  color=color.hex(tint), **kwargs)


def capped_disk(segments=64):
    """Closed cylinder, unlike Ursina's open-ended procedural pipe."""
    from ursina import Mesh
    vertices, normals, triangles = [], [], []
    def triangle(points, normal):
        i=len(vertices)
        vertices.extend(points)
        normals.extend([normal]*3)
        triangles.append((i,i+1,i+2))
    for i in range(segments):
        a,b=i*math.tau/segments,(i+1)*math.tau/segments
        x,z=.5*math.cos(a),.5*math.sin(a)
        xx,zz=.5*math.cos(b),.5*math.sin(b)
        triangle([(0,1,0),(xx,1,zz),(x,1,z)],(0,1,0))
        triangle([(0,0,0),(x,0,z),(xx,0,zz)],(0,-1,0))
        normal=(math.cos((a+b)/2),0,math.sin((a+b)/2))
        triangle([(x,0,z),(x,1,z),(xx,0,zz)],normal)
        triangle([(xx,0,zz),(x,1,z),(xx,1,zz)],normal)
    return Mesh(vertices=vertices,triangles=triangles,normals=normals)


class CityView:
    def __init__(self, network, select):
        from ursina.shaders import lit_with_shadows_shader
        from ursina.shaders import unlit_shader
        from .lighting import make_shader,Lighting
        from ursina import Mesh, Text
        from .network import RADIUS, VECTORS
        existing = set(scene.entities)
        Entity.default_shader = make_shader()
        self.network, self.select = network, select
        self.cars, self.lamps = {}, {}
        self.markers={}
        self.heat=[]
        self.heat_key=None
        self.street_bulbs=[]
        self.street_positions=[]
        self.wheel_mesh = Cylinder(resolution=12, start=-.5)
        self.disk = capped_disk()
        cube(pos=(0, -1, 0), scale=(network.extent*2, 2, network.extent*2), tint='#8fb77a')
        drawn = set()
        for lane in network.lanes.values():
            edge = tuple(sorted((lane.source, lane.target)))
            if edge in drawn:
                continue
            drawn.add(edge)
            a, b = network.nodes[lane.source], network.nodes[lane.target]
            length = math.dist(a, b)
            dx, dz = b[0]-a[0], b[1]-a[1]
            root = Entity(position=((a[0]+b[0])/2, 0, (a[1]+b[1])/2),
                          rotation_y=math.degrees(math.atan2(dx,dz)))
            cube(root, (0, .02, 0), (10, .15, length), '#424b59')
            # Mark only lane segments, outside junction connector footprints.
            for t in range(18, int(length)-17, 6):
                cube(root, (0, .13, t-length/2), (.16, .04, 2.6), '#f5dc91')
            for i,t in enumerate(range(22,int(length)-17,24)):
                fraction=t/length;side=1 if i%2 else -1
                self.streetlamp(a[0]+dx*fraction+side*dz/length*7.3,
                                a[1]+dz*fraction-side*dx/length*7.3)
        for j in network.junctions.values():
            x, z = j.position
            if j.kind == 'signal':
                tile = cube(pos=(x, .06, z), scale=(10, .16, 10), tint='#424b59', collider='box')
            else:
                tile = Entity(model=deepcopy(self.disk), position=(x,.12,z), scale=(28,.15,28), color=color.hex('#424b59'), collider='box')
                Entity(model=deepcopy(self.disk), position=(x,.25,z), scale=(12,.6,12), color=color.hex('#ded4b9'))
                Entity(model=deepcopy(self.disk), position=(x,.85,z), scale=(10,.2,10), color=color.hex('#77a56b'))
                self.tree(x,z)
            # Entry/exit pavement follows the very same sampled connectors.
            for path in network.connectors.values():
                if path.junction == j.id:
                    vertices, triangles = [], []
                    for i, point in enumerate(path.points):
                        other = path.points[min(i+1,len(path.points)-1)] if i < len(path.points)-1 else path.points[i-1]
                        sign = 1 if i < len(path.points)-1 else -1
                        vx, vz = (other[0]-point[0])*sign, (other[1]-point[1])*sign
                        norm = max(.0001,(vx*vx+vz*vz)**.5)
                        width=2.6+math.sin(math.pi*i/(len(path.points)-1))
                        vertices.extend([(point[0]+vz/norm*width,.17,point[1]-vx/norm*width),
                                         (point[0]-vz/norm*width,.17,point[1]+vx/norm*width)])
                        if i:
                            k=i*2
                            triangles.extend([(k-2,k,k-1),(k-1,k,k+1)])
                    Entity(model=Mesh(vertices=vertices, triangles=triangles, normals=[(0,1,0)]*len(vertices), static=True), color=color.hex('#424b59'), double_sided=True)
            tile.on_click = lambda jid=j.id: self.select('junction', jid)
            for arm in j.approaches:
                d = VECTORS[arm]
                yaw = math.degrees(math.atan2(-d[0],-d[1]))
                root = Entity(position=(x,0,z), rotation_y=yaw)
                if j.kind == 'signal':
                    cube(root,(2.5,.22,-RADIUS),(4.6,.04,.35),'#f5edcf')
                    cube(root,(6,2.5,-RADIUS),(.25,5,.25),'#3b4951')
                    cube(root,(6,5.1,-RADIUS),(1,2.4,.65),'#293942')
                    lamps={}
                    for light, y in (('red',5.8),('amber',5.1),('green',4.4)):
                        lamps[light]=Entity(parent=root, model='sphere',position=(6,y,-RADIUS-.38),scale=(.5,.5,.12),shader=unlit_shader)
                    self.lamps[(j.id,arm)] = lamps
                else:
                    for offset in (1,2.5,4):
                        Entity(parent=root,model=Mesh(vertices=[(offset-.5,.23,-20.7),(offset+.5,.23,-20.7),(offset,.23,-19.7)],triangles=[(0,1,2)]),color=color.hex('#f5edcf'),double_sided=True)
        names = [('SCHOOL','#eac66d',5),('UNIVERSITY','#eac66d',8),('HOSPITAL','#d9ece6',7),
                 ('APARTMENTS','#d8a4a0',10),('DOWNTOWN','#a7cbd0',16),('BANK / OFFICES','#b8b2ce',9),
                 ('DINING / PUB','#e5aa98',5),('CITY PARK','#79a676',0),('TRANSIT / DEPOT','#9aafbe',5)]
        centres=[(a+b)/2 for a,b in zip(network.grid,network.grid[1:])]
        plots=[(centres[i%3],centres[i//3],*spec) for i,spec in enumerate(names)]
        if network.peripheral:
            outer=network.grid[-1]+32
            frontage=[-outer,*centres,outer]
            labels={(-outer,outer):'BELT HOMES',(-outer,-outer):'BELT OFFICES',
                    (outer,-outer):'BELT PUB',(outer,outer):'BELT SHOPS'}
            plots += [(x,z,labels.get((x,z),'OUTER HOMES'),'#d8a4a0',7) for x in frontage for z in frontage
                      if abs(x)==outer or abs(z)==outer]
        for index,(x,z,name,tint,height) in enumerate(plots):
            outline=[(-24,-10),(-10,-24),(10,-24),(24,-10),(24,10),(10,24),(-10,24),(-24,10)]
            vertices=[(x,.3,z)]+[(x+a,.3,z+b) for a,b in outline]
            Entity(model=Mesh(vertices=vertices,triangles=[(0,i+1,(i+1)%8+1) for i in range(8)]),color=color.hex('#ded4b9'),double_sided=True)
            cube(pos=(x,.4,z),scale=(31,.15,31),tint='#9ac180')
            if height:
                self.building(x-7,z+4,height,tint)
                self.building(x+7,z+4,max(4,height-3),tint if index in (0,1,2) else PALETTE[index%6])
                if name == 'HOSPITAL':
                    cube(pos=(x-7,height+1,z+4),scale=(1,.2,5),tint='#db6566')
                    cube(pos=(x-7,height+1.01,z+4),scale=(5,.2,1),tint='#db6566')
                if name == 'UNIVERSITY':
                    for column in (-10,-7,-4):
                        cube(pos=(x+column,3,z-1),scale=(.65,5,.65),tint='#f3e5c5')
                if name == 'TRANSIT / DEPOT':
                    for offset in (-9,-6,-3,4,7,10):
                        cube(pos=(x+offset,2,z-.6),scale=(1.8,2.5,.1),tint='#466878')
                if name in ('DINING / PUB','BELT PUB'):
                    cube(pos=(x-7,3,z-2),scale=(10,.5,3),tint='#edbd65')
            else:
                for offset in (-8,0,8):
                    cube(pos=(x+offset,1,z),scale=(4,.5,1.5),tint='#a57e53')
                Entity(model=deepcopy(self.disk),position=(x,.6,z+8),scale=(9,.5,9),color=color.hex('#68b8c6'))
            # Low block signage, repeated trees, bushes and lamps stay off lanes.
            cube(pos=(x,1,z-12),scale=(23,1.8,.3),tint='#42666c')
            Text(parent=scene,text=name,position=(x,1.4,z-12.3),origin=(0,0),scale=55,color=color.hex('#fff0cf'),double_sided=True)
            for tx,tz in ((-17,0),(17,0),(-8,17),(8,17)):
                self.tree(x+tx,z+tz)
            for tx in (-9,-6,6,9):
                Entity(model='sphere',position=(x+tx,1,z-17),scale=(2.4,1.8,2.4),color=color.hex('#538c68'))
            for tx in (-19,19):
                self.streetlamp(x+tx,z-7)
        for access in network.access.values():
            x,z,yaw=network.paths[access.lane].pose(access.s)
            root=Entity(position=(x,0,z),rotation_y=yaw)
            tint='#69c7dc' if access.name == 'Terminal' else '#efcb77'
            for side in (-1,1):
                cube(root,(side*1.4,.24,0),(.12,.04,10),tint)
            cube(root,(3.8,1.6,0),(.16,3.2,.16),'#42666c')
            cube(root,(3.8,3,0),(5,1,.25),'#42666c')
            Text(parent=root,text=access.name,position=(3.8,3, -.16),origin=(0,0),scale=28,color=color.hex('#ffedbc'),double_sided=True)
        for lane,(name,s) in BUS_STOPS.items():
            x,z,yaw=network.paths[lane].pose(s)
            root=Entity(position=(x,0,z),rotation_y=yaw)
            cube(root,(3.7,.35,1),(1.6,.35,9),'#67b4c4')
            cube(root,(3.7,2.2,4),(.18,4.4,.18),'#42666c')
            cube(root,(3.7,4.1,4),(1.5,1.5,.2),'#67b4c4')
            Text(parent=root,text='B',position=(3.7,4.1,3.85),origin=(0,0),scale=40,color=color.white,double_sided=True)
        # Batch immutable scenery, preserving vertex colours and world normals.
        static = Entity()
        lamps = {lamp for lights in self.lamps.values() for lamp in lights.values()}|set(self.street_bulbs)
        for entity in list(scene.entities):
            if entity not in existing and entity is not static and entity not in lamps and not isinstance(entity,Text) and entity.model and not entity.collider:
                entity.world_parent = static
        static.combine(include_normals=True)
        static.model.normals = [Vec3(*n).normalized() for n in static.model.normals]
        static.model.generate()
        static.double_sided = True
        self.lighting=Lighting(self.street_positions,self.street_bulbs,network.extent)
        camera.orthographic = True
        self.highlight = Entity(model='wireframe_cube',color=color.hex('#ffdb77'),shader=unlit_shader,enabled=False)
        self.home()

    def building(self, x, z, height, tint):
        root = Entity(position=(x, .5, z))
        cube(root, (0, height / 2, 0), (9, height, 9), tint)
        cube(root, (0, height + .35, 0), (10, .7, 10), '#657d88')
        cube(root, (0, .25, 0), (10, .5, 10), '#eee2c6')
        for side in (-1, 1):
            for offset in (-2.7, 0, 2.7):
                for y in range(2, height, 3):
                    cube(root, (offset, y, side * 4.52), (1.5, 1.8, .08), '#466878')
                    cube(root, (side * 4.52, y, offset), (.08, 1.8, 1.5), '#466878')

    def streetlamp(self,x,z):
        from ursina.shaders import unlit_shader
        cube(pos=(x,3.5,z),scale=(.22,7,.22),tint='#42666c')
        cube(pos=(x,7.1,z),scale=(1.5,.25,1.5),tint='#344653')
        self.street_bulbs.append(cube(pos=(x,7.3,z),scale=(1.05,.25,1.05),tint='#ffe0a0',shader=unlit_shader))
        self.street_positions.append((x,z))

    def tree(self, x, z):
        cube(pos=(x, 1.4, z), scale=(.7, 2.2, .7), tint='#9b7753')
        Entity(model='sphere', position=(x, 3.3, z), scale=(4, 4.6, 4), color=color.hex('#43896b'))
        Entity(model='sphere', position=(x + .6, 4.2, z), scale=(2.8, 2.8, 2.8), color=color.hex('#71a36b'))

    def sedan(self, v):
        if v.spec.kind != 'Sedan':
            return self.long_vehicle(v)
        root = Entity()
        body = cube(root, (0, .8, 0), (1.8, .65, 4.4), PALETTE[v.tint], collider='box')
        body.on_click = lambda: self.select('vehicle', v.id)
        cube(root, (0, 1.3, -.15), (1.5, .65, 2.1), PALETTE[v.tint])
        cube(root, (0, 1.4, .93), (1.35, .42, .06), '#294d64')
        cube(root, (0, 1.4, -1.23), (1.35, .42, .06), '#294d64')
        for side in (-1, 1):
            cube(root, (side * .76, 1.4, -.15), (.04, .42, 1.7), '#294d64')
            for z in (-1.35, 1.35):
                Entity(parent=root, model=deepcopy(self.wheel_mesh), position=(side * .775, .48, z), rotation_z=90, scale=(.72, .25, .72), color=color.hex('#26333c'))
            cube(root, (side * .58, .86, 2.22), (.4, .22, .06), '#fff0bd')
            cube(root, (side * .58, .86, -2.22), (.4, .22, .06), '#c4494e')
        root.combine(ignore=[body],include_normals=True)
        root.model.normals = [Vec3(*n).normalized() for n in root.model.normals]
        root.model.generate()
        root.scale=(v.spec.width/1.8,1,v.spec.length/4.4)
        return root

    def long_vehicle(self,v):
        root=Entity()
        length,width=v.spec.length,v.spec.width
        tint='#e8c65b' if v.spec.kind == 'Bus' else PALETTE[v.tint]
        body=cube(root,(0,1.4,0),(width,2.3,length),tint,collider='box')
        body.on_click=lambda:self.select('vehicle',v.id)
        if v.spec.kind == 'Truck':
            body.scale_y=.6
            body.y=.9
            cube(root,(0,2,-.9),(width,2.4,length-2.1),'#dfdcc8')
            cube(root,(0,1.7,length/2-1),(width,2.1,1.9),tint)
            cube(root,(0,2.1,length/2+.02),(width-.2,.9,.06),'#294d64')
            for side in (-1,1):
                cube(root,(side*(width/2+.02),2.1,length/2-1),(.05,.8,1.4),'#294d64')
        else:
            cube(root,(0,2.75,-.5),(1.6,.3,2.5),'#eee2c6')
            cube(root,(0,2,length/2+.03),(width-.2,1,.05),'#294d64')
            for side in (-1,1):
                for z in (-3,-1.5,0,1.5,3):
                    cube(root,(side*(width/2+.03),2,z),(.06,.9,1.2),'#294d64')
            cube(root,(width/2+.05,1.4,2.8),(.08,1.8,1),'#406478')
        for side in (-1,1):
            for z in (-length*.32,length*.32):
                Entity(parent=root,model=deepcopy(self.wheel_mesh),position=(side*(width/2-.16),.58,z),rotation_z=90,scale=(1,.32,1),color=color.hex('#26333c'))
            cube(root,(side*.7,1.05,length/2+.06),(.4,.25,.08),'#fff0bd')
        root.combine(ignore=[body],include_normals=True)
        root.model.normals=[Vec3(*n).normalized() for n in root.model.normals]
        root.model.generate()
        return root

    def sync(self, sim):
        from ursina import destroy
        from ursina.shaders import unlit_shader
        self.lighting.sync(sim,self.focus)
        ids = {v.id for v in sim.vehicles}
        for vid in list(self.cars):
            if vid not in ids:
                destroy(self.cars.pop(vid))
        for v in sim.vehicles:
            if v.id not in self.cars:
                self.cars[v.id] = self.sedan(v)
                car=self.cars[v.id];car.bulbs=[]
                for side in (-1,1):
                    for direction,tint in ((1,'#fff0bd'),(-1,'#ee4545')):
                        # Sedan root is scaled to spec; all nominal sedans use its dimensions.
                        car.bulbs.append(cube(car,(side*v.spec.width*.32,.95,direction*(v.spec.length/2+.08)),
                            (.38,.22,.1),tint,shader=unlit_shader))
            for bulb in self.cars[v.id].bulbs:bulb.enabled=self.lighting.day<.99
            x, z, yaw = sim.pose(v)
            self.cars[v.id].position = (x, .22, z)
            self.cars[v.id].rotation_y = yaw
            self.cars[v.id].color=color.hex('#b97e73' if v.crashed else '#ffffff')
        active={r['id']:r for r in sim.incidents.records if r['cleared'] is None}
        for iid in list(self.markers):
            if iid not in active: destroy(self.markers.pop(iid))
        for iid,r in active.items():
            if iid not in self.markers:
                x,z=r['location']
                marker=cube(pos=(x,4.5,z),scale=(1.8,1.8,1.8),tint='#ff9a57',rotation_y=45,
                    collider='box',shader=unlit_shader,on_click=lambda iid=iid:self.select('incident',iid))
                from ursina import Text
                Text(parent=marker,text=f'! {iid}',origin=(0,0),y=1.3,scale=2,billboard=True,color=color.white)
                self.markers[iid]=marker
        self.sync_heat(sim)
        colours = {'red': '#ff6057', 'amber': '#ffc95c', 'green': '#76ef9e'}
        for (jid, arm), lights in self.lamps.items():
            active = sim.signals[jid].light(arm)
            for name, lamp in lights.items():
                lamp.color = color.hex(colours[name] if name == active else '#263b3c')

    def sync_heat(self,sim):
        from ursina import destroy
        from ursina.shaders import unlit_shader
        key=(sim.overlay,tuple(sorted(sim.metrics.usage.items())),tuple(sorted(sim.incidents.cells.items())))
        if key==self.heat_key:return
        self.heat_key=key
        for entity in self.heat:destroy(entity)
        self.heat=[]
        palette=('#42666c','#b9b551','#e67946','#ce4144')
        if sim.overlay=='Road usage':
            for pid,p in sim.network.lanes.items():
                count=sim.metrics.usage[pid]
                level=0 if count==0 else (1 if count<25 else 2 if count<50 else 3)
                a,b=p.points[0],p.points[-1]
                self.heat.append(cube(pos=((a[0]+b[0])/2,.205,(a[1]+b[1])/2),
                    scale=(.85,.025,p.length),rotation_y=p.pose(0)[2],tint=palette[level],shader=unlit_shader))
        elif sim.overlay=='Accidents':
            # Empty cells are transparent: a blank map means zero incidents.
            for (x,z),count in sim.incidents.cells.items():
                level=1 if count<3 else 2 if count<5 else 3
                e=cube(pos=(x*16+8,.19,z*16+8),scale=(16,.018,16),tint=palette[level],shader=unlit_shader)
                e.color=color.rgba(e.color.r,e.color.g,e.color.b,.42)
                self.heat.append(e)

    def clear_cars(self):
        from ursina import destroy
        for car in self.cars.values():
            destroy(car)
        self.cars.clear()
        for marker in self.markers.values():destroy(marker)
        self.markers.clear()
        self.heat_key=None

    def show_selection(self, sim, selected):
        self.highlight.enabled = False
        if not selected:
            return
        kind, key = selected
        if kind == 'vehicle':
            v = next((v for v in sim.vehicles if v.id == key), None)
            if v:
                x,z,yaw = sim.pose(v)
                self.highlight.position = (x,1,z)
                self.highlight.scale = (v.spec.width+.8,3.4,v.spec.length+.8)
                self.highlight.rotation_y = yaw
                self.highlight.enabled = True
        elif kind=='incident' and key<=len(sim.incidents.records):
            x,z=sim.incidents.records[key-1]['location']
            self.highlight.position=(x,.6,z)
            self.highlight.scale=(8,.4,8)
            self.highlight.rotation_y=0
            self.highlight.enabled=True
        elif key in self.network.junctions:
            x,z = self.network.junctions[key].position
            self.highlight.position = (x,.5,z)
            self.highlight.scale = (32,.5,32)
            self.highlight.rotation_y = 0
            self.highlight.enabled = True

    def home(self):
        self.focus = Vec3(0,0,0)
        self.home_mode = True
        self.fit()
        self.set_camera()

    def fit(self):
        from ursina import window
        self.last_aspect = window.aspect_ratio
        if self.home_mode:
            camera.fov = max(345, 400 / max(.65,window.aspect_ratio-.37))
        camera.orthographic_lens.set_film_offset(-camera.fov*.16, camera.fov*.07)

    def set_camera(self):
        camera.position = self.focus + Vec3(190,265,-285)
        camera.look_at(self.focus)

    def pan(self, dx, dz):
        self.home_mode = False
        bound=self.network.extent-7
        self.focus.x = max(-bound,min(bound,self.focus.x+dx))
        self.focus.z = max(-bound,min(bound,self.focus.z+dz))
        self.set_camera()

    def zoom(self, delta):
        self.home_mode = False
        camera.fov = max(55,min(620,camera.fov+delta))
        camera.orthographic_lens.set_film_offset(-camera.fov*.16, camera.fov*.07)
