"""Seeded opposing-lane episodes on explicit, collision-visible road paths."""
import math
from .profiles import PARAMETERS
from .behaviour import opportunity
from .overtaking import base_position,corridor,install,road_window


def decide(sim,v):
    cfg=PARAMETERS['wrong_way']
    if (sim.mode!='accident' or v.crashed or not cfg['enabled'] or
        v.driver.kind!='Drunk' or v.driver.subgroup!='higher_risk' or
        v.spec.kind!='Sedan' or v.driver.wrong_way<=0):return
    if v.manoeuvre and v.manoeuvre_mode!='wrong_way':return
    if v.passing_state!='follow' and v.manoeuvre_mode!='wrong_way':return
    base,s,side=base_position(sim,v);p=sim.network.paths[base]
    if p.kind!='lane':return
    _,_,gap,closing,return_clear=corridor(sim,v)
    # Overtaking already samples this corridor until a wrong-way episode owns it.
    if v.manoeuvre_mode=='wrong_way':
        v.oncoming_history.append((sim.elapsed,gap,closing))
        while len(v.oncoming_history)>1 and v.oncoming_history[1][0]<=sim.elapsed-v.driver.reaction:
            v.oncoming_history.popleft()
    old=v.oncoming_history[0] if v.oncoming_history else (sim.elapsed,gap,closing)
    estimate=old[1]*v.driver.gap_bias/max(.1,old[2]*v.driver.closing_bias)
    clear=estimate>4.
    shift=PARAMETERS['overtaking']['shift_length']
    buffer=PARAMETERS['overtaking']['end_buffer']
    if v.manoeuvre:
        if v.passing_state=='move_out' and v.s>=v.manoeuvre['shift_end']:
            v.passing_state='wrong_way'
            v.manoeuvre['until']=sim.elapsed+v.manoeuvre['duration']
            sim.behaviour_audit.passing['wrong_way_episodes']+=1
        if v.passing_state=='return' and v.s>=v.manoeuvre['shift_end']:
            v.route=v.manoeuvre['route'];v.s=s;v.manoeuvre=None
            v.passing_state='follow';v.manoeuvre_mode='overtaking';v.passing_reason='wrong_way_completed'
            sim.behaviour_audit.passing['wrong_way_returns']+=1
            sim.flow_audit.mark(v,'wrong_way','completions')
            return
        due=sim.elapsed>=v.manoeuvre.get('until',math.inf) or s>=v.manoeuvre.get('end_limit',p.length)-shift-buffer-1.
        state,reason=sim.rules.wrong_way(v.passing_state,True,True,due,clear,return_clear)
        if state=='return' and v.passing_state!='return':
            if install(sim,v,returning=True):v.passing_state=state
            else:reason='wrong_way_braking'
        v.passing_reason=reason
        sim.behaviour_audit.decision(sim,v,reason,gap<20)
        return
    encounter=('wrong_way',v.index)
    minimum=2*shift+buffer if v.passing_state=='assess' else cfg['minimum_straight']
    window=road_window(sim,base,s)
    eligible=(encounter not in v.used_manoeuvres and window is not None and window[0]<=s<=window[1]-minimum and
              v.speed>=1. and not v.permit)
    willing=opportunity(v,('wrong_way',v.index),v.driver.wrong_way) if eligible else False
    if eligible:
        sim.flow_audit.opportunity(v,'wrong_way',v.index)
        sim.flow_audit.mark(v,'wrong_way','eligible_encounters')
        if not willing:sim.flow_audit.mark(v,'wrong_way','personality_declined')
    state,reason=sim.rules.wrong_way(v.passing_state,eligible,willing,False,clear,return_clear)
    if state=='assess' and v.passing_state=='follow':
        v.assess_until=sim.elapsed+cfg['assessment_seconds'];v.manoeuvre_mode='wrong_way'
        sim.behaviour_audit.passing['wrong_way_assessments']+=1
        sim.flow_audit.mark(v,'wrong_way','selected_assessment')
    if v.passing_state=='assess' and (sim.elapsed<v.assess_until or (window and s<window[0]+PARAMETERS['overtaking']['start_buffer'])):return
    if state=='move_out':
        v.used_manoeuvres.add(encounter)
        v.manoeuvre=dict(base=base,route=v.route,leader=None,serial=0,returning=False,
                        duration=v.behaviour_rng.uniform(*cfg['duration']),start_limit=window[0],end_limit=window[1])
        if install(sim,v):
            sim.behaviour_audit.passing['wrong_way_attempts']+=1
            sim.behaviour_audit.decision(sim,v,reason,gap/max(.1,closing)<4)
        else:v.manoeuvre=None;state='follow';reason='wrong_way_geometry_rejected'
    if state=='follow' and v.passing_state=='assess':
        v.used_manoeuvres.add(encounter)
        sim.flow_audit.mark(v,'wrong_way','assessment_declined')
    v.passing_state=state;v.passing_reason=reason
    if state=='follow':v.manoeuvre_mode='overtaking'


def observe_oncoming(sim,v):
    """Normal response to wrong-way traffic uses delayed sight and bounded braking.

    Ordinary following/reservation protections are unchanged. This extra hazard
    is deliberately not fed into the instantaneous hard following-gap clamp.
    """
    if v.driver.kind!='Normal' or v.crashed:return
    if not sim.wrong_way_actors and not v.threat_history:return
    x,z,yaw=sim.pose(v);angle=math.radians(yaw);f=(math.sin(angle),math.cos(angle))
    gap=math.inf;closing=0.
    for w in sim.wrong_way_actors:
        if w is v or not w.manoeuvre or w.manoeuvre_mode!='wrong_way':continue
        xx,zz,wyaw=sim.pose(w);front=(xx-x)*f[0]+(zz-z)*f[1]
        side=abs((xx-x)*f[1]-(zz-z)*f[0])
        dot=math.cos(math.radians(wyaw-yaw))
        if front>0 and dot<-.5 and side<(v.spec.width+w.spec.width)/2+.4:
            g=front-(v.spec.length+w.spec.length)/2
            if g<gap:gap=g;closing=v.speed-w.speed*dot
    v.threat_history.append((sim.elapsed,gap,closing))
    while len(v.threat_history)>1 and v.threat_history[1][0]<=sim.elapsed-v.driver.reaction:
        v.threat_history.popleft()
    stamp,seen,rate=v.threat_history[0]
    ready=stamp<=sim.elapsed-v.driver.reaction+1e-8
    action,reason=sim.rules.drive('proceed',False,seen-v.driver.gap,rate,v.speed,v.spec.braking,False,False)
    v.oncoming_brake=ready and action=='brake'
    if math.isfinite(gap) or math.isfinite(seen):
        v.actual_gap=min(v.actual_gap,gap);v.perceived_gap=min(v.perceived_gap,seen)
    if v.oncoming_brake:
        v.action='brake';v.reason='oncoming_wrong_way';v.control_reason=reason
        v.recent.append(dict(time=sim.elapsed,path=v.path_id,action='brake',reason=v.reason,
                            actual_gap=gap,perceived_gap=seen,executed=v.executed))
