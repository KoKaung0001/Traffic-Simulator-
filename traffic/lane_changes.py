"""Physical same-direction changes, deterministic claims and approach merges."""
import math
from collections import Counter,deque
from .behaviour import opportunity
from .profiles import PARAMETERS


def coordinate(sim,v):
    p=sim.network.paths[v.path_id]
    if not hasattr(p,'road'):return None
    r=sim.network.roads[p.road];x,z,_=sim.pose(v)
    s=(x-r['start'][0])*r['forward'][0]+(z-r['start'][1])*r['forward'][1]
    return p.road,p.lane,s


def occupants(sim,v):
    loc=coordinate(sim,v)
    if loc is None:return ()
    road,lane,s=loc;p=sim.network.paths[v.path_id]
    lanes=('inner','outer') if p.kind=='lane_change' or (v.change_grant and p.end_s-s<v.spec.length/2+3) else (lane,)
    return tuple((road,k,s) for k in lanes)


def build_index(sim):
    from collections import defaultdict
    sim.path_index=defaultdict(list);sim.road_index=defaultdict(list);sim.connector_tails=defaultdict(list)
    for v in sim.vehicles:
        sim.path_index[v.path_id].append((v,v.s))
        p=sim.network.paths[v.path_id]
        if p.kind in ('signal','roundabout'):sim.connector_tails[p.incoming].append((v,v.s))
        for road,lane,s in occupants(sim,v):sim.road_index[road,lane].append((v,s))


def following_gap(sim,v,snapshot,preferred=True):
    distance=math.inf;offset=-v.s;net=sim.network
    # Shared route tails include different connectors leaving the same lane.
    for pid in v.route[v.index:v.index+6]:
        path=net.paths[pid]
        # A roundabout exit initially occupies one shared physical lane even
        # though the route already names its eventual inner/outer destination.
        if path.kind=='lane' and net.roads[path.road]['split'] and path.start_s<16:
            for slot in ('inner','outer'):
                for w,ws in sim.road_index[path.road,slot]:
                    if w is v or ws>16+w.spec.length/2:continue
                    d=offset+ws-path.start_s
                    if d>0:distance=min(distance,d-(v.spec.length+w.spec.length)/2)
        for w,ws in sim.path_index[pid]:
            if w is v:continue
            if offset+ws>0:distance=min(distance,offset+ws-(v.spec.length+w.spec.length)/2)
        for w,ws in sim.connector_tails[pid]:
            if w is v:continue
            d=offset+net.paths[pid].length+ws
            if d>0:distance=min(distance,d-(v.spec.length+w.spec.length)/2)
        offset+=net.paths[pid].length
    own=occupants(sim,v)
    for road,lane,s in own:
        r=net.roads[road]
        slots=(lane,'inner' if lane=='outer' else 'outer') if r['merge'] or r['split'] else (lane,)
        for slot in slots:
            for w,ws in sim.road_index[road,slot]:
                if w is v or (w.manoeuvre and w.manoeuvre_mode=='wrong_way'):continue
                if slot!=lane and not (r['merge'] and max(s,ws)>r['length']-20 or r['split'] and min(s,ws)<16+max(v.spec.length,w.spec.length)/2):continue
                if ws>s:distance=min(distance,ws-s-(v.spec.length+w.spec.length)/2)
    return distance-(v.driver.gap if preferred else .6)


def target_gaps(sim,v,road,lane,s):
    front=rear=math.inf;leader=follower=None
    for w,ws in sim.road_index[road,lane]:
        if w is v:continue
        d=ws-s
        if d>=0 and d<front:front=d;leader=w
        if d<0 and -d<rear:rear=-d;follower=w
    safe=True
    if leader:
        front-=(v.spec.length+leader.spec.length)/2
        required=v.driver.gap+v.speed*v.driver.reaction+max(0.,v.speed*v.speed-leader.speed*leader.speed)/(2*v.spec.braking)+1
        safe &= front>=required
    if follower:
        rear-=(v.spec.length+follower.spec.length)/2
        required=follower.driver.gap+follower.speed*follower.driver.reaction+max(0.,follower.speed*follower.speed-v.speed*v.speed)/(2*follower.spec.braking)+1
        safe &= rear>=required
    return safe,front,rear,leader,follower


