"""Labelled deterministic conflict fixtures; never ordinary-run evidence."""
import json,random
from pathlib import Path
from .simulation import Simulation,Vehicle
from .profiles import Driver
from .prolog import PrologRules
from .four_lane import FourLaneNetwork
from .verify_four_lane import finite_json

def conflict(net,rules,kind):
    # Explore explicit arrival phases, keeping both participants present and
    # moving. Prolog still decides the red/failure-to-yield entry.
    pairs=[]
    for a in net.connectors.values():
        if a.kind!=kind or (kind=='signal' and a.turn!='straight'):continue
        if getattr(net.junctions[a.junction],'bend',False):continue
        for b in net.connectors.values():
            if b.junction!=a.junction or a.approach==b.approach:continue
            if kind=='signal' and (b.turn!='straight' or a.approach in ('north','south')):continue
            if net.conflict(a.id,DriverSpec,b.id,DriverSpec):pairs.append((a,b))
    for cp,other in pairs[:32]:
        for phase in (0,4,8,12,16):
            s=Simulation(rules,network=net,mode='accident');s.vehicles=[];s.queued.clear();s.target=0
            lane=net.paths[cp.incoming]
            a=Vehicle(1,(lane.id,cp.id,cp.outgoing),lane.length-3,0,speed=8,
                      driver=Driver(kind='Drunk',signal_risk=1,gap_risk=1,gap_bias=2),behaviour_rng=random.Random(1))
            b=Vehicle(2,(other.id,other.outgoing),min(phase,other.length-1),1,speed=6,permit=other.id,behaviour_rng=random.Random(2))
            s.vehicles=[a,b]
            from .supervisor import rectangles_overlap
            if rectangles_overlap(s.pose(a),a.spec,s.pose(b),b.spec):continue
            initial=[dict(id=v.id,route=v.route,s=v.s,speed=v.speed) for v in s.vehicles]
            for _ in range(360):
                s.step()
                if s.incidents.records:break
            if s.incidents.records and any(e.get('unsafe') for e in s.junction_events):
                return dict(label='constructed deterministic conflict, not ordinary traffic',kind=kind,initial=initial,
                            junction_events=s.junction_events,incidents=s.incidents.records,behaviour=s.behaviour_audit.values())
    raise AssertionError('No executable unsafe contact fixture for '+kind)

from .profiles import VehicleSpec
DriverSpec=VehicleSpec()

def main():
    net=FourLaneNetwork();rules=PrologRules()
    for kind in ('signal','roundabout'):
        result=conflict(net,rules,kind)
        Path(f'artifacts/correction/conflict-{kind}.json').write_text(json.dumps(finite_json(result),indent=2))
        print('CONTACT VERIFIED',kind,result['initial'],flush=True)

if __name__=='__main__':main()
