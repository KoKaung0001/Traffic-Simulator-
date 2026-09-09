"""Illustrative, configurable assumptions; not measured traffic statistics."""
from dataclasses import dataclass
from pathlib import Path
import json

PARAMETERS = json.loads(Path(__file__).with_name('parameters.json').read_text())


@dataclass(frozen=True)
class Driver:
    reckless: bool = False
    kind: str = 'Normal'
    speed_factor: float = 1.0
    reaction: float = 0.0
    gap: float = 2.5
    acceleration: float = 1.0
    entry_gap: float = 0.0
    hesitation: float = 0.0
    signal_risk: float = 0.0
    gap_risk: float = 0.0
    subgroup: str = 'standard'
    braking: float = 1.0
    gap_bias: float = 1.0
    closing_bias: float = 1.0
    overshoot: float = 0.0
    overtake: float = 0.0
    wrong_way: float = 0.0


@dataclass(frozen=True)
class VehicleSpec:
    kind: str = 'Sedan'
    length: float = 4.4
    width: float = 1.8
    cruise: float = 10.0
    acceleration: float = 2.4
    braking: float = 4.5
    turn_radius: float = 2.5


def sample_driver(kind, rng):
    p = PARAMETERS['drivers'][kind]
    subgroup='standard'
    if kind in PARAMETERS['personalities']:
        groups=PARAMETERS['personalities'][kind]
        subgroup=rng.choices(list(groups),weights=[v['weight'] for v in groups.values()])[0]
        p=groups[subgroup]
    traits=dict(kind=kind,subgroup=subgroup,
        **{name:rng.uniform(*p[key]) for name,key in
           (('speed_factor','speed'),('reaction','reaction'),('gap','gap'),
            ('acceleration','acceleration'),('entry_gap','entry_gap'))},
        **{k:p[k] for k in ('hesitation','signal_risk','gap_risk')})
    if subgroup!='standard':
        traits.update({k:rng.uniform(*p[k]) for k in ('braking','gap_bias','closing_bias')})
        traits.update({k:p[k] for k in ('overshoot','overtake')})
        traits['wrong_way']=p.get('wrong_way',0.)
    return Driver(**traits)


def vehicle_spec(kind):
    return VehicleSpec(kind=kind, **PARAMETERS['vehicles'][kind])
