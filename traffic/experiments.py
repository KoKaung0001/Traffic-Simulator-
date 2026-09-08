"""Headless paired timing experiments with CSV, incident and configuration exports."""
import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean,stdev
from .simulation import Simulation, STEP
from .prolog import PrologRules
from .demand import SCENARIOS
from .profiles import PARAMETERS
from .collisions import pairs
from .supervisor import rectangles_overlap
from .overtaking import valid

DEFINITIONS={
    'distance_km':'Sum of actual vehicle centre travel / 1000; wreck travel stops at contact.',
    'waiting_vehicle_s':'Speed < 0.05 m/s, including red lights and wrecks, excluding bus dwell.',
    'bus_dwell_vehicle_s':'Scheduled bus dwell only; separate from waiting.',
    'waiting_fraction':'Waiting vehicle-seconds / all active vehicle-seconds (including dwell/wrecks).',
    'mean_speed_mps':'Arithmetic mean across all active vehicles at run end, including stopped/wrecked.',
    'accidents_per_1000_vehicle_km':'Incident origins * 1000 / distance_km; null/blank at zero distance.',
    'usage':'Directed lane entries once per vehicle route occurrence, including initial partial traversal; connectors excluded.',
    'incident_cells':'16 m x 16 m world cells; one origin per incident, cumulative since reset.',
    'incident_time':'Seconds elapsed since reset, quantized to start of the 1/60 s contact step.',
    'counts':'Accidents = distinct origins; active incidents = not cleared; involved = unique vehicle IDs since reset.',
    'randomness':'Legacy seed-based initial state, separate subsequent driver-parameter stream seed+7919; per-vehicle behaviour seed*1000003+ID. Demand/routing retain their own seed stream.',
}


def run(rules,scenario,seed,duration,green,mode,population=40,clearance=45,progress=None):
    sim=Simulation(rules,seed=seed,scenario=scenario,mode=mode,clearance=clearance)
    sim.reset(target=population)
    sim.set_global(green)
    # Comparisons begin with the requested green, rather than a common 30 s first phase.
    for signal in sim.signals.values(): signal.active_green=green
    for _ in range(round(duration/STEP)):
        sim.step()
        if progress and sim.ticks%1800==0:progress(sim)
        for v in sim.vehicles:
            if not valid(sim,v):
                raise AssertionError(f'Invalid geometry: {v.id}')
        # Contact is valid. Significant interpenetration is independently invalid.
        positions=[(v,v.s,0.) for v in sim.vehicles]
        for i,j in pairs(sim,positions):
            va,vb=sim.vehicles[i],sim.vehicles[j]
            if rectangles_overlap(sim.pose(va),va.spec,sim.pose(vb),vb.spec,margin=-.001):
                raise AssertionError(f'Interpenetration: {va.id}, {vb.id}, t={sim.elapsed}')
    row=dict(scenario=scenario,seed=seed,duration_s=sim.elapsed,start_clock_s=sim.start_clock,
             green_s=green,mode=mode,population=population,clearance_s=clearance,
             **sim.metrics.values(sim),interventions=sim.supervisor.interventions,
             signal_attempts=sim.supervisor.violations)
    row.update(invalid_positions=0,interpenetrations=0)
    row.update({k:json.dumps(v,sort_keys=True) for k,v in sim.behaviour_audit.values().items()})
    return row,sim


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scenario',choices=SCENARIOS,default='Evening/night')
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--duration',type=float,default=600)
    p.add_argument('--green',type=float,default=30)
    p.add_argument('--mode',choices=('supervised','accident'),default='accident')
    p.add_argument('--population',type=int,default=40)
    p.add_argument('--clearance',type=float,default=45)
    p.add_argument('--compare',action='store_true',help='15/30/60 s; seeds seed, seed+1, seed+2')
    p.add_argument('--output',type=Path,default=Path('artifacts/experiments'))
    a=p.parse_args()
    if a.duration<=0 or not 5<=a.green<=120 or not 0<=a.population<=100 or a.clearance<=0:
        p.error('Require positive duration/clearance, green 5..120, population 0..100.')
    a.output.mkdir(parents=True,exist_ok=True)
    rules=PrologRules(); rows=[]
    for green in ((15,30,60) if a.compare else (a.green,)):
        for seed in (range(a.seed,a.seed+3) if a.compare else (a.seed,)):
            row,sim=run(rules,a.scenario,seed,a.duration,green,a.mode,a.population,a.clearance)
            rows.append(row)
            label=f'{a.mode}-g{green:g}-seed{seed}'
            payload=dict(configuration=row,parameters=PARAMETERS,definitions=DEFINITIONS,
                fixed_step_s=STEP,local_overrides={},incidents=sim.incidents.records,
                road_usage=dict(sim.metrics.usage),incident_cells={str(k):v for k,v in sim.incidents.cells.items()},
                safety_interventions=sim.supervisor.details)
            payload.update(behaviour=sim.behaviour_audit.values(),behaviour_events=list(sim.behaviour_audit.events.values()),
                admitted_vehicles=sim.behaviour_audit.admitted)
            (a.output/f'{label}.json').write_text(json.dumps(payload,indent=2))
            with (a.output/f'{label}.csv').open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(row));writer.writeheader();writer.writerow(row)
            with (a.output/'results.csv').open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(row)); writer.writeheader(); writer.writerows(rows)
            print(json.dumps(row),flush=True)
    if a.compare:
        summary={str(g):{metric:dict(mean=mean(values),sd=stdev(values),minimum=min(values),maximum=max(values))
            for metric in ('accidents','completed','distance_km','waiting_fraction')
            if (values:=[r[metric] for r in rows if r['green_s']==g])} for g in (15,30,60)}
        (a.output/'comparison.json').write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
