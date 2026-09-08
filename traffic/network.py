"""Directed lanes and smooth connectors shared by routing and rendering.
Metres; x east, z north. Roundabout angles increase counterclockwise.
"""
from dataclasses import dataclass, field
from bisect import bisect_right
from collections import deque
import math

GRID = (-96., -32., 32., 96.)
OFFSET, RADIUS, RING = 2.5, 16., 10.
VECTORS = {'N': (0, 1), 'E': (1, 0), 'S': (0, -1), 'W': (-1, 0)}
OPPOSITE = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}


def add(a, b, scale=1):
    return a[0] + b[0] * scale, a[1] + b[1] * scale


def unit(a, b):
    d = math.dist(a, b)
    return (b[0] - a[0]) / d, (b[1] - a[1]) / d


def bezier(a, b, c, d, steps=32):
    return [tuple((1-t)**3*a[k] + 3*(1-t)**2*t*b[k] + 3*(1-t)*t*t*c[k] + t**3*d[k]
                  for k in (0, 1)) for t in (i/steps for i in range(steps+1))]


@dataclass
class Path:
    id: str
    points: list
    kind: str = 'lane'
    source: str = ''
    target: str = ''
    junction: str = ''
    incoming: str = ''
    outgoing: str = ''
    approach: str = ''
    turn: str = 'straight'
    distances: list = field(init=False)

    def __post_init__(self):
        self.distances = [0.]
        for a, b in zip(self.points, self.points[1:]):
            self.distances.append(self.distances[-1] + math.dist(a, b))

    @property
    def length(self):
        return self.distances[-1]

    def pose(self, s):
        s = max(0., min(self.length, s))
        i = min(len(self.points)-2, max(0, bisect_right(self.distances, s)-1))
        a, b = self.points[i:i+2]
        t = (s-self.distances[i]) / (self.distances[i+1]-self.distances[i])
        return a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, math.degrees(math.atan2(b[0]-a[0], b[1]-a[1]))


@dataclass
class Junction:
    id: str
    position: tuple
    kind: str
    approaches: dict = field(default_factory=dict)


