"""Clock-driven sunlight and baked local lamp irradiance shared by scene surfaces."""
import math


def daylight(clock):
    # Illustrative equatorial day: sunrise 06:00, sunset 18:00; 45 min twilight.
    elevation=math.sin((clock/86400-.25)*math.tau)
    t=max(0.,min(1.,elevation/.195))
    return t*t*(3-2*t)


def make_shader():
    from ursina import Shader
    from ursina.shaders import lit_with_shadows_shader as day
    uniforms='''
uniform float night_amount;
uniform float city_shadows;
uniform float city_optimized;
uniform float city_extent;
uniform sampler2D street_irradiance;
uniform vec4 headlights[8];
uniform float headlight_strength[8];
'''
    lighting='''
    if (night_amount > 0.001 || city_optimized < 0.5) {
    vec4 material = texture(p3d_Texture0, texcoords) * p3d_ColorScale * vertex_color;
    vec2 uv = (vertex_world_position.xz + vec2(city_extent)) / (2.0*city_extent);
    vec3 lamps = texture(street_irradiance, uv).rgb;
    float elevation_fill = clamp(1.0-vertex_world_position.y/14.0, 0.0, 1.0);
    vec3 illumination = vec3(0.12,0.15,0.23) + lamps*elevation_fill;
    for (int i=0;i<8;i++) {
        vec2 offset = vertex_world_position.xz-headlights[i].xy;
        float range = length(offset);
        float cone = dot(offset/max(range,0.01),headlights[i].zw);
        illumination += vec3(0.8,0.78,0.6)*smoothstep(0.85,0.97,cone)
            *pow(max(0.0,1.0-range/18.0),2.0)*elevation_fill*headlight_strength[i];
    }
    fragment_color.rgb = mix(max(fragment_color.rgb,vec3(0.0)),
        material.rgb*illumination,night_amount);
    }
'''
    fragment=day.fragment.replace('uniform sampler2D p3d_Texture0;',uniforms+'\nuniform sampler2D p3d_Texture0;')
    fragment=fragment.replace('fragment_color = cast_shadows(fragment_color);','''
    if (city_shadows > 0.5) fragment_color = cast_shadows(fragment_color);
    else {
        vec3 L = normalize(p3d_LightSource[0].position.xyz-vertex_position*p3d_LightSource[0].position.w);
        fragment_color.rgb *= 0.65+0.35*max(0.0,dot(normalize(normal_vector),L));
    }
''')
    fragment=fragment.replace('    float distance_to_camera',lighting+'\n    float distance_to_camera')
    return Shader(name='city_day_night',vertex=day.vertex,fragment=fragment,
                  default_input=dict(day.default_input))


def lightmap(positions,resolution=512,extent=167.):
    """One baked ground irradiance texture; no per-lamp shadow passes or UI quads.

    Applied to road, pavement, building and vehicle materials in world space.
    Approximate height falloff, without building occlusion, is intentional.
    """
    from panda3d.core import PNMImage,Texture
    size=resolution;pixels=[0.]*(size*size)
    radius=18.;scale=size/(extent*2)
    for x,z in positions:
        px,pz=(x+extent)*scale,(z+extent)*scale
        for row in range(max(0,int(pz-radius*scale)),min(size,int(pz+radius*scale)+1)):
            for col in range(max(0,int(px-radius*scale)),min(size,int(px+radius*scale)+1)):
                distance=math.hypot((col+.5-px)/scale,(row+.5-pz)/scale)
                pixels[row*size+col]+=1.7*max(0.,1-distance/radius)**2
    img=PNMImage(size,size,3)
    for row in range(size):
        for col in range(size):
            value=min(1.,pixels[row*size+col])
            img.setXel(col,size-1-row,value,value*.77,value*.4)
    tex=Texture('baked_street_irradiance');tex.load(img)
    tex.setWrapU(Texture.WM_clamp);tex.setWrapV(Texture.WM_clamp)
    return tex


