from dataclasses import dataclass, field
import math
import random
from collections import deque
from .profiles import Driver, VehicleSpec, PARAMETERS, sample_driver, vehicle_spec
from .demand import ACCESS, BUS_ROUTE, BUS_STOPS, SCENARIOS, TripRequest, request, route_between, choose, profile_weights
from .supervisor import SafetySupervisor
from .incidents import Incidents, Metrics
from .collisions import movement as collide, contact
from . import behaviour
from . import overtaking
from copy import copy

from .lanes import LENGTH, GAP
from .network import Network, OPPOSITE
from .signals import Signals

STEP = 1 / 60
DECISION_STEPS = 6
ACCEL, BRAKE, CRUISE = 2.4, 4.5, 10.0
STOP_MARGIN = LENGTH / 2 + .5


@dataclass
class Vehicle:
    id: int
    route: tuple
    s: float
    tint: int
    index: int = 0
    speed: float = 0.0
    permit: str | None = None
    waiting: float = 0.0
    action: str = 'stop'
    reason: str = 'awaiting_observation'
    driver: Driver = field(default_factory=Driver)
    spec: VehicleSpec = field(default_factory=VehicleSpec)

    origin: str = 'Boundary'
    destination: str = 'Boundary'
    end_s: float | None = None
    executed: str = 'stop'
    intervention: str = ''
    history: deque = field(default_factory=deque)
    epoch: int = 0
    next_behaviour: float = 0.0
    risky_signal: bool = False
    risky_gap: bool = False
    hesitation_until: float = 0.0
    speed_variation: float = 1.0
    behaviour_rng: object = field(default=None,compare=False,repr=False)
    dwell: float = 0.0
    stop_status: str = ''
    stop_name: str = ''
    serviced: set = field(default_factory=set)
    crashed: bool = False
    incident: int | None = None
    contact_pose: tuple | None = None
    recent: deque = field(default_factory=lambda:deque(maxlen=12))
    perception: deque = field(default_factory=deque)
    perception_ready: bool = False
    actual_gap: float = math.inf
    actual_closing: float = 0.
    perceived_gap: float = math.inf
    perceived_closing: float = 0.
    perceived_leader: int | None = None
    opportunities: dict = field(default_factory=dict)
    episode: str = 'steady'
    control: str = 'proceed'
    control_reason: str = 'perceived_clear'
    passing_state: str = 'follow'
    passing_reason: str = ''
    manoeuvre: object = field(default=None,compare=True)
    oncoming_history: deque = field(default_factory=deque)
    assess_until: float = 0.
    queued_since: float = 0.
    spawn_block: str = ''
    manoeuvre_mode: str = 'overtaking'
    threat_history: deque = field(default_factory=deque)
    oncoming_brake: bool = False
    used_manoeuvres: set = field(default_factory=set)

    @property
    def desired_speed(self):
        return self.spec.cruise*self.driver.speed_factor*self.speed_variation

    @property
    def path_id(self):
        return self.route[self.index]

    @property
    def committed(self):
        return self.permit is not None


