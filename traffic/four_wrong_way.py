"""Wrong-way travel from the inner lane, physically across the centre line."""
import math
from .network import Path,add,bezier
from .profiles import PARAMETERS
from .behaviour import opportunity
from .lane_changes import coordinate,event,target_gaps


def install(sim,v,returning=False):
    m=v.manoeuvre;r=sim.network.roads[m['road']]
    shift=PARAMETERS['wrong_way']['four_lane_shift_length']
    s=coordinate(sim,v)[2];end_s=s+shift
    if end_s>m['limit']-4:return False
    start=sim.pose(v);f=r['forward'];right=r['right']
    end=add(add(r['start'],f,end_s),right,1.75 if returning else -1.75)
    h=(math.sin(math.radians(start[2])),math.cos(math.radians(start[2])))
    points=bezier(start[:2],add(start[:2],h,shift/3),add(end,f,-shift/3),end,120)
    shift_length=sum(math.dist(a,b) for a,b in zip(points,points[1:]))
    tail=r['length'] if returning else m['limit']
    if tail>end_s:points.append(add(add(r['start'],f,tail),right,1.75 if returning else -1.75))
    serial=m.get('serial',0)+1;pid=f'ot:{v.id}:ww:{serial}'
    p=Path(pid,points,'opposing',r['source'],r['target']);p.road=m['road'];p.lane='inner';p.end_s=tail
    sim.network.paths[pid]=p
    if not sim.network.supports((pid,),v.spec):del sim.network.paths[pid];return False
    m.update(serial=serial,shift_end=shift_length,returning=returning)
    v.route=v.route[:v.index]+(pid,)+v.route[v.index+1:];v.s=0
    return True


