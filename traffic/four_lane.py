"""Four 3.5 m lanes, lane-state routing and explicit mid-road change links.

The compact node coordinates are inherited unchanged. Long roads have entry,
decision-zone and exit segments. Short streets deliberately have no lateral
link: the lane must be selected upstream, or routing takes another legal turn.
"""
import math
from collections import deque
from dataclasses import replace
from .network import Network,Path,add,unit,bezier,VECTORS,RING

WIDTH=3.5
OFFSETS={'inner':WIDTH/2,'outer':WIDTH*1.5}


def smooth(t):
    t=max(0.,min(1.,t));return t*t*t*(10+t*(-15+6*t))


class FourLaneNetwork(Network):
    lane_count=4
    road_width=14.

    def __init__(self,peripheral=True,gates=True):
        super().__init__(spacing=64.,gates=gates,peripheral=peripheral)
        edges=list(dict.fromkeys((p.source,p.target) for p in self.lanes.values()))
        old_access=self.access
        self.paths={};self.lanes={};self.connectors={};self.successors={}
        self.roads={};self.references={};self.segments={};self.change_links={}
        for j in self.junctions.values():j.approaches={}
        for source,target in edges:self.build_road(source,target)
        for j in self.junctions.values():
            incoming=[self.paths[ids[-1]] for ids in self.segments.values() if self.paths[ids[-1]].target==j.id]
            outgoing=[self.paths[ids[0]] for ids in self.segments.values() if self.paths[ids[0]].source==j.id]
            j.bend=len({p.source for p in incoming})==2 and len({p.target for p in outgoing})==2
            for a in incoming:
                for b in outgoing:
                    if a.source==b.target:continue
                    di=unit(self.nodes[a.source],self.nodes[a.target]);do=unit(self.nodes[b.source],self.nodes[b.target])
                    cross=di[0]*do[1]-di[1]*do[0]
                    turn='left' if cross>.5 else 'right' if cross<-.5 else 'straight'
                    if j.bend:turn='straight'  # A road bend has no route-choice turn lane.
                    if turn=='left' and a.lane!='inner':continue
                    if turn=='right' and a.lane!='outer':continue
                    if j.kind!='roundabout':
                        if turn=='straight' and a.lane!=b.lane:continue
                        # A left turn chooses a marked destination lane during
                        # route planning. This permits curb access on short
                        # blocks where a post-turn lane change cannot fit.
                        if turn=='right' and b.lane!='outer':continue
                    self.build_connector(j,a,b,turn,di,do)
        self.conflicts={k:set() for k in self.connectors};self.separation={}
        for j in self.junctions.values():
            paths=[p for p in self.connectors.values() if p.junction==j.id]
            samples={p.id:[p.pose(s)[:2] for s in range(math.ceil(p.length)+1)] for p in paths}
            for a in paths:
                for b in paths:
                    separation=min(math.dist(x,y) for x in samples[a.id] for y in samples[b.id])
                    self.separation[a.id,b.id]=separation
                    if a.incoming==b.incoming or a.outgoing==b.outgoing or separation<5.8:self.conflicts[a.id].add(b.id)
        self.access={}
        for name,a in old_access.items():
            if name=='Terminal':a=replace(a,lane='33>23')
            if name=='Apartments':a=replace(a,lane='01>02')
            road=self.roads[a.lane];s=min(a.s,road['length']-6)
            if road['merge']:s=min(s,road['length']-22)
            s=max(5.5,s)
            pid,local=self.locate(a.lane,'outer',s)
            self.access[name]=replace(a,lane=pid,s=local)
        from .demand import BUS_STOPS
        self.bus_stops={}
        for road,(name,s) in BUS_STOPS.items():
            if name=='Terminal':road='33>23'
            if self.roads[road]['merge']:s=min(s,self.roads[road]['length']-22)
            pid,local=self.locate(road,'outer',max(5.5,s));self.bus_stops[pid]=(name,local)
        self.bus_route=self.service_route()

    def register(self,p):
        self.paths[p.id]=p;self.successors[p.id]=[]
        return p

    def point(self,road,s,lane):
        r=self.roads[road];offset=OFFSETS[lane]
        if r['split'] and s<16:offset=3.5+(offset-3.5)*smooth(s/16)
        if r['merge'] and s>r['length']-20:
            offset=offset+(3.5-offset)*smooth((s-(r['length']-20))/16)
        return add(add(r['start'],r['forward'],s),r['right'],offset)

    def build_road(self,source,target):
        road=f'{source}>{target}';a,b=self.nodes[source],self.nodes[target]
        f=unit(a,b);right=(f[1],-f[0])
        split=source in self.junctions and self.junctions[source].kind=='roundabout'
        merge=target in self.junctions and self.junctions[target].kind=='roundabout'
        begin=(20 if split else 16) if source in self.junctions else 0
        end=(20 if merge else 16) if target in self.junctions else 0
        length=math.dist(a,b)-begin-end
        self.roads[road]=dict(source=source,target=target,start=add(a,f,begin),forward=f,right=right,
                              length=length,merge=merge,split=split)
        bounds=(0.,length/2-10,length/2+10,length) if length>=76 else (0.,length)
        for lane in OFFSETS:
            ref=Path(f'{road}:{lane}:reference',[self.point(road,length*i/120,lane) for i in range(121)],'reference',source,target)
            ref.road=road;ref.lane=lane;self.references[road,lane]=ref
            self.segments[road,lane]=[]
            for i,(lo,hi) in enumerate(zip(bounds,bounds[1:])):
                part=('entry','zone','exit')[i] if len(bounds)==4 else 'full'
                p=self.register(Path(f'{road}:{lane}:{part}',[self.point(road,lo+(hi-lo)*k/40,lane) for k in range(41)],source=source,target=target))
                p.lane=lane;p.road=road;p.start_s=lo;p.end_s=hi;p.lane_width=WIDTH
                p.part=part if part!='full' else 'entry';p.merge=merge;p.split=split
                self.lanes[p.id]=p;self.segments[road,lane].append(p.id)
            chain=self.segments[road,lane]
            for x,y in zip(chain,chain[1:]):self.successors[x].append(y)
            # Full short lanes act as both entry and exit without duplicate paths.
            if len(chain)==1:self.lanes[chain[0]].part='exit'
        if target in self.junctions:
            outward=(-f[0],-f[1]);arm=next(k for k,v in VECTORS.items() if v==outward)
            self.junctions[target].approaches[arm]=self.segments[road,'outer'][-1]
        if len(bounds)==4:
            lo,hi=bounds[1:3]
            for lane,other in (('outer','inner'),('inner','outer')):
                points=[]
                for i in range(121):
                    t=i/120;s=lo+(hi-lo)*t
                    p=self.point(road,s,lane);q=self.point(road,s,other);blend=smooth(t)
                    points.append(tuple(p[k]+(q[k]-p[k])*blend for k in (0,1)))
                p=self.register(Path(f'lc:{road}:{lane}>{other}',points,'lane_change',source,target))
                p.road=road;p.lane=other;p.from_lane=lane;p.start_s=lo;p.end_s=hi
                p.incoming=self.segments[road,lane][0];p.outgoing=self.segments[road,other][-1]
                self.successors[p.incoming].append(p.id);self.successors[p.id].append(p.outgoing)
                self.change_links[road,lane]=p.id

    def build_connector(self,j,a,b,turn,di,do):
        start,end=a.points[-1],b.points[0]
        if j.bend and j.kind!='roundabout':
            ri=(di[1],-di[0]);ro=(do[1],-do[0]);offset=OFFSETS[a.lane]
            centre_start=add(start,ri,-offset);centre_end=add(end,ro,-offset)
            centre=bezier(centre_start,add(centre_start,di,8.8),add(centre_end,do,-8.8),centre_end,120)
            pts=[]
            for i,p in enumerate(centre):
                f=di if i==0 else do if i==len(centre)-1 else unit(centre[i-1],centre[i+1])
                pts.append(add(p,(f[1],-f[0]),offset))
        elif j.kind=='roundabout':
            entry=math.atan2(-di[1],-di[0])+.65;exit_angle=math.atan2(do[1],do[0])-.65
            while exit_angle<=entry:exit_angle+=2*math.pi
            ring=lambda angle:add(j.position,(math.cos(angle),math.sin(angle)),RING)
            tangent=lambda angle:(-math.sin(angle),math.cos(angle))
            p,q=ring(entry),ring(exit_angle)
            pts=bezier(start,add(start,di,6),add(p,tangent(entry),-4),p)
            steps=math.ceil((exit_angle-entry)*RING*3)
            pts += [ring(entry+(exit_angle-entry)*i/steps) for i in range(1,steps+1)]
            pts += bezier(q,add(q,tangent(exit_angle),4),add(end,do,-6),end)[1:]
        else:
            control=math.dist(start,end)*.48
            pts=bezier(start,add(start,di,control),add(end,do,-control),end)
        arm=next(k for k,v in VECTORS.items() if v==(-di[0],-di[1]))
        p=self.register(Path(f'{a.id}|{b.id}',pts,j.kind,junction=j.id,incoming=a.id,outgoing=b.id,approach=arm,turn=turn))
        self.connectors[p.id]=p;self.successors[a.id].append(p.id);self.successors[p.id].append(b.id)

    def locate(self,road,lane,s):
        for pid in self.segments[road,lane]:
            p=self.paths[pid]
            if s<=p.end_s+1e-8:return pid,max(0.,s-p.start_s)
        p=self.paths[self.segments[road,lane][-1]];return p.id,p.length

    def plan(self,start,goal,rng,blocked=()):
        queue=deque([start]);previous={start:None};blocked=set(blocked)
        while queue:
            pid=queue.popleft()
            if pid==goal:
                route=[]
                while pid is not None:route.append(pid);pid=previous[pid]
                return tuple(reversed(route))
            choices=list(self.successors[pid]);rng.shuffle(choices)
            for nxt in choices:
                if nxt not in previous and nxt not in blocked:previous[nxt]=pid;queue.append(nxt)
        raise ValueError(f'No legal lane route from {start} to {goal}')

    def trip_route(self,origin,destination,rng):
        a,b=self.access[origin],self.access[destination]
        if a.lane==b.lane:raise ValueError('Same access segment')
        return self.plan(a.lane,b.lane,rng)

    def service_route(self):
        import random
        rng=random.Random(17);start=self.access['Terminal'].lane;route=(start,)
        for goal in (*self.bus_stops,start):
            if goal!=route[-1]:route+=self.plan(route[-1],goal,rng)[1:]
        return route
