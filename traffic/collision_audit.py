"""Bounded physical pre-contact histories; observation only, no RNG draws."""
import math
from .behaviour import finite


def footprint(pose,spec):
    x,z,yaw=pose;a=math.radians(yaw);f=(math.sin(a),math.cos(a));r=(f[1],-f[0])
    return [[x+front*f[0]+side*r[0],z+front*f[1]+side*r[1]]
            for front,side in ((spec.length/2,spec.width/2),(spec.length/2,-spec.width/2),
                               (-spec.length/2,-spec.width/2),(-spec.length/2,spec.width/2))]


def sample(sim):
    from .lane_changes import coordinate,target_gaps
    for v in sim.vehicles:
        if v.crashed:continue
        p=sim.network.paths[v.path_id];loc=coordinate(sim,v)
        leader=None
        if loc:
            road,lane,s=loc;leader=target_gaps(sim,v,road,lane,s)[3]
        prior=v.trace[-1] if v.trace else None
        acceleration=(v.speed-prior['speed'])/max(.001,sim.elapsed-prior['time']) if prior else 0
        v.trace.append(dict(time=sim.elapsed,path=v.path_id,lane=getattr(p,'lane',None),road=getattr(p,'road',None),
            speed=v.speed,acceleration=acceleration,braking_limit=v.spec.braking*v.driver.braking,
            actual_gap=finite(v.actual_gap),perceived_gap=finite(v.perceived_gap),closing=finite(v.actual_closing),
            perceived_closing=finite(v.perceived_closing),manoeuvre=v.passing_state,
            proposal=v.action,reason=v.reason,control=v.control,control_reason=v.control_reason,executed=v.executed,
            leader=None if leader is None else dict(id=leader.id,path=leader.path_id,speed=leader.speed,
                action=leader.action,control=leader.control,executed=leader.executed),
            dimensions=[v.spec.length,v.spec.width],pose=sim.pose(v),footprint=footprint(sim.pose(v),v.spec)))
