"""Ordinary-run acceptance checks for 100 active vehicles and manoeuvre funnels."""
import argparse
import json
import math
import time
from pathlib import Path
from .experiments import run
from .prolog import PrologRules
from .profiles import PARAMETERS


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--scenario',default='Evening/night',choices=('Baseline','Evening/night'))
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--population',type=int,default=100)
    p.add_argument('--duration',type=float,default=360)
    p.add_argument('--output',type=Path,default=Path('artifacts/capacity-final'))
    a=p.parse_args();start=time.perf_counter()
    if not 0<=a.population<=100 or not math.isfinite(a.duration) or a.duration<=0:
        p.error('Require population 0..100 and a finite positive duration.')
    def progress(sim):
        print(json.dumps(dict(time=sim.elapsed,active=len(sim.vehicles),trips=sim.completed,
            first_100=sim.flow_audit.first_100,manoeuvres=dict(sim.behaviour_audit.passing))),flush=True)
    row,sim=run(PrologRules(),a.scenario,a.seed,a.duration,30,'accident',a.population,progress=progress)
    audit=sim.flow_audit.values()
    assert len(sim.behaviour_audit.admitted)-len(sim.removals)==len(sim.vehicles)
    assert not any(x['stale_reservations'] for x in audit['samples'])
    row.update(block_spacing=sim.network.spacing,peripheral=sim.network.peripheral,first_100=audit['first_100'],maximum_active=audit['max_active'],
               wall_seconds=time.perf_counter()-start)
    output=a.output;output.mkdir(parents=True,exist_ok=True)
    slug=a.scenario.lower().replace('/','-')
    payload=dict(result=row,parameters=PARAMETERS,audit=audit,incidents=sim.incidents.records,
        admitted=sim.behaviour_audit.admitted,removals=sim.removals,
        storage=dict(lane_metres=sum(p.length for p in sim.network.lanes.values()),
            nominal_sedan_slots=sum(math.floor(max(0,p.length-2)/8.9) for p in sim.network.lanes.values())))
    (output/f'{slug}-{a.seed}-{a.population}.json').write_text(json.dumps(payload,indent=2))
    print(json.dumps(row),flush=True);print(json.dumps(audit['funnel']),flush=True)
    if a.scenario=='Baseline' and a.population==100:
        assert audit['first_100'] is not None,'Ordinary Normal run did not reach 100'
        assert not sim.incidents.records,'Normal baseline produced contact'


if __name__=='__main__':main()
