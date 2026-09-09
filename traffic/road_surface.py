"""One non-overlapping pavement mesh from the network's sampled lane curves."""
from functools import lru_cache
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
from shapely import constrained_delaunay_triangles

def surface(net):
    strips=[]
    for p in list(net.lanes.values())+list(net.connectors.values()):
        # Round joins follow the actual turning centre curves. Flat ends join
        # their matching lane endpoints, rather than extending to node centres.
        # Turning apron accommodates rigid bus/truck corner sweep outside the
        # nominal 3.5 m lane. Taper it to zero at the straight-road seam.
        line=LineString(p.points)
        strips.append(line.buffer(1.75,cap_style=2,join_style=1,quad_segs=12))
        if p.kind in ('signal','roundabout'):
            import math
            from .profiles import vehicle_spec
            from shapely.geometry import Polygon
            spec=vehicle_spec('Bus')
            for i in range(81):
                x,z,yaw=p.pose(p.length*i/80);angle=math.radians(yaw)
                f=(math.sin(angle),math.cos(angle));r=(f[1],-f[0])
                corners=[(x+f[0]*a*spec.length/2+r[0]*b*(spec.width/2+.12),z+f[1]*a*spec.length/2+r[1]*b*(spec.width/2+.12)) for a,b in ((-1,-1),(-1,1),(1,1),(1,-1))]
                strips.append(Polygon(corners))
    paved=unary_union(strips)
    # Close sub-metre slivers between overlapping turning envelopes, then
    # round concave joins; do not change road spacing or nominal lane width.
    paved=paved.buffer(.5,quad_segs=12).buffer(-.5,quad_segs=12)
    for j in net.junctions.values():
        if j.kind=='roundabout':paved=paved.difference(Point(j.position).buffer(6,quad_segs=32))
    return paved

def mesh(poly,height):
    from ursina import Mesh
    vertices=[];triangles=[]
    for triangle in constrained_delaunay_triangles(poly).geoms:
        coords=list(triangle.exterior.coords)[:3];i=len(vertices)
        vertices.extend((x,height,z) for x,z in coords);triangles.append((i,i+1,i+2))
    return Mesh(vertices=vertices,triangles=triangles,normals=[(0,1,0)]*len(vertices),static=True)

def draw(net):
    from ursina import Entity,color
    paved=surface(net)
    Entity(model=mesh(paved,.17),color=color.hex('#424b59'),double_sided=True)
    # Adjacent rings have disjoint interiors; no asphalt/curb z-fighting.
    curb=paved.buffer(.22,quad_segs=12).difference(paved)
    pavement=paved.buffer(.95,quad_segs=12).difference(paved.buffer(.22,quad_segs=12))
    Entity(model=mesh(curb,.23),color=color.hex('#d2cbb6'),double_sided=True)
    Entity(model=mesh(pavement,.22),color=color.hex('#ded4b9'),double_sided=True)
    # On a two-arm bend the dividers follow the same offset curves used by
    # vehicles. Draw one centre pair and both same-direction lane dividers.
    marked=set()
    for p in net.connectors.values():
        j=net.junctions[p.junction]
        if not j.bend or p.kind=='roundabout':continue
        a=net.paths[p.incoming]
        if a.lane!='inner':continue
        from .network import unit,add
        centre=[];divider=[]
        for i,point in enumerate(p.points):
            f=unit(p.points[max(0,i-1)],p.points[min(len(p.points)-1,i+1)])
            right=(f[1],-f[0])
            centre.append(add(point,right,-1.75+.17));divider.append(add(point,right,1.75))
        Entity(model=mesh(LineString(centre).buffer(.065,cap_style=2),.195),color=color.hex('#f5dc91'),double_sided=True)
        line=LineString(divider)
        from shapely.ops import substring
        for start in range(0,int(line.length)-2,6):
            Entity(model=mesh(substring(line,start,start+2.6).buffer(.07,cap_style=2),.195),color=color.hex('#eee9da'),double_sided=True)
    return paved
