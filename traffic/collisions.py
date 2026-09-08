"""Swept SAT on the actual piecewise-linear, piecewise-constant-heading paths."""
import math
from collections import defaultdict
from .supervisor import rectangles_overlap


def impact_pose(sim,a,b,previous):
    """Resolve angular contact at a polyline heading boundary, not penetration.

    Translation SAT can first detect contact at the instant heading changes.
    Sweep that small angular transition and retain its first-touch orientation
    for the wreck instead of snapping the entire rectangle to the next heading.
    """
    ends=[sim.future_pose(v,v.s) for v in (a,b)]
    starts=[previous[v.id] for v in (a,b)]
    def blend(start,end,t):
        delta=(end[2]-start[2]+180)%360-180
        return (start[0]+(end[0]-start[0])*t,start[1]+(end[1]-start[1])*t,start[2]+delta*t)
    if rectangles_overlap(ends[0],a.spec,ends[1],b.spec,margin=-1e-8):
        low,high=0.,1.
        if rectangles_overlap(starts[0],a.spec,starts[1],b.spec,margin=-1e-8):
            raise AssertionError('Collision resolver received an already penetrating start')
        for _ in range(45):
            mid=(low+high)/2
            aa,bb=[blend(start,end,mid) for start,end in zip(starts,ends)]
            if rectangles_overlap(aa,a.spec,bb,b.spec,margin=0):high=mid
            else:low=mid
        ends=[blend(start,end,low) for start,end in zip(starts,ends)]
    for v,pose in zip((a,b),ends):
        if not v.crashed:v.contact_pose=pose


def axes(yaw):
    a=math.radians(yaw)
    return ((math.sin(a),math.cos(a)),(math.cos(a),-math.sin(a)))


def swept(a, da, sa, b, db, sb):
    """First contact fraction for translating oriented rectangles, or None."""
    aa,bb=axes(a[2]),axes(b[2])
    lo,hi=0.,1.
    for n in (*aa,*bb):
        dot=lambda p:p[0]*n[0]+p[1]*n[1]
        extent=sum(h*abs(dot(axis)) for h,axis in
                   ((sa.length/2,aa[0]),(sa.width/2,aa[1]),
                    (sb.length/2,bb[0]),(sb.width/2,bb[1])))
        position=dot((a[0]-b[0],a[1]-b[1]))
        velocity=dot((da[0]-db[0],da[1]-db[1]))
        if abs(velocity)<1e-12:
            if abs(position)>extent+1e-9: return None
        else:
            enter,leave=sorted(((-extent-position)/velocity,(extent-position)/velocity))
            lo,hi=max(lo,enter),min(hi,leave)
            if lo>hi+1e-10: return None
    return max(0.,lo) if lo<=1 and hi>=0 else None


def breaks(sim,v,travel):
    points={0.,1.}
    if travel<=0: return points
    offset=-v.s
    for pid in v.route[v.index:]:
        p=sim.network.paths[pid]
        for d in p.distances:
            t=(offset+d)/travel
            if 0<t<1: points.add(t)
        offset+=p.length
        if offset>=travel: break
    return points


def contact(sim,a,travel_a,b,travel_b):
    times=sorted(breaks(sim,a,travel_a)|breaks(sim,b,travel_b))
    for t,u in zip(times,times[1:]):
        pa=sim.future_pose(a,a.s+travel_a*t)
        pb=sim.future_pose(b,b.s+travel_b*t)
        ea=sim.future_pose(a,a.s+travel_a*u)
        eb=sim.future_pose(b,b.s+travel_b*u)
        # Heading is constant inside each polyline interval, including at its start.
        ya=sim.future_pose(a,a.s+travel_a*(t+u)/2)[2]
        yb=sim.future_pose(b,b.s+travel_b*(t+u)/2)[2]
        hit=swept((*pa[:2],ya),(ea[0]-pa[0],ea[1]-pa[1]),a.spec,
                  (*pb[:2],yb),(eb[0]-pb[0],eb[1]-pb[1]),b.spec)
        if hit is not None: return t+(u-t)*hit
    # Heading can change exactly at a polyline/route boundary.
    aend=sim.future_pose(a,a.s+travel_a)
    bend=sim.future_pose(b,b.s+travel_b)
    if swept(aend,(0,0),a.spec,bend,(0,0),b.spec) is not None:return 1.
    return None


def pairs(sim,updates):
    """16 m spatial hash of swept centre bounds expanded by circumradius."""
    grid=defaultdict(list)
    for i,(v,s,_) in enumerate(updates):
        travel=s-v.s
        poses=[sim.future_pose(v,v.s+travel*t) for t in breaks(sim,v,travel)]
        r=math.hypot(v.spec.length,v.spec.width)/2
        for x in range(math.floor((min(p[0] for p in poses)-r)/16),math.floor((max(p[0] for p in poses)+r)/16)+1):
            for z in range(math.floor((min(p[1] for p in poses)-r)/16),math.floor((max(p[1] for p in poses)+r)/16)+1):
                grid[x,z].append(i)
    return sorted({(a,b) for bucket in grid.values() for a in bucket for b in bucket if a<b})


def movement(sim,updates):
    """Advance to earliest contact, hold wrecks, recompute remaining trajectories."""
    remaining={v.id:max(0.,s-v.s) for v,s,_ in updates}
    moved={v.id:0. for v,_,_ in updates}
    speeds={v.id:speed for v,_,speed in updates}
    starts={v.id:v.s for v,_,_ in updates}
    for _ in range(len(updates)+1):
        candidates=[(v,v.s+remaining[v.id],speeds[v.id]) for v,_,_ in updates]
        hits=[]
        for i,j in pairs(sim,candidates):
            a,b=updates[i][0],updates[j][0]
            if a.crashed and b.crashed: continue
            if remaining[a.id]+remaining[b.id]<=1e-12: continue
            t=contact(sim,a,remaining[a.id],b,remaining[b.id])
            if t is not None: hits.append((t,a,b))
        if not hits:
            for v,_,_ in updates: moved[v.id]+=remaining[v.id]
            break
        earliest=min(t for t,_,_ in hits)
        previous={v.id:sim.future_pose(v,v.s+remaining[v.id]*max(0.,earliest-1e-7)) for v,_,_ in updates}
        for v,_,_ in updates:
            distance=remaining[v.id]*earliest
            moved[v.id]+=distance
            v.s+=distance
            remaining[v.id]*=1-earliest
        edges=[(a,b) for t,a,b in hits if t<=earliest+1e-8]
        # Walk each simultaneous contact component before starting another ID.
        # Pair enumeration order must not split one multi-car pile-up.
        while edges:
            component=set()
            while edges:
                index=next((i for i,(a,b) in enumerate(edges)
                            if not component or a.id in component or b.id in component),None)
                if index is None:break
                a,b=edges.pop(index)
                component.update((a.id,b.id))
                impact_pose(sim,a,b,previous)
                sim.incidents.register(sim,a,b)
                remaining[a.id]=remaining[b.id]=0.
                speeds[a.id]=speeds[b.id]=0.
    result=[]
    for v,_,_ in updates:
        v.s=starts[v.id]
        result.append((v,v.s+moved[v.id],speeds[v.id]))
    return result
