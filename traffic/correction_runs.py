"""Ordinary night time series; no actor injection, event quotas or rerolls."""
import argparse,json
from pathlib import Path
from collections import Counter
from .simulation import Simulation
from .four_lane import FourLaneNetwork
from .prolog import PrologRules
from .night import counts
from .verify_four_lane import finite_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--seeds',type=int,nargs='+',default=[42,43,44]);p.add_argument('--duration',type=float,default=300)
    p.add_argument('--population',type=int,default=40);p.add_argument('--normal',action='store_true');a=p.parse_args()
    net=FourLaneNetwork();rules=PrologRules();out=Path('artifacts/correction');out.mkdir(exist_ok=True,parents=True)
    for seed in a.seeds:
        s=Simulation(rules,network=net,seed=seed,scenario='Baseline' if a.normal else 'Evening/night',mode='accident');s.reset(target=a.population)
        samples=[]
        for tick in range(round(a.duration*60)):
            if tick%300==0:
                samples.append(dict(time=s.elapsed,**counts(s),total=len(s.vehicles),trips=s.completed,incidents=len(s.incidents.records)))
            s.step()
            assert len(s.vehicles)<=s.target
            if tick%3600==0:print(seed,round(s.elapsed),counts(s),dict(s.lane_counts),flush=True)
        samples.append(dict(time=s.elapsed,**counts(s),total=len(s.vehicles),trips=s.completed,incidents=len(s.incidents.records)))
        crossed=[e for e in s.junction_events if e['stage']=='crossed']
        summary=dict(seed=seed,population=a.population,duration=s.elapsed,first={k:next((e['time'] for e in s.lane_events if e['kind']==k and e['stage']=='attempt'),None) for k in ('overtaking','wrong_way')},
            red_entries=sum(e['unsafe'] and (e['signal']=='red' or e['reason']=='signal_violation') for e in crossed),
            committed_crossings_under_red=sum(e['signal']=='red' and not e['unsafe'] for e in crossed),
            failed_yields=sum(e['reason']=='unsafe_gap_accepted' for e in crossed),
            incidents_by_location=dict(Counter(r['location_type'] for r in s.incidents.records)),counts=dict(s.lane_counts),mix=s.behaviour_audit.values())
        data=dict(summary=summary,samples=samples,junction_events=s.junction_events,events=s.lane_events,incidents=s.incidents.records,removals=s.removals,admitted=s.behaviour_audit.admitted)
        (out/f'{"normal" if a.normal else "night"}-{a.population}-{seed}.json').write_text(json.dumps(finite_json(data),indent=2,allow_nan=False))
        print('SAVED',json.dumps(summary),flush=True)

if __name__=='__main__':main()
