"""Marked curb access on directed lanes, weighted trips and a connected bus line."""
from dataclasses import dataclass

SCENARIOS = {'Baseline': 12*3600, 'Morning commute': 7*3600+30*60, 'Evening/night': 21*3600}


@dataclass(frozen=True)
class Access:
    name: str
    lane: str
    s: float = 14.0


ACCESS = {
    'Apartments': Access('Apartments','01>11'),
    'School': Access('School','00>10'),
    'University': Access('University','10>20'),
    'Offices': Access('Offices','21>31'),
    'Pub': Access('Pub','02>12'),
    'Depot': Access('Depot','23>33'),
    'Terminal': Access('Terminal','32>33'),
}
GATES={name:Access(name,lane,6.) for name,lane in (
    ('West gate','west>01'),('East gate','east>32'),
    ('South gate','south>20'),('North gate','north>13'))}
ACCESS.update(GATES)
FRONTAGE={name:Access(name,lane,40.) for name,lane in (
    ('Belt homes','rNW>rw'),('Belt offices','rSW>rs'),
    ('Belt pub','rSE>re'),('Belt shops','rNE>rn'))}
BUS_NODES = ('32','33','23','13','03','02','01','00','10','20','30','31','32','33')
BUS_STOPS = {'00>10': ('School',14.), '10>20': ('University',14.),
             '31>32': ('Offices curb',14.), '32>33': ('Terminal',14.)}


def chain(nodes):
    lanes = [f'{a}>{b}' for a,b in zip(nodes,nodes[1:])]
    result=[]
    for i,p in enumerate(lanes):
        if i:
            result.append(f'{lanes[i-1]}|{p}')
        result.append(p)
    return tuple(result)


BUS_ROUTE = chain(BUS_NODES)


def weights(seconds, arrivals=False):
    hour=(seconds/3600)%24
    morning=6 <= hour < 10
    evening=16 <= hour < 24 or hour < 2
    result={name: 1.0 for name in ACCESS if name not in GATES}
    if morning:
        result.update(Apartments=1. if arrivals else 5., Offices=5. if arrivals else 1.,
                      University=3.,School=3.)
    if evening:
        result.update(Apartments=5. if arrivals else 1., Offices=1. if arrivals else 4.,
                      Pub=2. if arrivals else 5.)
    return result


def profile_weights(scenario, origin, seconds):
    if scenario == 'Baseline':
        return {'Normal':1.,'Newbie':0.,'Drunk':0.}
    result={'Normal':.78,'Newbie':.17,'Drunk':.05}
    hour=seconds/3600%24
    if origin == 'University' and (6 <= hour < 10 or 16 <= hour < 20):
        result={'Normal':.50,'Newbie':.45,'Drunk':.05}
    if origin in ('Pub','Belt pub') and (hour >= 18 or hour < 3):
        result={'Normal':.52,'Newbie':.13,'Drunk':.35}
    return result


def choose(rng, mapping):
    return rng.choices(list(mapping),weights=list(mapping.values()),k=1)[0]


@dataclass(frozen=True)
class TripRequest:
    origin: str
    destination: str
    vehicle: str
    profile: str


def request(rng, scenario, clock, *, gates=False,queued=(),peripheral=False):
    origins=weights(clock)
    if gates:
        from .profiles import PARAMETERS
        from collections import Counter
        origins.update({name:PARAMETERS['demand']['gate_weight'] for name in GATES})
        if peripheral:
            origins.update(frontage_weights(clock))
        # Allocate NEW tickets across independent entrances; never change an
        # existing ticket, count it twice, or force a physically blocked spawn.
        if PARAMETERS['demand']['balance_pending_origins']:
            pending=Counter(v.origin for v in queued)
            origins={name:weight/(1+pending[name]) for name,weight in origins.items()}
    origin=choose(rng,origins)
    mix={'Sedan':.9,'Truck':.1}
    if origin == 'Depot':
        mix={'Sedan':.15,'Truck':.85}
    if origin == 'Terminal':
        mix={'Sedan':.25,'Bus':.75}
    kind=choose(rng,mix)
    destinations=weights(clock,True)
    if peripheral:
        destinations.update({name.replace('gate','exit'):PARAMETERS['demand']['gate_weight'] for name in GATES})
        destinations.update(frontage_weights(clock,True))
    destinations.pop(origin,None)
    destination='Terminal' if kind == 'Bus' else choose(rng,destinations)
    return TripRequest(origin,destination,kind,choose(rng,profile_weights(scenario,origin,clock)))


def frontage_weights(clock,arrivals=False):
    from .profiles import PARAMETERS
    base=weights(clock,arrivals)
    return {name:PARAMETERS['demand']['frontage_weight']*base.get(kind,1.) for name,kind in
            (('Belt homes','Apartments'),('Belt offices','Offices'),('Belt pub','Pub'),('Belt shops','Shops'))}


def route_between(net, origin, destination, rng):
    access=getattr(net,'access',ACCESS)
    a,b=access[origin].lane,access[destination].lane
    if a == b:
        raise ValueError('Same curb access')
    lane=net.lanes[b]
    route=net.route(net.lanes[a].source,lane.source,rng,first_lane=a)
    connector=f'{route[-1]}|{b}'
    if connector not in net.connectors and origin in GATES:
        route=net.route(net.lanes[a].source,lane.source,rng,first_lane=a,next_target=lane.target)
        connector=f'{route[-1]}|{b}'
    if connector not in net.connectors:
        raise ValueError('Access would require a U-turn')
    return route+(connector,b)
