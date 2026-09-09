"""Explicit sedan opposing-lane paths; never a same-lane speed trick."""
import math
from .network import Path
from .profiles import PARAMETERS
from .demand import ACCESS,BUS_STOPS
from .behaviour import opportunity


def base_position(sim,v):
    base=v.manoeuvre['base'] if v.manoeuvre else v.path_id
    p=sim.network.paths[base]
    x,z,yaw=p.pose(0);xx,zz,_=sim.pose(v)
    f=(math.sin(math.radians(yaw)),math.cos(math.radians(yaw)))
    return base,(xx-x)*f[0]+(zz-z)*f[1],-(xx-x)*f[1]+(zz-z)*f[0]


def excluded(sim,base):
    p=sim.network.paths[base]
    reverse=f'{p.target}>{p.source}'
    forbidden={a.lane for a in sim.network.access.values()}|set(BUS_STOPS)
    return base in forbidden or reverse in forbidden or p.source in sim.network.portals or p.target in sim.network.portals


def road_window(sim,base,s):
    """Uninterrupted road section outside physical access/stop protection zones."""
    p=sim.network.paths[base]
    if p.kind!='lane' or p.source in sim.network.portals or p.target in sim.network.portals:return None
    reverse=f'{p.target}>{p.source}'
    locations=[a.s if a.lane==base else p.length-a.s for a in sim.network.access.values() if a.lane in (base,reverse)]
    locations += [pos if lane==base else p.length-pos for lane,(_,pos) in BUS_STOPS.items() if lane in (base,reverse)]
    radius=PARAMETERS['overtaking'].get('access_buffer',14.)
    start=0.
    for lo,hi in sorted((max(0.,pos-radius),min(p.length,pos+radius)) for pos in locations):
        if start<=s<lo:return start,lo
        start=max(start,hi)
    return (start,p.length) if start<=s<=p.length else None


def corridor(sim,v):
    base,s,lateral=base_position(sim,v)
    p=sim.network.paths[base]
    x,z,yaw=p.pose(0);f=(math.sin(math.radians(yaw)),math.cos(math.radians(yaw)))
    leader=None;lead_s=math.inf;oncoming=math.inf;closing=0.;return_clear=True
    for w in sim.vehicles:
        if w is v:continue
        xx,zz,wyaw=sim.pose(w)
        ws=(xx-x)*f[0]+(zz-z)*f[1]
        side=-(xx-x)*f[1]+(zz-z)*f[0]
        if abs(side)<1.2:
            if s<ws<lead_s:leader=w;lead_s=ws
            if abs(ws-s)<(w.spec.length+v.spec.length)/2+v.driver.gap+1:return_clear=False
        dot=math.cos(math.radians(wyaw-yaw))
        if 3.5<side<6.5 and ws>s and dot<-.5:
            if ws-s<oncoming:
                oncoming=ws-s-(v.spec.length+w.spec.length)/2;closing=v.speed+w.speed
    return leader,lead_s,oncoming,closing,return_clear


def install(sim,v,returning=False):
    """Cubic with current heading and a lane-parallel end; dense explicit polyline."""
    cfg=PARAMETERS['overtaking']
    base,s,lateral=base_position(sim,v);p=sim.network.paths[base]
    start=sim.pose(v);yaw=p.pose(0)[2]
    f=(math.sin(math.radians(yaw)),math.cos(math.radians(yaw)));left=(-f[1],f[0])
    length=cfg['shift_length']
    end_s=s+length
    limit=v.manoeuvre.get('end_limit',p.length)
    if end_s>limit-cfg['end_buffer']:return False
    endpoint=p.pose(end_s)
    target_lateral=0. if returning else 5.
    end=(endpoint[0]+left[0]*target_lateral,endpoint[1]+left[1]*target_lateral)
    h=(math.sin(math.radians(start[2])),math.cos(math.radians(start[2])))
    control=length/3
    a=start[:2];b=(a[0]+h[0]*control,a[1]+h[1]*control)
    c=(end[0]-f[0]*control,end[1]-f[1]*control)
    points=[]
    for i in range(121):
        t=i/120
        points.append(tuple((1-t)**3*a[k]+3*(1-t)**2*t*b[k]+3*(1-t)*t*t*c[k]+t**3*end[k] for k in (0,1)))
    tail_s=p.length if returning else limit-cfg['end_buffer']
    tail=p.pose(tail_s)
    if tail_s>end_s+1e-6:points.append((tail[0]+left[0]*target_lateral,tail[1]+left[1]*target_lateral))
    serial=v.manoeuvre.get('serial',0)+1
    pid=f'ot:{v.id}:{serial}'
    path=Path(pid,points,source=p.source,target=p.target)
    sim.network.paths[pid]=path
    if not sim.network.supports((pid,),v.spec):
        del sim.network.paths[pid]
        return False
    v.manoeuvre.update(serial=serial,shift_end=path.distances[120],returning=returning)
    v.route=v.route[:v.index]+(pid,)+v.route[v.index+1:]
    v.s=0.
    return True


