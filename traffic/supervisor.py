"""Temporary collision prevention, independent from Prolog proposals.

Spawn admission remains mandatory if the movement supervisor is replaced later.
"""
import math


def rectangles_overlap(a, sa, b, sb, margin=0.02):
    x,z,yaw=a
    xx,zz,yyaw=b
    if math.hypot(x-xx,z-zz) > (sa.length+sb.length)/2+sa.width+sb.width:
        return False
    axis=lambda angle:(math.sin(math.radians(angle)),math.cos(math.radians(angle)))
    fa,fb=axis(yaw),axis(yyaw)
    ra,rb=(fa[1],-fa[0]),(fb[1],-fb[0])
    dot=lambda p,q:p[0]*q[0]+p[1]*q[1]
    for n in (fa,fb,ra,rb):
        extent=(sa.length/2*abs(dot(fa,n))+sb.length/2*abs(dot(fb,n))+
                sa.width/2*abs(dot(ra,n))+sb.width/2*abs(dot(rb,n))+margin)
        if abs(dot((x-xx,z-zz),n)) >= extent:
            return False
    return True


class SafetySupervisor:
    def __init__(self):
        self.interventions=0
        self.violations=0
        self.events=set()
        self.details=[]
        self.context=None

    def record(self, v, reason):
        v.intervention=reason
        v.executed='wait'
        # One event per reason / approach / persistent behaviour episode.
        key=('intervention',v.id,v.index,reason)
        if key not in self.events:
            self.events.add(key)
            self.interventions+=1
            sim=self.context
            self.details.append(dict(time=sim.elapsed if sim else None,id=v.id,path=v.path_id,
                location=sim.pose(v) if sim else None,cause=reason,action=v.action,reason=v.reason))

    def violation(self,v):
        key=('violation',v.id,v.index)
        if key not in self.events:
            self.events.add(key)
            self.violations+=1

    def admission(self, v, *, conflicts, exit_clear, signal):
        if conflicts:
            return 'reserved_conflict'
        if not exit_clear:
            return 'blocked_exit'
        if signal == 'red' and v.reason != 'signal_violation':
            return 'stale_signal_response'
        return None

    def limit_travel(self,v,proposed,hard_gap):
        if proposed>max(0.,hard_gap)+1e-8:
            self.record(v,'physical_following_gap')
        return min(proposed,max(0.,hard_gap))

    def spawn_clear(self, net, v, others):
        return not self.spawn_reason(net,v,others)

    def spawn_reason(self, net, v, others):
        pose=net.paths[v.path_id].pose(v.s)
        for other in others:
            path=net.paths[other.path_id]
            if other.permit and net.paths[other.permit].outgoing == v.path_id:
                # A reservation protects the junction, not every metre of its
                # exit lane. Admit ahead only with stopping/reaction clearance.
                distance=-other.s
                for pid in other.route[other.index:other.index+3]:
                    if pid==v.path_id:
                        distance+=v.s
                        break
                    distance+=net.paths[pid].length
                else:distance=0.  # Unknown approach remains conservatively blocked.
                stopping=other.speed*other.driver.reaction+other.speed**2/(2*other.spec.braking)
                if 0<=distance<(v.spec.length+other.spec.length)/2+other.driver.gap+stopping+2:
                    return 'Incoming reservation'
            if other.path_id == v.path_id and other.s < v.s:
                stopping=other.speed*other.driver.reaction+other.speed**2/(2*other.spec.braking)
                if v.s-other.s < (v.spec.length+other.spec.length)/2+other.driver.gap+stopping+2:
                    return 'Approaching traffic'
            other_pose=other.contact_pose or net.paths[other.path_id].pose(other.s)
            if rectangles_overlap(pose,v.spec,other_pose,other.spec,margin=1.):
                return 'Wreck at entry' if other.crashed else 'Occupied entry'
            if other.path_id == v.path_id and abs(other.s-v.s) < (other.spec.length+v.spec.length)/2+max(v.driver.gap,other.driver.gap)+2:
                return 'Entry queue spacing'
        return ''

    def movement(self, sim, updates):
        # Compare swept endpoint/midpoint poses against simultaneous candidates.
        # If either must stop, iterate to prevent another car moving into it.
        starts={v.id:sim.pose(v) for v,_,_ in updates}
        held=set()
        for _ in range(len(updates)+1):
            new=set()
            for i,(a,sa,_) in enumerate(updates):
                for b,sb,_ in updates[i+1:]:
                    if math.dist(starts[a.id][:2],starts[b.id][:2]) > (a.spec.length+b.spec.length)/2+4:
                        continue
                    for t in (.5,1.):
                        pa=starts[a.id] if a.id in held else sim.future_pose(a,a.s+(sa-a.s)*t)
                        pb=starts[b.id] if b.id in held else sim.future_pose(b,b.s+(sb-b.s)*t)
                        if rectangles_overlap(pa,a.spec,pb,b.spec):
                            new.update((a.id,b.id))
                            break
            if new <= held:
                break
            held.update(new)
        result=[]
        for v,s,speed in updates:
            if v.id in held:
                if s > v.s+1e-8:
                    self.record(v,'physical_overlap_prevented')
                result.append((v,v.s,0.))
            else:
                result.append((v,s,speed))
        return result