def protected(sim,p):
    net=sim.network;r=net.roads[p.road]
    buffer=PARAMETERS['lane_changes']['access_buffer']
    if r['merge'] or r['split']:return True
    for a in net.access.values():
        ap=net.paths[a.lane]
        if ap.road==p.road:
            pos=ap.start_s+a.s
            if p.start_s-buffer<pos<p.end_s+buffer:return True
    return False


def event(sim,v,kind,stage,**extra):
    sim.lane_counts[kind+'/'+stage]+=1
    item=dict(time=sim.elapsed,id=v.id,kind=kind,stage=stage,path=v.path_id,**extra)
    sim.lane_events.append(item)
    if kind in ('overtaking','return','wrong_way') and stage in ('attempt','completion','abort','collision'):
        sim.event_feed.append(item)


def reroute(sim,v,blocked=()):
    try:
        goal=sim.network.access[v.destination].lane
        suffix=()
        if v.spec.kind=='Bus':
            next_stop=next((i for i in range(v.index+1,len(v.route))
                            if v.route[i] in sim.network.bus_stops and i not in v.serviced),None)
            if next_stop is not None:goal=v.route[next_stop];suffix=v.route[next_stop+1:]
        tail=sim.network.plan(v.path_id,goal,v.behaviour_rng,blocked)
    except (ValueError,KeyError):return False
    v.route=v.route[:v.index]+tail+suffix
    return True


def decide_all(sim):
    net=sim.network;cfg=PARAMETERS['lane_changes']
    for v in sim.vehicles:
        if v.pass_episode and not v.crashed:
            leader=next((w for w in sim.vehicles if w.id==v.pass_episode['leader']),None)
            a=coordinate(sim,v);b=coordinate(sim,leader) if leader else None
            if a and b and a[0]==b[0] and a[2]-b[2]>(v.spec.length+leader.spec.length)/2+v.driver.gap:
                if v.pass_episode['phase']!='passed':
                    event(sim,v,'overtaking','completion',leader=leader.id);v.pass_episode['phase']='passed'
            elif v.pass_episode['phase']!='passed' and (not leader or (a and b and a[0]!=b[0])):
                event(sim,v,'overtaking','abort',reason='routes_diverged');v.pass_episode=None
    claimed={net.paths[v.change_grant or v.path_id].road for v in sim.vehicles if v.change_grant or net.paths[v.path_id].kind=='lane_change'}
    for v in sorted(sim.vehicles,key=lambda v:(-v.waiting,v.id)):
        p=net.paths[v.path_id]
        if v.change_grant and p.kind=='lane' and p.length-v.s<v.spec.length/2+3:
            cp=net.paths[v.change_grant];s=coordinate(sim,v)[2]
            safe,*_=target_gaps(sim,v,p.road,cp.lane,s)
            if not safe and not v.lane_change.get('risky',False):
                action,_=sim.rules.lane_change(True,False,False,True,False,False)
                if action=='hold':
                    event(sim,v,v.lane_change['kind'],'abort',reason='gap_changed_before_departure')
                    link=v.change_grant;v.used_changes.discard(v.lane_change['token'])
                    v.change_grant=None;v.lane_change=None;v.change_after=sim.elapsed+cfg['retry_seconds']
                    reroute(sim,v,blocked=(link,))
        if v.crashed or v.manoeuvre or v.change_grant or p.kind!='lane' or sim.elapsed<v.change_after:continue
        link=net.change_links.get((p.road,p.lane))
        if link is None or p.id!=net.paths[link].incoming:continue
        cp=net.paths[link]
        if p.length-v.s>max(12.,v.speed*2):continue
        needed=v.index+1<len(v.route) and v.route[v.index+1]==link
        loc=coordinate(sim,v);_,lane,s=loc
        _,_,_,leader,_=target_gaps(sim,v,p.road,lane,s)
        passing=(v.spec.kind!='Bus' and lane=='outer' and leader is not None and not leader.crashed and .2<leader.speed<v.desired_speed-1.5
                 and 0<coordinate(sim,leader)[2]-s<40 and v.speed>.5)
        next_turn=next((net.paths[pid].turn for pid in v.route[v.index+1:] if pid in net.connectors),None)
        returning=(lane=='inner' and not needed and next_turn!='left' and sim.elapsed>=v.change_after
                   and (v.pass_episode is None or v.pass_episode['phase']=='passed'))
        kind='planned' if needed else 'overtaking' if passing else 'return'
        if not (needed or passing or returning):continue
        token=(kind,p.road,v.index,leader.id if passing else None)
        if token in v.used_changes:continue
        v.used_changes.add(token);event(sim,v,kind,'opportunity')
        safe,front,rear,_,_=target_gaps(sim,v,p.road,cp.lane,s)
        eligible=not protected(sim,cp) and sim.elapsed>=v.change_after and p.road not in claimed
        risk=(v.driver.kind=='Drunk' and v.driver.subgroup=='higher_risk' and sim.mode=='accident'
              and opportunity(v,('lane_risk',*token),cfg['higher_risk_gap_acceptance']) and front*v.driver.gap_bias>1 and rear*v.driver.gap_bias>1)
        willing=needed or returning or opportunity(v,('lane_pass',*token),cfg['passing_willingness'] if v.driver.kind!='Newbie' else cfg['newbie_passing_willingness'])
        action,reason=sim.rules.lane_change(needed,passing and willing,returning,eligible,safe,risk)
        v.passing_reason=reason
        if action=='change':
            try:tail=v.route[v.index+2:] if needed else net.plan(cp.outgoing,net.access[v.destination].lane,v.behaviour_rng)
            except ValueError:
                event(sim,v,kind,'abort',reason='no_destination_route');continue
            v.route=v.route[:v.index+1]+(link,)+tail
            v.change_grant=link;v.lane_change=dict(kind=kind,link=link,source=p.id,leader=leader.id if passing else None,risky=risk,token=token)
            claimed.add(p.road);event(sim,v,kind,'selected',front=front,rear=rear,risky=risk)
        else:
            event(sim,v,kind,'rejected',reason=reason,front=front,rear=rear)
            if needed:
                if reroute(sim,v,blocked=(link,)):event(sim,v,kind,'reroute')
                else:
                    # At a lane-ending boundary no legal forward alternative
                    # exists. Reassess on a bounded 2 s schedule while stopped.
                    v.used_changes.discard(token);v.change_after=sim.elapsed+cfg['retry_seconds']