class Lighting:
    def __init__(self,positions,bulbs,extent=167.):
        from ursina import AmbientLight,DirectionalLight,Vec3,scene,color
        from panda3d.core import PTA_LVecBase4f,PTA_float
        self.bulbs=bulbs;self.positions=positions;self.last=None
        self.ambient=AmbientLight(color=color.white)
        self.sun=DirectionalLight(shadows=True)
        self.sun.look_at(Vec3(1,-2,-1))
        self.texture=lightmap(positions,extent=extent)
        self.headlights=PTA_LVecBase4f.empty_array(8)
        self.strength=PTA_float.empty_array(8)
        self.fades={};self.last_frame=None
        scene.set_shader_input('headlight_strength',self.strength)
        scene.set_shader_input('street_irradiance',self.texture)
        scene.set_shader_input('city_extent',extent)
        scene.set_shader_input('headlights',self.headlights)
        scene.set_shader_input('night_amount',0.)
        scene.set_shader_input('city_shadows',1.)
        scene.set_shader_input('city_optimized',0.)
        self.day=1.
        self.optimized=True;self.quality=False;self.selected=[];self.next_selection=0

    def sync(self,sim,focus):
        from ursina import scene,window,color,Vec3
        from panda3d.core import LVecBase4f
        from time import perf_counter
        self.day=daylight(sim.clock);night=1-self.day
        if self.optimized:
            shadows=getattr(self,'forced_shadows',None)
            if shadows is None:shadows=self.quality and self.day>.01
            if self.sun.shadows!=shadows:self.sun.shadows=shadows
        scene.set_shader_input('city_shadows',1. if self.sun.shadows else 0.)
        scene.set_shader_input('city_optimized',1. if self.optimized else 0.)
        scene.set_shader_input('night_amount',night)
        self.sun.color=color.rgba(self.day,self.day*.98,self.day*.92,1)
        # Below the horizon after sunset, with exactly zero sun intensity.
        elevation=math.sin((sim.clock/86400-.25)*math.tau)
        direction=round(elevation,3)
        if direction!=self.last:
            self.sun.look_at(Vec3(1,-2*elevation,-1))
            self.last=direction
        self.ambient.color=color.rgba(.12+.4*self.day,.15+.42*self.day,.23+.38*self.day,1)
        window.color=color.rgba(.018+.758*self.day,.027+.839*self.day,.065+.782*self.day,1)
        tint=round(night,2)
        if not self.optimized or tint!=getattr(self,'bulb_tint',None):
            for bulb in self.bulbs:bulb.color=color.rgba(.3+.7*night,.28+.55*night,.2+.3*night,1)
            self.bulb_tint=tint
        now=perf_counter();live={v.id:v for v in sim.vehicles if not v.crashed}
        if not self.optimized or now>=self.next_selection or any(vid not in live for vid in self.selected):
            # Retained lights receive a 12 m preference to prevent selection flicker.
            desired=[v.id for v in sorted(live.values(),key=lambda v:
                math.dist(sim.pose(v)[:2],(focus.x,focus.z))-(12 if v.id in self.selected else 0))[:8]]
            self.desired=desired
            self.selected=[vid for vid in self.selected if vid in live and (vid in desired or self.fades.get(vid,0)>.001)]
            self.selected += [vid for vid in desired if vid not in self.selected][:8-len(self.selected)]
            self.next_selection=now+.1
        dt=min(.1,now-self.last_frame) if self.last_frame is not None else 0.
        self.last_frame=now
        for vid in self.selected:
            distance=math.dist(sim.pose(live[vid])[:2],(focus.x,focus.z))
            target=max(0.,min(1.,(145-distance)/70)) if vid in self.desired else 0.
            old=self.fades.get(vid,0.)
            self.fades[vid]=old+max(-dt*2,min(dt*2,target-old))
        cars=[live[vid] for vid in self.selected if vid in live]
        for i in range(8):
            self.strength[i]=self.fades.get(cars[i].id,0.) if i<len(cars) else 0.
            if i<len(cars) and night>.01:
                x,z,yaw=sim.visual_pose(cars[i]) if self.optimized else sim.pose(cars[i]);a=math.radians(yaw)
                # Cone origin follows the same interpolated front bumper as
                # the visible lamps, rather than projecting from the cabin.
                front=cars[i].spec.length/2-.05
                x+=math.sin(a)*front;z+=math.cos(a)*front
                self.headlights[i]=LVecBase4f(x,z,math.sin(a),math.cos(a))
            else:self.headlights[i]=LVecBase4f(10000,10000,0,0)


def beam(parent,v):
    """Cheap world-space translucent beam for EVERY vehicle, independent of LOD."""
    from ursina import Entity,Mesh,color
    from ursina.shaders import unlit_shader
    # Root scales differ by asset type; compensate to retain metre dimensions.
    z=v.spec.length/2-.05;w=v.spec.width*.35
    points=[(-w,z),(w,z),(3.2,z+12),(-3.2,z+12)]
    vertices=[(x/parent.scale_x,-.025/parent.scale_y,zz/parent.scale_z) for x,zz in points]
    colours=[color.rgba(1,.94,.7,.17),color.rgba(1,.94,.7,.17),color.rgba(1,.94,.7,0),color.rgba(1,.94,.7,0)]
    e=Entity(parent=parent,model=Mesh(vertices=vertices,triangles=[(0,1,2),(0,2,3)],colors=colours),
             shader=unlit_shader,double_sided=True)
    e.model.setDepthWrite(False)
    return e
