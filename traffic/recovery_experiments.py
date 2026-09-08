"""Ordinary seeded night frequencies, admissions and headless execution cost."""
import json
import time
from pathlib import Path
from .experiments import run
from .prolog import PrologRules


def main():
    root=Path('artifacts/recovery');root.mkdir(exist_ok=True)
    rules=PrologRules();rows=[]
    configs=[('Evening/night',seed,40,180) for seed in (42,43,44)]
    configs+=[('Baseline',42,100,120),('Evening/night',42,100,120)]
    for scenario,seed,population,duration in configs:
        start=time.perf_counter()
        row,sim=run(rules,scenario,seed,duration,30,'accident',population)
        row.update(wall_seconds=time.perf_counter()-start,pending=sim.pending,
                   queued=len(sim.queued),spawn_status=sim.spawn_status)
        name=f'{scenario.lower().replace("/","-").replace(" ","-")}-{seed}-{population}'
        (root/f'{name}.json').write_text(json.dumps(dict(result=row,removals=sim.removals,
            incidents=sim.incidents.records,events=list(sim.behaviour_audit.events.values()),
            admitted=sim.behaviour_audit.admitted),indent=2))
        rows.append(row);(root/'results.json').write_text(json.dumps(rows,indent=2))
        print(json.dumps(row),flush=True)


if __name__=='__main__':main()