def transition(sim,v,previous):
    p=sim.network.paths[v.path_id]
    if p.kind=='lane_change':
        if v.lane_change is None:v.lane_change=dict(kind='planned',link=p.id)
        v.passing_state='change';event(sim,v,v.lane_change['kind'],'attempt')
        event(sim,v,'lane_change','attempt',purpose=v.lane_change['kind'])
        if v.lane_change['kind']=='overtaking':v.pass_episode=dict(leader=v.lane_change['leader'],phase='passing')
    elif sim.network.paths[previous].kind=='lane_change':
        kind=v.lane_change['kind'] if v.lane_change else 'planned'
        event(sim,v,kind,'lane_reached' if kind=='overtaking' else 'completion')
        event(sim,v,'lane_change','completion',purpose=kind);v.change_after=sim.elapsed+PARAMETERS['lane_changes']['cooldown_seconds']
        if kind=='return':v.pass_episode=None
        v.lane_change=None;v.change_grant=None;v.passing_state='follow'


def merge_limit(sim,v):
    loc=coordinate(sim,v)
    if loc is None:return math.inf
    road,lane,s=loc;r=sim.network.roads[road]
    if not r['merge']:return math.inf
    owner=sim.merge_owners.get(road)
    other=next((w for w in sim.vehicles if w.id==owner),None)
    if other:
        op=sim.network.paths[other.path_id]
        if getattr(op,'road',None)!=road and not (op.kind=='roundabout' and op.incoming in sim.network.segments[road,'inner']+sim.network.segments[road,'outer'] and other.s<other.spec.length+2):
            other=None
    if other is None:
        candidates=[w for w in sim.vehicles if (where:=coordinate(sim,w)) and where[0]==road]
        other=max(candidates,key=lambda w:(coordinate(sim,w)[2],-w.id),default=None)
        sim.merge_owners[road]=other.id if other else None
    if other is v:return math.inf
    return max(0.,r['length']-20-v.spec.length/2-.5-s)
