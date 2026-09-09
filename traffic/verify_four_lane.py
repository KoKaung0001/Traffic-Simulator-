"""Ordinary seeded verification, with independent geometry checks and saved evidence."""
import argparse,json,math
from pathlib import Path
from .experiments import run
from .prolog import PrologRules
from .profiles import PARAMETERS


def finite_json(value):
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,dict):return {k:finite_json(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [finite_json(v) for v in value]
    return value


def main():
    p=argparse.ArgumentParser();p.add_argument('--duration',type=float,default=240)
    p.add_argument('--seeds',type=int,nargs='+',default=[42,43,44]);p.add_argument('--population',type=int,default=100)
    p.add_argument('--normal',action='store_true');a=p.parse_args()
    if not math.isfinite(a.duration) or a.duration<=0 or not 0<=a.population<=100:p.error('Require finite positive duration and population 0..100')
    rules=PrologRules();out=Path('artifacts/four-lane');out.mkdir(parents=True,exist_ok=True)
    for seed in a.seeds:
        scenario='Baseline' if a.normal else 'Evening/night'
        def progress(s):print(json.dumps(dict(seed=seed,time=s.elapsed,active=len(s.vehicles),trips=s.completed,incidents=len(s.incidents.records),events=dict(s.lane_counts))),flush=True)
        row,s=run(rules,scenario,seed,a.duration,30,'accident',a.population,progress=progress)
        first={kind:next((e['time'] for e in s.lane_events if e['kind']==kind and e['stage']=='attempt'),None)
               for kind in ('lane_change','overtaking','wrong_way')}
        assert len(s.behaviour_audit.admitted)-len(s.removals)==len(s.vehicles)
        assert not any(row['stale_reservations'] for row in s.flow_audit.samples)
        if a.normal:
            assert not s.incidents.records,'Normal run produced contact'
            if a.population==100:assert s.flow_audit.first_100 is not None,'Normal run did not reach 100'
        payload=dict(configuration=row,parameters=PARAMETERS,behaviour=s.behaviour_audit.values(),flow=s.flow_audit.values(),
            counts=dict(s.lane_counts),first_attempt=first,events=s.lane_events,incidents=s.incidents.records,
            admitted=s.behaviour_audit.admitted,usage=dict(s.metrics.usage),removals=s.removals)
        name=f'{"normal" if a.normal else "night"}-{a.population}-seed{seed}.json'
        (out/name).write_text(json.dumps(finite_json(payload),indent=2,allow_nan=False));print('SAVED '+name,flush=True)


if __name__=='__main__':main()