def decide(sim,v):
    if v.driver.kind!='Drunk':return
    audit=sim.flow_audit
    audit.mark(v,'wrong_way','drunk_route_encounters')
    if v.driver.subgroup!='higher_risk':audit.mark(v,'wrong_way','reject_personality');return
    if v.spec.kind!='Sedan':audit.mark(v,'wrong_way','reject_vehicle_type');return
    if v.crashed or sim.mode!='accident' or not PARAMETERS['wrong_way']['enabled']:return
    p=sim.network.paths[v.path_id];loc=coordinate(sim,v)
    if loc is None:audit.mark(v,'wrong_way','reject_connector');return
    road,lane,s=loc;r=sim.network.roads[road]
    gap=math.inf;closing=0.
    x,z,_=sim.pose(v);f=r['forward'];right=r['right']
    for w in sim.vehicles:
        if w is v:continue
        wx,wz,yaw=sim.pose(w);ahead=(wx-x)*f[0]+(wz-z)*f[1]
        side=(wx-r['start'][0])*right[0]+(wz-r['start'][1])*right[1]
        dot=math.sin(math.radians(yaw))*f[0]+math.cos(math.radians(yaw))*f[1]
        if ahead>0 and abs(side+1.75)<2 and dot<-.5 and ahead<gap:
            gap=ahead-(v.spec.length+w.spec.length)/2;closing=v.speed+w.speed
    v.oncoming_history.append((sim.elapsed,gap,closing))
    while len(v.oncoming_history)>1 and v.oncoming_history[1][0]<=sim.elapsed-v.driver.reaction:v.oncoming_history.popleft()
    _,old_gap,old_closing=v.oncoming_history[0]
    clear=old_gap*v.driver.gap_bias/max(.1,old_closing*v.driver.closing_bias)>PARAMETERS['wrong_way']['four_lane_oncoming_ttc']
    return_clear,*_=target_gaps(sim,v,road,'inner',s)
    if v.manoeuvre:
        m=v.manoeuvre
        if v.passing_state=='move_out' and v.s>=m['shift_end']:
            v.passing_state='wrong_way';m['until']=sim.elapsed+m['duration'];event(sim,v,'wrong_way','sustained')
        if v.passing_state=='return' and v.s>=m['shift_end']:
            v.route=m['route'];v.s=s-sim.network.paths[v.path_id].start_s
            event(sim,v,'wrong_way','completion');v.manoeuvre=None;v.passing_state='follow';v.manoeuvre_mode='overtaking'
            v.change_after=sim.elapsed+8;return
        due=sim.elapsed>=m.get('until',math.inf) or s>=m['limit']-22
        state,reason=sim.rules.wrong_way(v.passing_state,True,True,due,clear,return_clear)
        if state=='return' and v.passing_state!='return':
            if install(sim,v,True):v.passing_state=state
            else:reason='wrong_way_braking'
        v.passing_reason=reason;sim.behaviour_audit.decision(sim,v,reason,gap<20)
        return
    token=('four_wrong_way',v.index)
    if token in v.used_manoeuvres or v.lane_change or v.change_grant:return
    audit.mark(v,'wrong_way','higher_risk_sedan_lane_encounters')
    eligible=p.kind=='lane' and p.id==sim.network.segments[road,'inner'][-1] and lane=='inner' and not r['merge'] and not r['split'] and v.speed>=1
    if lane!='inner':audit.mark(v,'wrong_way','reject_lane')
    limit=r['length']-8
    for a in sim.network.access.values():
        ap=sim.network.paths[a.lane]
        if ap.road==road:
            pos=ap.start_s+a.s
            if abs(pos-s)<14:eligible=False;audit.mark(v,'wrong_way','reject_access')
            if pos>s:limit=min(limit,pos-14)
    if limit-s<PARAMETERS['wrong_way']['four_lane_minimum_room']:eligible=False;audit.mark(v,'wrong_way','reject_remaining_length')
    if not eligible:
        if v.passing_state=='assess' and v.manoeuvre_mode=='wrong_way':
            event(sim,v,'wrong_way','abort');v.used_manoeuvres.add(token)
            v.passing_state='follow';v.manoeuvre_mode='overtaking'
        return
    audit.mark(v,'wrong_way','eligible_encounters')
    if v.passing_state!='assess':
        event(sim,v,'wrong_way','opportunity')
        if not opportunity(v,token,v.driver.wrong_way):
            v.used_manoeuvres.add(token);event(sim,v,'wrong_way','declined');return
        state,reason=sim.rules.wrong_way('follow',True,True,False,clear,return_clear)
        v.passing_state=state;v.passing_reason=reason;v.manoeuvre_mode='wrong_way'
        v.assess_until=sim.elapsed+PARAMETERS['wrong_way']['assessment_seconds'];event(sim,v,'wrong_way','selected');return
    if sim.elapsed<v.assess_until:return
    state,reason=sim.rules.wrong_way('assess',True,True,False,clear,return_clear)
    v.used_manoeuvres.add(token)
    if state=='move_out':
        v.manoeuvre=dict(road=road,base=p.id,route=v.route,limit=limit,duration=v.behaviour_rng.uniform(*PARAMETERS['wrong_way']['duration']))
        if install(sim,v):
            v.passing_state=state;v.passing_reason=reason;event(sim,v,'wrong_way','attempt')
            sim.behaviour_audit.decision(sim,v,reason,gap/max(.1,closing)<5);return
        v.manoeuvre=None
    event(sim,v,'wrong_way','abort');v.passing_state='follow';v.manoeuvre_mode='overtaking'


def valid(sim,v):
    p=sim.network.paths[v.path_id]
    if not math.isfinite(v.s+v.speed) or not -.001<=v.s<=p.length+.001:return False
    loc=coordinate(sim,v)
    if loc is None:return True
    road,lane,s=loc;r=sim.network.roads[road];x,z,yaw=sim.pose(v)
    side=(x-r['start'][0])*r['right'][0]+(z-r['start'][1])*r['right'][1]
    angle=math.radians(yaw)-math.atan2(r['forward'][0],r['forward'][1])
    extent=abs(math.sin(angle))*v.spec.length/2+abs(math.cos(angle))*v.spec.width/2
    return abs(side)+extent<=7.001
