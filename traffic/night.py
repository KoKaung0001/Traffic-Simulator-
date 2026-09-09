"""Illustrative night quota and arcade preset; never changes an admitted driver."""
from collections import Counter
from dataclasses import replace
from .profiles import PARAMETERS
from .demand import TripRequest,choose

def enabled(sim):
    return getattr(sim.network,'lane_count',2)==4 and sim.scenario=='Evening/night'

def config(sim):
    return PARAMETERS['reckless_night'] if enabled(sim) else {}

def counts(sim):
    target=min(sim.target,PARAMETERS['reckless_night']['drunk_target']) if enabled(sim) and (sim.clock>=18*3600 or sim.clock<6*3600) else 0
    active=sum(v.driver.kind=='Drunk' and not v.crashed for v in sim.vehicles)
    wrecks=sum(v.driver.kind=='Drunk' and v.crashed for v in sim.vehicles)
    pending=sum(v.driver.kind=='Drunk' for v in sim.queued)
    blocker=('Total occupancy at target; awaiting a trip or wreck clearance' if active<target and not sim.pending else
             'Queued entry blocked' if active<target and pending else '')
    return dict(active=active,wrecks=wrecks,pending=pending,target=target,blocker=blocker)

def ticket(sim,ticket):
    c=counts(sim)
    if not c['target']:return ticket
    if c['active']+c['pending']>=c['target']:
        # Replacement profiles remain varied after the quota is supplied.
        return replace(ticket,profile=choose(sim.rng,{'Normal':.8,'Newbie':.2}))
    origins={'Pub':3,'Belt pub':3,'Belt shops':2,'Belt offices':1,'West gate':1,'East gate':1,'North gate':1,'South gate':1}
    queued=Counter(v.origin for v in sim.queued)
    origin=choose(sim.rng,{k:w/(1+queued[k]) for k,w in origins.items() if k in sim.network.access})
    destination=ticket.destination if ticket.destination!=origin else 'Apartments'
    return TripRequest(origin,destination,'Sedan','Drunk')

def driver(sim,driver,rng):
    cfg=config(sim)
    if not cfg or driver.kind!='Drunk' or not cfg['enabled']:return driver
    high=rng.random()<cfg['high_risk_fraction']
    if not high:return replace(driver,subgroup='less_aggressive')
    return replace(driver,subgroup='higher_risk',reckless=True,
        speed_factor=rng.uniform(1.35,1.7),reaction=rng.uniform(.55,1.15),
        acceleration=rng.uniform(1.25,1.6),gap=rng.uniform(.65,1.15),
        braking=rng.uniform(.65,.9),gap_bias=rng.uniform(1.3,1.9),closing_bias=rng.uniform(.45,.75),
        signal_risk=cfg['signal_risk'],gap_risk=cfg['gap_risk'],overtake=.95,
        wrong_way=cfg['wrong_way_willingness'],hesitation=.01)