class Network:
    def __init__(self,spacing=64.,gates=False,peripheral=False):
        if spacing<64:raise ValueError('Block spacing must preserve junction footprints')
        self.spacing=spacing
        self.gates=gates or peripheral
        self.peripheral=peripheral
        self.grid=tuple((i-1.5)*spacing for i in range(4))
        self.nodes = {f'{x}{z}': (px, pz) for x, px in enumerate(self.grid) for z, pz in enumerate(self.grid)}
        self.junctions = {k: Junction(k, p, 'roundabout' if k in ('11', '22') else 'signal') for k, p in self.nodes.items()}
        # Other boundary junctions have only their actual two or three arms.
        edge=self.grid[-1]+64
        self.portals = {'west': (-edge, self.grid[1]), 'east': (edge, self.grid[2]),
                        'south': (self.grid[2], -edge), 'north': (self.grid[1], edge)}
        self.extent=edge+7
        self.nodes.update(self.portals)
        self.paths, self.lanes, self.connectors, self.adjacency = {}, {}, {}, {k: [] for k in self.nodes}
        edges = []
        for x in range(4):
            for z in range(4):
                if x < 3:
                    edges.append((f'{x}{z}', f'{x+1}{z}'))
                if z < 3:
                    edges.append((f'{x}{z}', f'{x}{z+1}'))
        edges += [('west', '01'), ('east', '32'), ('south', '20'), ('north', '13')]
        if peripheral:
            # Keep every central node and block unchanged. A belt road joins
            # the four old boundary approaches; external gates move outward.
            ring={'rw':(-edge,self.grid[1]),'re':(edge,self.grid[2]),
                  'rs':(self.grid[2],-edge),'rn':(self.grid[1],edge),
                  'rNW':(-edge,edge),'rNE':(edge,edge),
                  'rSW':(-edge,-edge),'rSE':(edge,-edge)}
            self.nodes.update(ring)
            self.junctions.update({k:Junction(k,p,'signal') for k,p in ring.items()})
            self.portals={'west':(-edge-64,self.grid[1]),'east':(edge+64,self.grid[2]),
                          'south':(self.grid[2],-edge-64),'north':(self.grid[1],edge+64)}
            self.nodes.update(self.portals);self.extent=edge+71
            edges=edges[:-4]+[('west','rw'),('rw','01'),('east','re'),('re','32'),
                ('south','rs'),('rs','20'),('north','rn'),('rn','13')]
            belt=('rNW','rw','rSW','rs','rSE','re','rNE','rn','rNW')
            edges+=list(zip(belt,belt[1:]))
            self.adjacency={k:[] for k in self.nodes}
        from .demand import ACCESS,Access,GATES,FRONTAGE
        self.access=dict(ACCESS)
        if peripheral:
            self.access.update(FRONTAGE)
            for name,node in zip(GATES,('rw','re','rs','rn')):
                portal=GATES[name].lane.split('>')[0]
                self.access[name]=Access(name,f'{portal}>{node}',6.)
                exit_name=name.replace('gate','exit')
                self.access[exit_name]=Access(exit_name,f'{node}>{portal}',42.)
        for a, b in edges:
            for source, target in ((a, b), (b, a)):
                self._lane(source, target)
        for j in self.junctions.values():
            incoming = [p for p in self.lanes.values() if p.target == j.id]
            outgoing = [p for p in self.lanes.values() if p.source == j.id]
            for a in incoming:
                for b in outgoing:
                    if a.source != b.target:
                        self._connector(j, a, b)
        self.conflicts = {k: set() for k in self.connectors}
        self.separation = {}
        for j in self.junctions:
            paths = [p for p in self.connectors.values() if p.junction == j]
            samples = {p.id: [p.pose(s)[:2] for s in range(math.ceil(p.length)+1)] for p in paths}
            for a in paths:
                for b in paths:
                    separation=min(math.dist(x,y) for x in samples[a.id] for y in samples[b.id])
                    self.separation[(a.id,b.id)]=separation
                    if a.incoming == b.incoming or a.outgoing == b.outgoing or separation < 5.8:
                        self.conflicts[a.id].add(b.id)

    def conflict(self, a, sa, b, sb):
        pa,pb=self.paths[a],self.paths[b]
        if pa.junction != pb.junction:
            return False
        if pa.incoming == pb.incoming or pa.outgoing == pb.outgoing:
            return True
        envelope=math.hypot(sa.length/2,sa.width/2)+math.hypot(sb.length/2,sb.width/2)+1.1
        return self.separation[(a,b)] < envelope

    def supports(self, route, spec):
        # The current widened connector pavement is verified for this envelope.
        # Larger assets require a geometry change, not silent clipping.
        if spec.length>9.0 or spec.width>2.3:
            return False
        for pid in route:
            p=self.paths[pid]
            for a,b,c in zip(p.points,p.points[1:],p.points[2:]):
                cross=abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
                if cross > 1e-8:
                    radius=math.dist(a,b)*math.dist(b,c)*math.dist(a,c)/(2*cross)
                    if radius < spec.turn_radius:
                        return False
        return True

    def _lane(self, source, target):
        a, b = self.nodes[source], self.nodes[target]
        d = unit(a, b)
        right = (d[1], -d[0])
        start = add(add(a, d, (20 if self.junctions[source].kind == 'roundabout' else RADIUS) if source in self.junctions else 0), right, OFFSET)
        end = add(add(b, d, -(20 if self.junctions[target].kind == 'roundabout' else RADIUS) if target in self.junctions else 0), right, OFFSET)
        p = Path(f'{source}>{target}', [start, end], source=source, target=target)
        self.paths[p.id] = self.lanes[p.id] = p
        self.adjacency[source].append(target)
        if target in self.junctions:
            outward = (-d[0], -d[1])
            arm = next(k for k, v in VECTORS.items() if v == outward)
            self.junctions[target].approaches[arm] = p.id

    def _connector(self, j, a, b):
        start, end = a.points[-1], b.points[0]
        di, do = unit(*a.points), unit(*b.points)
        cross = di[0]*do[1]-di[1]*do[0]
        turn = 'left' if cross > .5 else ('right' if cross < -.5 else 'straight')
        approach = next(k for k, v in j.approaches.items() if v == a.id)
        if j.kind == 'signal':
            control = math.dist(start, end) * .48
            pts = bezier(start, add(start, di, control), add(end, do, -control), end)
        else:
            entry_angle = math.atan2(-di[1], -di[0]) + .65
            exit_angle = math.atan2(do[1], do[0]) - .65
            while exit_angle <= entry_angle:
                exit_angle += 2*math.pi
            ringpoint = lambda angle: add(j.position, (math.cos(angle), math.sin(angle)), RING)
            tangent = lambda angle: (-math.sin(angle), math.cos(angle))
            p, q = ringpoint(entry_angle), ringpoint(exit_angle)
            pts = bezier(start, add(start, di, 6), add(p, tangent(entry_angle), -4), p)
            steps = math.ceil((exit_angle-entry_angle)*RING*3)
            pts += [ringpoint(entry_angle+(exit_angle-entry_angle)*i/steps) for i in range(1, steps+1)]
            pts += bezier(q, add(q, tangent(exit_angle), 4), add(end, do, -6), end)[1:]
        p = Path(f'{a.id}|{b.id}', pts, j.kind, junction=j.id, incoming=a.id, outgoing=b.id, approach=approach, turn=turn)
        self.paths[p.id] = self.connectors[p.id] = p

    def route(self, source, destination, rng, first_lane=None, next_target=None):
        """Randomized BFS over simple node paths excludes immediate U-turns."""
        lane = self.lanes.get(first_lane)
        queue = deque([[lane.source, lane.target] if lane else [source]])
        while queue:
            route = queue.popleft()
            node = route[-1]
            if node == destination:
                if len(route)>1 and route[-2]==next_target:
                    continue  # Seek another approach rather than requiring a U-turn.
                lanes = [f'{a}>{b}' for a, b in zip(route, route[1:])]
                result = []
                for i, lane in enumerate(lanes):
                    if i:
                        result.append(f'{lanes[i-1]}|{lane}')
                    result.append(lane)
                return tuple(result)
            neighbors = list(self.adjacency[node])
            rng.shuffle(neighbors)
            for nxt in neighbors:
                if nxt not in route and (nxt not in self.portals or nxt == destination):
                    queue.append(route+[nxt])
        raise ValueError(f'No route from {source} to {destination}')