class Simulation:
    def __init__(self, rules, seed=42, network=None, scenario='Baseline', mode='supervised', clearance=45.):
        self.rules, self.seed = rules, seed
        self.network = copy(network) if network else Network(spacing=PARAMETERS.get('network',{}).get('block_spacing',64.),
                                          gates=PARAMETERS.get('demand',{}).get('enable_gates',True),
                                          peripheral=PARAMETERS.get('network',{}).get('peripheral',False))
        self.network.paths=dict(self.network.paths)
        self.scenario=scenario
        if mode not in ('supervised','accident'): raise ValueError(mode)
        if clearance<=0: raise ValueError('Clearance must be positive')
        self.mode,self.clearance=mode,clearance
        self.reset()

    def reset(self, scenario=None, target=None):
        for pid in list(self.network.paths):
            if pid.startswith('ot:'):del self.network.paths[pid]
        if scenario is not None:
            if scenario not in SCENARIOS:
                raise ValueError(scenario)
            self.scenario=scenario
        self.start_clock=SCENARIOS[self.scenario]
        self.supervisor=SafetySupervisor()
        self.incidents=Incidents(self.clearance)
        self.metrics=Metrics()
        self.behaviour_audit=behaviour.BehaviourAudit()
        from .flow_audit import FlowAudit
        self.flow_audit=FlowAudit()
        self.overlay='None'
        self.queued=deque()
        self.removals=[]
        self.removed_ids=set()
        self.spawn_status='Ready'
        self.wrong_way_actors=[]
        self.rng = random.Random(self.seed)
        self.driver_rng = random.Random(self.seed+7919)
        self.initializing=True
        self.signals = {k: Signals() for k, j in self.network.junctions.items() if j.kind == 'signal'}
        self.global_green = 30.
        self.target = 40 if target is None else target
        self.elapsed = self.accumulator = 0.
        self.ticks = self.completed = 0
        self.paused = False
        self.next_id = 1
        self.vehicles = []
        if sum(PARAMETERS['initial_mix'].values()) != 40:
            raise ValueError('initial_mix must total 40 vehicles')
        initial=min(40,self.target)
        mix={k:int(count*initial/40) for k,count in PARAMETERS['initial_mix'].items()}
        mix['Sedan']+=initial-sum(mix.values())
        for kind,count in mix.items():
            for _ in range(count):
                for attempt in range(400):
                    ticket=request(self.rng,self.scenario,self.clock,gates=self.network.gates,peripheral=self.network.peripheral)
                    if kind == 'Bus':
                        ticket=TripRequest('Terminal','Terminal','Bus',ticket.profile)
                    else:
                        ticket=TripRequest('Depot' if kind == 'Truck' else ticket.origin,
                                           ticket.destination if ticket.destination != 'Depot' else 'Offices',kind,ticket.profile)
                    ticket=TripRequest(ticket.origin,ticket.destination,ticket.vehicle,choose(self.rng,profile_weights(self.scenario,ticket.origin,self.clock)))
                    v=self._make_vehicle(ticket)
                    if v is None:
                        continue
                    choices=[i for i,pid in enumerate(v.route[:-1]) if self.network.paths[pid].kind == 'lane']
                    self.rng.shuffle(choices)
                    accepted=False
                    for index in choices:
                        v.index=index
                        v.s=self.rng.uniform(v.spec.length/2+1,self.network.paths[v.path_id].length-v.spec.length/2-2)
                        v.serviced=set()
                        if v.path_id in BUS_STOPS and v.s>BUS_STOPS[v.path_id][1]:
                            v.serviced.add(index)
                        if self.supervisor.spawn_clear(self.network,v,self.vehicles):
                            self.vehicles.append(v)
                            accepted=True
                            break
                    if accepted:
                        break
                else:
                    raise RuntimeError('Cannot safely distribute the configured initial mix')
        self.initializing=False
        for v in self.vehicles:
            self.metrics.enter(v,self.network)
            self.behaviour_audit.admit(v)

    @property
    def clock(self):
        return (self.start_clock+self.elapsed) % 86400

    @property
    def clock_label(self):
        seconds=int(self.clock)
        return f'{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d}'

    def _make_vehicle(self, ticket):
        spec=vehicle_spec(ticket.vehicle)
        try:
            route=BUS_ROUTE if ticket.vehicle == 'Bus' else route_between(self.network,ticket.origin,ticket.destination,self.rng)
        except ValueError:
            return None
        if not self.network.supports(route,spec):
            return None
        v=Vehicle(self.next_id,route,self.network.access[ticket.origin].s,self.rng.randrange(6),
                  driver=sample_driver(ticket.profile,self.rng if self.initializing else self.driver_rng),spec=spec,origin=ticket.origin,
                  destination=ticket.destination,end_s=self.network.access[ticket.destination].s)
        v.behaviour_rng=random.Random(self.seed*1000003+v.id)
        self.next_id+=1
        return v

    def _admit_demand(self):
        # Unentered demand is a stable queue; blocked tickets retain their traits.
        while len(self.queued)>self.pending:
            self.queued.pop()
        for _ in range(max(0,self.pending-len(self.queued))):
            for attempt in range(30):
                ticket=request(self.rng,self.scenario,self.clock,gates=self.network.gates,queued=self.queued,peripheral=self.network.peripheral)
                if ticket.vehicle == 'Bus' and sum(v.spec.kind == 'Bus' for v in list(self.vehicles)+list(self.queued)) >= PARAMETERS['max_buses']:
                    continue
                v=self._make_vehicle(ticket)
                if v:
                    v.queued_since=self.elapsed
                    self.queued.append(v)
                    break
        admitted=0
        for _ in range(len(self.queued)):
            v=self.queued.popleft()
            v.spawn_block=self.supervisor.spawn_reason(self.network,v,self.vehicles)
            self.flow_audit.entry_checks[v.origin]+=1
            self.flow_audit.blocks[v.spawn_block or ('Tick admission limit' if admitted>=4 else 'clear')]+=1
            if admitted<4 and self.pending and not v.spawn_block:
                self.vehicles.append(v)
                self.metrics.enter(v,self.network)
                self.behaviour_audit.admit(v)
                admitted+=1
                self.flow_audit.admissions[v.origin]+=1
                self.flow_audit.waits.append(self.elapsed-v.queued_since)
            else:
                self.queued.append(v)
        # Rotate the starting ticket between retries, including when all are blocked.
        self.queued.rotate(-1)
        from collections import Counter
        blocked=Counter(v.spawn_block for v in self.queued if v.spawn_block)
        self.spawn_status=('At target' if not self.pending else
            ', '.join(f'{reason}: {count}' for reason,count in blocked.most_common(2))
            or 'Demand awaiting next admission tick')

    def remove_vehicles(self, ids, reason):
        """Single audited, idempotent exit from the active registry."""
        if reason not in ('trip_completion','crash_clearance','population_retirement'):
            raise ValueError(reason)
        ids=set(ids)
        if not ids:return []
        removed=[]
        for v in self.vehicles:
            if v.id not in ids or v.id in self.removed_ids:continue
            self.removals.append(dict(id=v.id,time=self.elapsed,reason=reason,
                incident=v.incident,path=v.path_id,position=self.pose(v),destination=v.destination))
            self.removed_ids.add(v.id);removed.append(v.id)
            v.permit=None
        self.vehicles[:]=[v for v in self.vehicles if v.id not in removed]
        if reason=='trip_completion':self.completed+=len(removed)
        return removed

    @property
    def pending(self):
        return max(0, self.target-len(self.vehicles))

    def set_target(self, count):
        self.target = max(0, min(100, int(count)))
        while len(self.queued)>self.pending:
            self.queued.pop()

    def set_global(self, seconds):
        self.global_green = max(5., min(120., float(seconds)))
        for signal in self.signals.values():
            if signal.override is None:
                signal.request(self.global_green)

    def set_local(self, junction, seconds=None):
        signal = self.signals[junction]
        signal.override = None if seconds is None else max(5., min(120., float(seconds)))
        signal.request(self.global_green if seconds is None else signal.override)

    def pose(self, v):
        if v.contact_pose is not None:return v.contact_pose
        return self.network.paths[v.path_id].pose(v.s)

    def _spawn(self, lane_id, s=0.):
        if any(v.path_id == lane_id and abs(v.s-s) < LENGTH+GAP+2 for v in self.vehicles):
            return False
        lane = self.network.lanes[lane_id]
        destinations = [p for p in self.network.portals if p != lane.source]
        if lane.target in self.network.portals:
            destinations = [lane.target]
        self.rng.shuffle(destinations)
        for destination in destinations:
            try:
                route = self.network.route(lane.source, destination, self.rng, first_lane=lane_id)
                break
            except ValueError:
                continue
        else:
            return False
        start_index = 0
        if lane.source not in self.network.portals:
            # Initial cars are mid-trip; retain a real boundary-entry prefix.
            for portal in self.network.portals:
                prefix = self.network.route(portal, lane.source, self.rng)
                connection = f'{prefix[-1]}|{lane.id}'
                if connection in self.network.connectors:
                    start_index = len(prefix)+1
                    route = prefix+(connection,)+route
                    break
            else:
                raise ValueError(f'Cannot construct boundary prefix for {lane.id}')
        candidate=Vehicle(self.next_id, route, s, self.rng.randrange(6), index=start_index)
        if not self.supervisor.spawn_clear(self.network,candidate,self.vehicles):
            return False
        self.vehicles.append(candidate)
        self.next_id += 1
        return True

    def advance(self, real_dt):
        if self.paused:
            return
        self.accumulator += max(0., real_dt)
        while self.accumulator + 1e-9 >= STEP:
            self.step()
            self.accumulator -= STEP

    def _gap(self, v, snapshot, preferred=True):
        path = self.network.paths[v.path_id]
        distance = math.inf
        # Look along this vehicle's next route segments, including connector tails.
        offset = -v.s
        for pid in v.route[v.index:v.index+3]:
            for w, wid, ws in snapshot:
                if w.id != v.id and wid == pid and offset+ws > 0:
                    distance = min(distance, offset+ws-(v.spec.length+w.spec.length)/2)
            offset += self.network.paths[pid].length
        if path.kind == 'lane':
            for w, wid, ws in snapshot:
                wp = self.network.paths[wid]
                if wp.kind != 'lane' and wp.incoming == path.id:
                    distance = min(distance, path.length-v.s+ws-(v.spec.length+w.spec.length)/2)
        if v.manoeuvre or any(w.manoeuvre for w,_,_ in snapshot):
            x,z,yaw=self.pose(v);r=math.radians(yaw)
            for w,_,_ in snapshot:
                if w is v or not (v.manoeuvre or w.manoeuvre):continue
                if v.driver.kind=='Normal' and w.manoeuvre_mode=='wrong_way':continue
                xx,zz,_=self.pose(w)
                front=(xx-x)*math.sin(r)+(zz-z)*math.cos(r)
                side=abs((xx-x)*math.cos(r)-(zz-z)*math.sin(r))
                if front>0 and side<(v.spec.width+w.spec.width)/2+.2:
                    distance=min(distance,front-(v.spec.length+w.spec.length)/2)
        return distance-(v.driver.gap if preferred else .6)

    def _decide(self, snapshot):
        net = self.network
        self.observation_poses={v.id:self.pose(v) for v,_,_ in snapshot}
        reservations = [(v, v.permit) for v, _, _ in snapshot if v.permit]
        candidates = []
        for v, pid, s in snapshot:
            path = net.paths[pid]
            connector = net.paths[v.route[v.index+1]] if path.kind == 'lane' and v.index+1 < len(v.route) and not v.manoeuvre else None
            candidates.append((v, path, connector))
        # After 60 seconds, oldest stopped queues get first chance at a safe gap.
        # Moving/committed opposing traffic retains priority; no reservation is revoked.
        candidates.sort(key=lambda item: (not (item[0].waiting >= 60),
                                         -item[0].waiting if item[0].waiting >= 60 else 0,
                                         item[2].turn == 'left' if item[2] else False,
                                         item[1].length-item[0].s, item[0].id))
        # Leave a gap open for an aged queue long enough for its delayed
        # observation to arrive. A claim covers only its conflicting paths.
        claims=[]
        for owner,road,cp in candidates:
            if cp is None or owner.permit or owner.waiting<60:
                continue
            if cp.kind == 'signal' and self.signals[cp.junction].light(cp.approach) != 'green':
                continue
            if any(wid == cp.outgoing and ws < owner.spec.length+w.spec.length/2+owner.driver.gap+1.75+owner.driver.entry_gap
                   for w,wid,ws in snapshot):
                continue
            if not any(net.conflict(cp.id,owner.spec,other.id,older.spec) for older,other in claims):
                claims.append((owner,cp))
        for v, path, connector in candidates:
            if v.crashed: continue
            gap = self._gap(v, snapshot)
            if v.driver.kind!='Normal':behaviour.observe(self,v,snapshot)
            else:
                v.actual_gap=v.perceived_gap=gap+v.driver.gap
            forward_safe = gap > v.speed*.45 + .05
            stop_gap = path.length-v.spec.length/2-.5-v.s
            near = stop_gap <= 2.0
            signal='green'
            conflicts=[]
            exit_clear=True
            extra_clear=True
            if connector:
                exit_clear = not any(wid == connector.outgoing and ws < v.spec.length+w.spec.length/2+v.driver.gap+1.75
                                     for w,wid,ws in snapshot)
                extra_clear = not any(wid == connector.outgoing and ws < v.spec.length+w.spec.length/2+v.driver.gap+1.75+v.driver.entry_gap
                                      for w,wid,ws in snapshot)
                conflicts = [pid for owner,pid in reservations if owner.id != v.id and net.conflict(connector.id,v.spec,pid,owner.spec)]
                claimed = any(owner.id != v.id and owner.waiting>v.waiting and net.conflict(connector.id,v.spec,cp.id,owner.spec)
                              for owner,cp in claims)
                oncoming_clear = not any(other is not v and cp and cp.junction == connector.junction
                                        and cp.approach == OPPOSITE[connector.approach] and cp.turn != 'left'
                                        and pp.length-other.s < 14+v.driver.entry_gap
                                        and not (v.waiting >= 60 and other.speed < .05 and other.waiting < v.waiting)
                                        for other,pp,cp in candidates)
                signal = self.signals[connector.junction].light(connector.approach) if connector.kind == 'signal' else 'green'
                observation=(signal,bool(v.permit),stop_gap >= v.speed*v.speed/(2*v.spec.braking)+v.speed*.1+.15,
                             exit_clear,forward_safe,connector.kind,connector.turn,not conflicts and not claimed,
                             not conflicts if connector.kind == 'roundabout' else True,oncoming_clear)
            else:
                observation=('green',bool(v.permit),True,True,forward_safe,'road','straight',True,True,True)
            self._proposal(v,observation,extra_clear and gap>v.driver.entry_gap)
            if v.reason == 'signal_violation' and connector and near:
                self.supervisor.violation(v)
            if connector and not v.permit and v.action == 'proceed' and (near or (signal == 'amber' and not observation[2])):
                intervention=self.supervisor.admission(v,conflicts=conflicts or claimed,exit_clear=exit_clear,signal=signal)
                if self.mode == 'accident' and (v.driver.kind!='Normal' or v.reason in ('signal_violation','unsafe_gap_accepted')):
                    intervention=None
                if intervention:
                    self.supervisor.record(v,intervention)
                else:
                    v.permit=connector.id
                    reservations.append((v,connector.id))

    def _proposal(self,v,observation,larger_gap):
        if v.driver.kind!='Normal':
            behaviour.propose(self,v,observation,larger_gap)
            return
        if v.behaviour_rng is None:
            v.behaviour_rng=random.Random(self.seed*1000003+v.id)
        if self.elapsed >= v.next_behaviour:
            rng=v.behaviour_rng
            v.epoch+=1
            v.next_behaviour=self.elapsed+rng.uniform(*PARAMETERS['behaviour_interval'])
            v.risky_signal=rng.random()<v.driver.signal_risk
            v.risky_gap=rng.random()<v.driver.gap_risk
            v.hesitation_until=self.elapsed+rng.uniform(.8,1.8) if rng.random()<v.driver.hesitation else 0.
            v.speed_variation=rng.uniform(.85,1.15) if v.driver.kind == 'Drunk' else 1.
        context=v.index
        v.history.append((self.elapsed,context,observation,larger_gap))
        while len(v.history)>1 and v.history[1][0] <= self.elapsed-v.driver.reaction:
            v.history.popleft()
        stamp,old_context,observed,large=v.history[0]
        ready=stamp <= self.elapsed-v.driver.reaction+1e-8 and old_context == context
        if v.permit:
            # Commitment is the driver's own state, not an external delayed signal.
            observed=observation
            ready=True
        v.action,v.reason=self.rules.behave(observed,v.driver.kind,ready=ready,larger_gap=large,
                                           hesitation=v.speed<.05 and self.elapsed<v.hesitation_until,
                                           risk_signal=v.risky_signal,risk_gap=v.risky_gap,dwell=v.dwell>0)
        v.executed=v.action
        v.intervention=''
        v.recent.append(dict(time=self.elapsed,path=v.path_id,signal=observation[0],
                             observed_signal=observed[0],action=v.action,reason=v.reason,executed=v.executed))

    def future_pose(self,v,s):
        if v.contact_pose is not None:return v.contact_pose
        index=v.index
        while s>self.network.paths[v.route[index]].length and index<len(v.route)-1:
            s-=self.network.paths[v.route[index]].length
            index+=1
        return self.network.paths[v.route[index]].pose(s)

    def bus_stop(self,v):
        if v.spec.kind != 'Bus' or v.index in v.serviced or v.path_id not in BUS_STOPS:
            return None
        if v.index == 0:
            return None
        return BUS_STOPS[v.path_id]

    def step(self):
        if self.paused:
            return
        self.incidents.clear(self)
        self.supervisor.context=self
        changed = False
        for signal in self.signals.values():
            before = signal.index
            signal.step(STEP)
            changed |= before != signal.index
        # Release only after the rear and following gap have cleared the exit.
        for v in self.vehicles:
            p = self.network.paths[v.path_id]
            if p.kind == 'lane' and p.length-v.spec.length/2-.5-v.s <= 2 and v.speed < .05:
                v.waiting += STEP
            else:
                v.waiting = 0.
            if v.permit and v.path_id == self.network.paths[v.permit].outgoing and v.s >= v.spec.length/2+.75:
                v.permit = None
        snapshot = [(v, v.path_id, v.s) for v in self.vehicles]
        if self.ticks % DECISION_STEPS == 0 or changed:
            self._decide(snapshot)
            from . import wrong_way
            for v in self.vehicles:
                self.flow_audit.inspect(self,v)
                overtaking.decide(self,v)
                wrong_way.decide(self,v)
            self.wrong_way_actors=[v for v in self.vehicles if v.manoeuvre and v.manoeuvre_mode=='wrong_way']
            for v in self.vehicles:wrong_way.observe_oncoming(self,v)
            snapshot=[(v,v.path_id,v.s) for v in self.vehicles]
        updates = []
        for v in self.vehicles:
            p = self.network.paths[v.path_id]
            if v.crashed:
                updates.append((v,v.s,0.))
                continue
            available = self._gap(v, snapshot)
            if v.reason == 'unsafe_gap_accepted':
                available=math.inf
            elif v.driver.kind=='Normal' or self.mode=='supervised':
                # Wrecks on crossing/merging paths are visible physical obstacles,
                # not merely members of the current longitudinal route queue.
                lookahead=max(3.,v.speed*v.driver.reaction+v.speed*v.speed/(2*v.spec.braking)+v.driver.gap+2)
                for wreck in self.vehicles:
                    if wreck.crashed and math.dist(self.pose(v)[:2],self.pose(wreck)[:2])<lookahead+v.spec.length+wreck.spec.length:
                        hit=contact(self,v,lookahead,wreck,0.)
                        if hit is not None:
                            available=min(available,max(0.,lookahead*hit-v.driver.gap))
            if v.dwell>0:
                v.dwell=max(0.,v.dwell-STEP)
                v.executed='wait'
                v.stop_status=f'{v.stop_name}: dwell {v.dwell:.1f}s'
                updates.append((v,v.s,0.))
                continue
            stop=self.bus_stop(v)
            if stop:
                v.stop_status=f'Approaching {stop[0]}'
                if v.s>=stop[1]-.01 and v.speed<.1:
                    v.serviced.add(v.index)
                    v.dwell=PARAMETERS['bus_dwell']
                    v.stop_name=stop[0]
                    v.stop_status=f'{v.stop_name}: dwell {v.dwell:.1f}s'
                    self._proposal(v,('green',bool(v.permit),True,True,True,'road','straight',True,True,True),True)
                    updates.append((v,v.s,0.))
                    continue
                available=min(available,max(0.,stop[1]-v.s))
            elif v.spec.kind == 'Bus':
                v.stop_status='In service'
            if v.index == len(v.route)-1 and v.end_s is not None:
                available=min(available,max(0.,v.end_s-v.s))
            if p.kind == 'lane' and v.index+1 < len(v.route) and v.permit != v.route[v.index+1]:
                available = min(available, p.length-v.spec.length/2-.5-v.s)
            cruise = v.desired_speed if p.kind == 'lane' else min(6.,v.desired_speed)
            if self.mode=='accident' and v.driver.kind!='Normal':
                # Imperfect drivers execute Prolog control using stale perception.
                # No actual-gap or stop-line travel clamp may erase this motion.
                target=0. if v.control in ('wait','brake') else cruise
                if v.manoeuvre:
                    # The Prolog passing state authorizes motion around the leader.
                    target=cruise
                    if v.manoeuvre_mode=='wrong_way':target=min(target,PARAMETERS['wrong_way']['speed'])
                    if v.passing_reason in ('overtaking_late_braking','wrong_way_braking'):target=0.
                    v.control_reason=v.passing_reason
                    remaining=p.length-v.s
                    if not v.manoeuvre['returning']:
                        target=min(target,math.sqrt(2*v.spec.braking*max(0.,remaining-1)))
                motor=1. if v.control=='accelerate' else min(1.,v.driver.acceleration)
                deceleration=v.spec.braking*v.driver.braking
                if v.driver.kind=='Newbie' and v.control=='brake':deceleration=v.spec.braking
                # Destinations and scheduled stops are known service locations.
                service=stop[1]-v.s if stop else math.inf
                if v.index==len(v.route)-1 and v.end_s is not None:service=min(service,v.end_s-v.s)
                target=min(target,math.sqrt(2*v.spec.braking*max(0.,service)))
                speed=min(target,v.speed+v.spec.acceleration*motor*STEP) if target>=v.speed else max(target,v.speed-deceleration*STEP)
                travel=speed*STEP
                if v.manoeuvre and not v.manoeuvre['returning'] and travel>p.length-v.s:
                    travel=max(0.,p.length-v.s);speed=0.
                    self.supervisor.record(v,'opposing_lane_end_guard')
                updates.append((v,v.s+travel,speed))
                continue
            if v.reason in ('delayed_response','hesitating','bus_stop_dwell') and not v.permit:
                cruise=0.
            if v.oncoming_brake:cruise=0.
            target = min(cruise, math.sqrt(2*v.spec.braking*max(0., available)))
            speed = min(target, v.speed+v.spec.acceleration*min(1.,v.driver.acceleration)*STEP) if target >= v.speed else max(target, v.speed-v.spec.braking*STEP)
            hard_gap=self._gap(v,snapshot,preferred=False)
            travel=min(speed*STEP,max(0.,available))
            if self.mode == 'supervised' or v.reason != 'unsafe_gap_accepted':
                travel=self.supervisor.limit_travel(v,travel,hard_gap)
            if travel < speed*STEP:
                speed = travel/STEP
            updates.append((v, v.s+travel, speed))
        updates=self.supervisor.movement(self,updates) if self.mode=='supervised' else collide(self,updates)
        finished = []
        for v, s, speed in updates:
            self.behaviour_audit.motion(self,v,max(0.,s-v.s))
            self.metrics.distance+=max(0.,s-v.s)
            self.metrics.exposure+=STEP
            if v.dwell>0: self.metrics.dwell+=STEP
            elif speed<.05: self.metrics.wait+=STEP
            v.executed='crashed' if v.crashed else ('wait' if s-v.s<1e-8 else ('brake' if speed<v.speed-1e-6 else 'proceed'))
            v.s, v.speed = s, speed
            if self.mode=='accident' and v.driver.kind!='Normal' and not v.crashed:
                p=self.network.paths[v.path_id]
                if p.kind=='lane' and not v.manoeuvre and v.index+1<len(v.route) and not v.permit and v.s>=p.length-v.spec.length/2:
                    v.permit=v.route[v.index+1]
                    cp=self.network.paths[v.permit]
                    if cp.kind=='signal' and self.signals[cp.junction].light(cp.approach)=='red':
                        occupied=any(w is not v and w.permit and
                            self.network.conflict(cp.id,v.spec,w.permit,w.spec) for w in self.vehicles)
                        e=self.behaviour_audit.decision(self,v,'late_signal_entry',occupied)
                        e['executed']=True
            if v.recent: v.recent[-1]['executed']=v.executed
            if not v.crashed and v.index == len(v.route)-1 and v.end_s is not None and v.s>=v.end_s-.01 and speed<.1 and v.dwell<=0 and self.bus_stop(v) is None:
                finished.append(v.id)
                continue
            while not v.crashed and not v.manoeuvre and v.s >= self.network.paths[v.path_id].length:
                v.s -= self.network.paths[v.path_id].length
                if v.index == len(v.route)-1:
                    finished.append(v.id)
                    break
                v.index += 1
                self.metrics.enter(v,self.network)
        self.remove_vehicles(finished,'trip_completion')
        if self.ticks % DECISION_STEPS == 0 and self.pending:
            self._admit_demand()
        self.ticks += 1
        self.elapsed = self.ticks*STEP
        self.flow_audit.sample(self)
