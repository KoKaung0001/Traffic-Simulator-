"""Seeded personalities are immutable; perception and episodes evolve in sim time."""
import math
import random
from collections import Counter,defaultdict
from dataclasses import asdict
from .profiles import PARAMETERS


RISK_REASONS={'signal_violation','unsafe_gap_accepted','late_braking',
              'acceleration_overshoot','speed_surge','late_signal_entry',
              'overtaking_gap_misjudged','overtaking_gap_accepted',
              'centre_line_crossing','sustained_wrong_way','wrong_way_braking'}


class BehaviourAudit:
    def __init__(self):
        self.admitted={}
        self.events={}
        self.by_vehicle=defaultdict(list)
        self.passing=Counter()

    def admit(self,v):
        self.admitted[v.id]=dict(profile=v.driver.kind,subgroup=v.driver.subgroup,type=v.spec.kind,traits=asdict(v.driver))

    def decision(self,sim,v,reason,conflict=False):
        if reason not in RISK_REASONS:return
        if reason=='late_braking' and (v.speed<.5 or
            v.actual_gap-v.driver.gap>=v.speed*v.speed/(2*v.spec.braking)):
            return  # Do not inflate risk counts with ordinary red-light braking/creep.
        token=v.index if reason in ('signal_violation','unsafe_gap_accepted','late_signal_entry') else v.epoch
        key=(v.id,token,reason)
        if key not in self.events:
            self.events[key]=dict(id=v.id,profile=v.driver.kind,subgroup=v.driver.subgroup,
                time=sim.elapsed,path=v.path_id,reason=reason,actual_gap=finite(v.actual_gap),
                perceived_gap=finite(v.perceived_gap),conflicting=False,executed=False,contact=False)
            self.by_vehicle[v.id].append(self.events[key])
        e=self.events[key]
        e['last']=sim.elapsed
        e['conflicting'] |= conflict
        return e

    def motion(self,sim,v,distance):
        for e in self.by_vehicle[v.id]:
            if sim.elapsed-e['last']>2:continue
            if v.crashed:e['contact']=True
            if e['reason'] in (v.reason,v.control_reason,v.passing_reason) and distance>1e-8:e['executed']=True

    def values(self):
        return dict(admitted_profiles=dict(Counter(x['profile'] for x in self.admitted.values())),
            admitted_subgroups=dict(Counter(x['profile']+'/'+x['subgroup'] for x in self.admitted.values())),
            risky_decisions=dict(Counter(e['reason'] for e in self.events.values())),
            risky_executed=dict(Counter(e['reason'] for e in self.events.values() if e['executed'])),
            risky_conflicts=dict(Counter(e['reason'] for e in self.events.values() if e['conflicting'])),
            risky_with_contact=dict(Counter(e['reason'] for e in self.events.values() if e['contact'])),
            overtaking=dict(self.passing))


def finite(n):
    return n if math.isfinite(n) else None


def observe(sim,v,snapshot):
    gap=sim._gap(v,snapshot)+v.driver.gap
    closing=0.;leader=None
    path=sim.network.paths[v.path_id]
    # Perception of moving leaders uses current geometric corridor, then delays it.
    poses=sim.observation_poses
    x,z,yaw=poses[v.id];r=math.radians(yaw);forward=(math.sin(r),math.cos(r))
    for w,_,_ in snapshot:
        if w is v:continue
        xx,zz,_=poses[w.id]
        along=(xx-x)*forward[0]+(zz-z)*forward[1]
        lateral=abs((xx-x)*forward[1]-(zz-z)*forward[0])
        if along>0 and lateral<(v.spec.width+w.spec.width)/2+.25:
            distance=along-(v.spec.length+w.spec.length)/2
            if distance<=gap+.01:
                gap=distance;leader=w.id
                wy=math.radians(poses[w.id][2])
                closing=v.speed-w.speed*(math.sin(wy)*forward[0]+math.cos(wy)*forward[1])
        if w.crashed and math.dist((x,z),(xx,zz))<40:
            from .collisions import contact
            hit=contact(sim,v,40,w,0)
            if hit is not None and hit*40<gap:
                gap=hit*40;closing=v.speed;leader=w.id
    v.actual_gap=gap;v.actual_closing=closing
    v.perception.append((sim.elapsed,v.index,gap,closing,leader))
    while len(v.perception)>1 and v.perception[1][0]<=sim.elapsed-v.driver.reaction:
        v.perception.popleft()
    stamp,index,old_gap,old_closing,old_leader=v.perception[0]
    v.perception_ready=stamp<=sim.elapsed-v.driver.reaction+1e-8 and index==v.index
    v.perceived_gap=old_gap*v.driver.gap_bias
    v.perceived_closing=old_closing*v.driver.closing_bias
    v.perceived_leader=old_leader


