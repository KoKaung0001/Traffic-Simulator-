"""Seeded headless integration audit; no rendering or fallback rules."""
import argparse
import json
import math
from .simulation import Simulation
from .prolog import PrologRules
from .supervisor import rectangles_overlap
from .demand import SCENARIOS


def overlap(a, b):
    """Separating-axis test on oriented sedan rectangles (small tolerance)."""
    x, z, yaw = a
    xx, zz, yyaw = b
    if math.hypot(x-xx, z-zz) > 5:
        return False
    axis = lambda angle: (math.sin(math.radians(angle)), math.cos(math.radians(angle)))
    fa, fb = axis(yaw), axis(yyaw)
    ra, rb = (fa[1], -fa[0]), (fb[1], -fb[0])
    dot = lambda p, q: p[0]*q[0]+p[1]*q[1]
    for n in (fa, fb, ra, rb):
        extent = 2.19*(abs(dot(fa,n))+abs(dot(fb,n))) + .89*(abs(dot(ra,n))+abs(dot(rb,n)))
        if abs(dot((x-xx,z-zz), n)) >= extent:
            return False
    return True


def audit(seconds=900, seed=42, population=40, scenario='Baseline', drain=False):
    sim = Simulation(PrologRules(), seed=seed,scenario=scenario)
    sim.set_target(population)
    last_completion = 0.
    previous_completed = 0
    concurrent = 0
    minimum_active = 1000
    last_motion = {}
    max_stationary = 0.
    long_waits=set()
    wait_seconds=0.
    vehicle_seconds=0.
    for tick in range(round(seconds*60)):
        sim.step()
        poses = []
        circulating = {}
        for v in sim.vehicles:
            vehicle_seconds+=1/60
            if v.speed<.05 and v.dwell<=0:
                wait_seconds+=1/60
            if v.id not in last_motion or v.speed > .05:
                last_motion[v.id] = sim.elapsed
            stationary = sim.elapsed-last_motion[v.id]
            max_stationary = max(max_stationary,stationary)
            if stationary>=180:
                long_waits.add(v.id)
            assert stationary < 600, ('Stationary vehicle for 600 seconds', v)
            p = sim.network.paths[v.path_id]
            assert 0 <= v.s <= p.length and math.isfinite(v.s), (tick, v)
            pose = sim.pose(v)
            assert all(math.isfinite(c) and abs(c) < 1000 for c in pose), (tick, pose)
            for other, other_pose in poses:
                assert not rectangles_overlap(pose,v.spec,other_pose,other.spec,margin=-.01), (tick, v, other, pose, other_pose)
            poses.append((v, pose))
            if p.kind == 'roundabout':
                circulating[p.junction] = circulating.get(p.junction, 0)+1
        concurrent = max(concurrent, max(circulating.values(), default=0))
        minimum_active = min(minimum_active, len(sim.vehicles))
        if sim.completed != previous_completed:
            last_completion = sim.elapsed
            previous_completed = sim.completed
        assert sim.elapsed-last_completion < 180, ('No completed trip for 180 seconds', sim.elapsed,
                                                   [(v.id, v.path_id, v.s, v.reason) for v in sim.vehicles])
    result={'scenario':scenario,'seed': seed, 'seconds': seconds, 'target': population, 'completed': sim.completed,
            'active': len(sim.vehicles), 'minimum_active': minimum_active,
            'max_simultaneous_roundabout_vehicles': concurrent, 'overlaps': 0, 'invalid_positions': 0,
            'max_stationary_seconds': round(max_stationary,2),
            'waiting_vehicle_seconds':round(wait_seconds,1),'waiting_fraction':round(wait_seconds/vehicle_seconds,3),
            'safety_interventions':sim.supervisor.interventions,'attempted_signal_violations':sim.supervisor.violations,
            'vehicles_waiting_over_180s':len(long_waits),
            'long_wait_vehicles_still_active':sum(v.id in long_waits for v in sim.vehicles),
            'longest_allowed_completion_gap_seconds': 180}
    if drain:
        sim.set_target(0)
        start=sim.elapsed
        for _ in range(60*900):
            if not sim.vehicles:
                break
            sim.step()
        assert not sim.vehicles, ('Traffic failed to drain',[(v.id,v.path_id,v.reason) for v in sim.vehicles])
        result['drain_seconds']=round(sim.elapsed-start,2)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, default=900)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--population', type=int, default=40)
    parser.add_argument('--scenario',choices=SCENARIOS,default='Baseline')
    parser.add_argument('--drain',action='store_true',help='After the audit, set target zero and verify all remaining trips finish.')
    args = parser.parse_args()
    print(json.dumps(audit(args.seconds, args.seed, args.population,args.scenario,args.drain), indent=2))
