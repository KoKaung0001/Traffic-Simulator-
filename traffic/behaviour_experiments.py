"""Multi-seed driver validation, preserving each run's execution/contact evidence."""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from .experiments import run,DEFINITIONS
from .demand import SCENARIOS
from .profiles import PARAMETERS
from .prolog import PrologRules


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seeds',type=int,nargs='+',default=[42,43,44])
    p.add_argument('--duration',type=float,default=300)
    p.add_argument('--green',type=float,default=30)
    p.add_argument('--population',type=int,default=40)
    p.add_argument('--mode',choices=('accident','supervised'),default='accident')
    p.add_argument('--output',type=Path,default=Path('artifacts/driver-revision'))
    a=p.parse_args()
    if a.duration<=0 or not 5<=a.green<=120 or not 0<=a.population<=100:p.error('Invalid duration, green or population')
    a.output.mkdir(parents=True,exist_ok=True);rows=[];rules=PrologRules()
    for scenario in SCENARIOS:
        for seed in a.seeds:
            row,sim=run(rules,scenario,seed,a.duration,a.green,a.mode,a.population)
            rows.append(row)
            payload=dict(configuration=row,parameters=PARAMETERS,definitions=DEFINITIONS,
                admitted=sim.behaviour_audit.admitted,behaviour=sim.behaviour_audit.values(),
                events=list(sim.behaviour_audit.events.values()),incidents=sim.incidents.records,
                interventions=sim.supervisor.details)
            slug=scenario.lower().replace(' ','-').replace('/','-')
            (a.output/f'{slug}-{seed}.json').write_text(json.dumps(payload,indent=2))
            with (a.output/'results.csv').open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(row));writer.writeheader();writer.writerows(rows)
            print(json.dumps(row),flush=True)
    summary={scenario:{metric:dict(mean=mean(values),minimum=min(values),maximum=max(values))
        for metric in ('accidents','involved','completed','distance_km','waiting_fraction')
        if (values:=[r[metric] for r in rows if r['scenario']==scenario])} for scenario in SCENARIOS}
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2))


if __name__=='__main__':main()