def opportunity(v,key,chance):
    """Exactly one draw per approach or encountered leader, never per stopped tick."""
    if key not in v.opportunities:
        v.opportunities[key]=v.behaviour_rng.random()<chance
    return v.opportunities[key]


def propose(sim,v,observation,larger_gap):
    if v.behaviour_rng is None:v.behaviour_rng=random.Random(sim.seed*1000003+v.id)
    rng=v.behaviour_rng
    if sim.elapsed>=v.next_behaviour:
        v.epoch+=1
        v.next_behaviour=sim.elapsed+rng.uniform(*PARAMETERS['behaviour_interval'])
        v.episode='steady'
        if rng.random()<v.driver.hesitation:
            v.hesitation_until=sim.elapsed+rng.uniform(.8,1.8)
            v.episode='hesitation'
        elif rng.random()<v.driver.overshoot:
            v.episode='pedal_overshoot'
        elif v.driver.kind=='Drunk' and rng.random()<.3:
            v.episode='surge'
        v.speed_variation=rng.uniform(1.03,1.15) if v.episode=='surge' else 1.
    if v.episode=='hesitation' and sim.elapsed>=v.hesitation_until:
        v.episode='restart_overshoot' if v.driver.subgroup=='unsteady' else 'steady'
    v.history.append((sim.elapsed,v.index,observation,larger_gap))
    while len(v.history)>1 and v.history[1][0]<=sim.elapsed-v.driver.reaction:v.history.popleft()
    stamp,index,observed,large=v.history[0]
    ready=stamp<=sim.elapsed-v.driver.reaction+1e-8 and index==v.index
    observed=list(observed)
    if v.permit:
        observed[1]=True  # Own commitment is current; external perception stays delayed.
    if v.perception:
        observed[4]=v.perceived_gap-v.driver.gap>max(.05,v.perceived_closing*.6)
        large=v.perceived_gap>v.driver.gap+v.driver.entry_gap
    if observed[0]=='red' and observed[5]=='signal':
        v.risky_signal=opportunity(v,('signal',v.index),v.driver.signal_risk)
    else:v.risky_signal=False
    if not all(observed[i] for i in (3,4,7,8)):
        key=('gap',v.index) if observed[5]!='road' else ('leader',v.index,v.perceived_leader)
        v.risky_gap=opportunity(v,key,v.driver.gap_risk)
    else:v.risky_gap=False
    v.action,v.reason=sim.rules.behave(tuple(observed),v.driver.kind,ready=ready,
        larger_gap=large,hesitation=v.speed<.05 and sim.elapsed<v.hesitation_until,
        risk_signal=v.risky_signal,risk_gap=v.risky_gap,dwell=v.dwell>0)
    effective_gap=v.perceived_gap-v.driver.gap
    if v.reason=='unsafe_gap_accepted':effective_gap=math.inf
    base=v.action
    if base in ('wait','stop') and sim.network.paths[v.path_id].kind=='lane':
        stop_gap=sim.network.paths[v.path_id].length-v.spec.length/2-.5-v.s
        effective_gap=min(effective_gap,stop_gap)
        base='proceed'  # Approach the known stop line while responding to the perceived signal.
    v.control,v.control_reason=sim.rules.drive(base,
        v.reason in ('delayed_response','hesitating','bus_stop_dwell'),effective_gap,
        v.perceived_closing,v.speed,v.spec.braking*v.driver.braking,
        v.episode in ('pedal_overshoot','restart_overshoot'),v.episode=='surge')
    v.executed=v.action;v.intervention=''
    v.recent.append(dict(time=sim.elapsed,path=v.path_id,signal=observation[0],
        observed_signal=observed[0],action=v.action,reason=v.reason,control=v.control,
        control_reason=v.control_reason,actual_gap=finite(v.actual_gap),perceived_gap=finite(v.perceived_gap),
        episode=v.episode,executed=v.executed))
    conflict=v.actual_gap<v.speed*v.speed/(2*v.spec.braking)+v.driver.gap or not all(observation[i] for i in (3,7,8))
    sim.behaviour_audit.decision(sim,v,v.reason,conflict)
    sim.behaviour_audit.decision(sim,v,v.control_reason,conflict)