def decide(sim,v):
    if v.manoeuvre_mode=='wrong_way':return
    if v.crashed or sim.mode!='accident' or not PARAMETERS['overtaking']['enabled']:return
    if v.driver.kind!='Drunk' or v.driver.subgroup!='higher_risk' or v.spec.kind!='Sedan':return
    cfg=PARAMETERS['overtaking']
    base,s,side=base_position(sim,v);p=sim.network.paths[base]
    if p.kind!='lane':return
    leader,lead_s,incoming,closing,return_clear=corridor(sim,v)
    # Delay oncoming recognition and bias its estimated arrival time.
    v.oncoming_history.append((sim.elapsed,incoming,closing))
    while len(v.oncoming_history)>1 and v.oncoming_history[1][0]<=sim.elapsed-v.driver.reaction:v.oncoming_history.popleft()
    _,old_gap,old_closing=v.oncoming_history[0]
    estimate=old_gap*v.driver.gap_bias/max(.1,old_closing*v.driver.closing_bias)
    actual=incoming/max(.1,closing)
    required=(2*cfg['shift_length']+cfg['pass_length'])/max(4.,v.desired_speed)+cfg['oncoming_margin_s']
    oncoming_clear=estimate>required
    if v.manoeuvre:
        if v.passing_state=='move_out' and v.s>=v.manoeuvre['shift_end']:v.passing_state='pass'
        if v.passing_state in ('return','abort') and v.s>=v.manoeuvre['shift_end']:
            original=v.manoeuvre['route']
            base,s,_=base_position(sim,v)
            v.route=original;v.s=s
            result='aborts' if v.passing_state=='abort' else 'completions'
            sim.behaviour_audit.passing[result]+=1
            sim.flow_audit.mark(v,'overtaking',result)
            v.manoeuvre=None;v.passing_state='follow';v.passing_reason='overtaking_'+result
            return
        passed=not any(w.id==v.manoeuvre['leader'] and base_position(sim,w)[0]==base and
                       base_position(sim,w)[1]>s-(v.spec.length+w.spec.length)/2-v.driver.gap for w in sim.vehicles)
        state,reason=sim.rules.passing(v.passing_state,True,True,oncoming_clear,return_clear,passed)
        if state in ('return','abort') and state!=v.passing_state:
            if install(sim,v,returning=True):v.passing_state=state;v.passing_reason=reason
        elif reason=='overtaking_late_braking':v.passing_reason=reason
        elif reason=='overtaking_hold' and v.passing_reason=='overtaking_late_braking':v.passing_reason='overtaking_gap_accepted'
        return
    encounter=('pass',v.index,leader.id if leader else None)
    window=road_window(sim,base,s)
    eligible=(encounter not in v.used_manoeuvres and window is not None and leader is not None and not leader.crashed and
        cfg['minimum_leader_speed']<=leader.speed<=cfg['maximum_leader_speed'] and
        v.desired_speed-leader.speed>=cfg['minimum_speed_advantage'] and
        s>=window[0] and window[1]-s>=2*cfg['shift_length']+(0 if v.passing_state=='assess' else cfg['pass_length'])+cfg['end_buffer'] and
        0<lead_s-s<cfg['leader_distance'] and v.speed>=2.)
    willing=False
    if eligible:
        sim.flow_audit.opportunity(v,'overtaking',leader.id)
        willing=opportunity(v,('pass',v.index,leader.id),v.driver.overtake)
        sim.flow_audit.mark(v,'overtaking','eligible_encounters')
        if not willing:sim.flow_audit.mark(v,'overtaking','personality_declined')
    state,reason=sim.rules.passing(v.passing_state,eligible,willing,oncoming_clear,False,False)
    if state=='assess' and v.passing_state=='follow':
        sim.behaviour_audit.passing['assessments']+=1
        sim.flow_audit.mark(v,'overtaking','selected_assessment')
        v.assess_until=sim.elapsed+cfg['assessment_seconds']
    if v.passing_state=='assess' and sim.elapsed<v.assess_until:return
    if state=='move_out' and s<window[0]+cfg['start_buffer']:return
    if state=='move_out':
        v.used_manoeuvres.add(encounter)
        v.manoeuvre=dict(base=base,route=v.route,leader=leader.id,serial=0,returning=False,
                         start_limit=window[0],end_limit=window[1])
        if install(sim,v):
            sim.behaviour_audit.passing['attempts']+=1
            reason='overtaking_gap_misjudged' if actual<=required else reason
            sim.behaviour_audit.decision(sim,v,reason,actual<=required)
        else:
            v.manoeuvre=None;state='follow';reason='overtaking_geometry_rejected'
    elif state=='follow' and v.passing_state=='assess':
        sim.behaviour_audit.passing['aborts']+=1
        v.used_manoeuvres.add(encounter)
        sim.flow_audit.mark(v,'overtaking','assessment_declined')
    v.passing_state=state;v.passing_reason=reason


def valid(sim,v):
    if getattr(sim.network,'lane_count',2)==4:
        from .four_wrong_way import valid as four_valid
        return four_valid(sim,v)
    p=sim.network.paths[v.path_id]
    if not math.isfinite(v.s+v.speed) or not 0<=v.s<=p.length+1e-6:return False
    if not v.manoeuvre:return not v.path_id.startswith('ot:')
    base,s,side=base_position(sim,v)
    delta=math.radians(sim.pose(v)[2]-sim.network.paths[base].pose(0)[2])
    lateral_extent=abs(math.sin(delta))*v.spec.length/2+abs(math.cos(delta))*v.spec.width/2
    forward_extent=abs(math.cos(delta))*v.spec.length/2+abs(math.sin(delta))*v.spec.width/2
    return (v.spec.kind=='Sedan' and road_window(sim,base,s) is not None and
            v.manoeuvre.get('start_limit',0)+forward_extent-.001<=s<=v.manoeuvre.get('end_limit',sim.network.paths[base].length)-forward_extent+.001 and
            -.05<=side<=5.05 and side-lateral_extent>=-2.5 and side+lateral_extent<=7.5)
