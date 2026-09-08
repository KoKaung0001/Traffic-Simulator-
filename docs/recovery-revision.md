# Crossing City - Python + Prolog Traffic Lab

This revision audits vehicle removal and admission, adds explicit wrong-way episodes, and makes lighting follow simulated time. The existing collision geometry, contextual trips, bus fleet, metrics and heatmaps remain.

## Launch and controls

Run from the project directory using the existing environment:

```powershell
& '..\.venv\Scripts\python.exe' main.py
```

The GUI defaults to **accident mode**, shown in the header and Run setup. Baseline starts at noon, Morning commute at 07:30, and Evening/night at 21:00. Select Evening/night for the dark scene and mixed drivers.

| Control | Effect |
| --- | --- |
| Run setup | Scenario, mode, target 0-100, profile counts and admission blockers |
| Target population | Desired active population; safe admissions retry automatically |
| Pause / Space | Freeze movement, clearance, demand and clock-based lighting |
| Reset / R | Fresh run, target 40, default 30 s green, cleared history |
| Scenario or mode change | Fresh run retaining target; updates existing lights |
| Click vehicle | Traits, actual/perceived gap, reaction, episode, proposal/execution, manoeuvre and removal reason |
| Click junction | Phase and local green override; Use global removes it |
| Global green slider | 5-120 s, applied at next green boundary |
| None / Road usage / Accidents | Cumulative overlays since reset |
| WASD / arrows / wheel; Home / H | Pan, zoom and fitted overview |

Optional flags: `--mode supervised` for conservative diagnostic movement; `--clearance 60` to change the default 45 simulated seconds after last contact. No dependencies were added. Use the existing Python 3.14.7, Ursina 8.3.0, Panda3D 1.10.16, janus-swi 1.5.3 and SWI-Prolog 10.0.2 environment.

## Removal and population findings

The original seed-42 audit, initial 30 raised to target 100, reproduced roughly 30-41 active vehicles over 120 s. Demand was generated and admitted: Baseline admitted 66 vehicles in total and ended with 38 active; night admitted 59 and ended with 33 active. Requests concentrated at seven constrained curb entrances. Safe spacing, approaching traffic and incoming reservations limited throughput. There was no hidden 40-car cap; the three-bus fleet cap is separate.

No unrelated removal by an expired crash location was reproduced. All original removals were destination arrivals (28 baseline, 19 night) or incident members (seven night). A separate confirmed bug let a wreck at a route endpoint enter trip-completion handling; that path now excludes wrecks. The inspector also described every absent vehicle as a completed trip. It now displays the audited reason, time and destination.

Cleanup iterates active incident IDs and removes only still-crashed vehicles whose IDs are explicit members of the due incident. It is idempotent. New pile-up arrivals receive membership and extend the active timer. Cleared records leave active processing; finalized history and heatmaps remain. Stale references cannot revive finalized incidents. Reservations and collision hash buckets derive from the active registry, so cleared members leave no obstruction there.

All registry exits use one audited removal function, recording ID, time, reason, incident, path, position and destination once. Only trip completion increments completed trips. Lower targets drain through trip completion, without arbitrary on-road deletion. Reset explicitly starts a new run, including fresh queues, IDs, incident state and logs.

**Active population = live on-road vehicles + uncleared wrecks.** Pending demand is target minus active, clamped at zero. Queued requests are part of pending demand, not additional vehicles. Stable tickets retain traits; retries rotate fairly, and reductions trim only unentered requests. Run setup shows entry occupancy, wreck, approaching-traffic and reservation blockers. Resume a paused run, wait for space/clearance, or lower the target when congested. Admission recovers automatically. No spacing checks were weakened and no extra vehicles are forced onto full roads.

See [the detailed audit](docs/recovery-audit.md) and `artifacts/recovery-before.json` for evidence. The regression reaches 100 using seven long, capacity-controlled entry corridors; that does not establish capacity 100 for ordinary city demand.

## Driver behaviours and wrong-way movement

Stable personalities remain seeded samples: drunk drivers are 75% higher risk / 25% less aggressive; newbies are 70% cautious / 30% unsteady. These and all numerical behaviours are **illustrative project assumptions, not real-world statistics**. Existing speed, reaction, braking, gap and estimation ranges are recorded in [the preceding driver revision](docs/driver-revision.md) and configured in `traffic/parameters.json`.

Delayed observations still feed Prolog, while actual geometry independently detects contact. Mistakes include late braking, unsafe gaps, pedal overshoot, speed changes and delayed starts. Episodes last 4-7 s; signal compliance is sampled once per approach, not rerolled while waiting. Vehicle acceleration/braking limits remain; contact can stop a vehicle abruptly.

| Opposing-lane setting | Default |
| --- | --- |
| Eligible drivers | Higher-risk drunk sedans, accident mode |
| Wrong-way willingness | 0.18 per eligible road occurrence; less aggressive 0 |
| Assessment | At least 0.4 s, using delayed/biased oncoming estimates |
| Minimum remaining straight | 28 m; movement begins beyond 3 m start buffer |
| Lane shift | 9 m sampled cubic, 5 m lateral displacement |
| Sustained episode | Sampled 2-4 s; shortened when return buffer approaches |
| Wrong-way desired manoeuvre speed | 2.5 m/s, reached using physical braking |
| End buffer | 4 m; explicit return path required |
| Existing overtaking | Willingness 0.50; moving leader 0.5-2.5 m/s; speed advantage at least 4 m/s |

Configure `wrong_way` and personality weights in `traffic/parameters.json`. Overtaking retains `follow -> assess -> move_out -> pass -> return`, with feasible aborts. Wrong-way states are `follow -> assess -> move_out -> wrong_way -> return`. Prolog `wrong_way/8` selects transitions/braking; Python supplies perception, seeded opportunities and continuous paths. The inspector exposes `centre_line_crossing`, `sustained_wrong_way`, `wrong_way_braking` and `wrong_way_return`.

Opposing traffic stays present. Normal drivers observe a wrong-way vehicle, wait their reaction delay and execute Prolog braking within physical limits. This hazard does not enter their instantaneous following-gap clamp. Ordinary following/reservation safeguards remain. A late response can still result in contact. If return is infeasible, the wrong-way vehicle brakes in the opposing lane and remains exposed; it never teleports or disappears to resolve a conflict.

Both manoeuvres exclude junctions, roundabouts, portal roads and both directions of roads containing access/spawn points or bus stops. The map has no mid-block pedestrian crossings. Validity checks permit deliberate opposing occupancy but require the full rectangle to stay on the road. A targeted existing-city scenario with seed 3 and normally sampled driver ID 100 selects and completes a sustained wrong-way episode; neither its probability nor its Prolog decision is forced.

## Clock-driven night lighting

Previously, the evening clock did not affect rendering: the daytime sun stayed on and block lamps were decorative. Lighting now uses `sim.clock`. The illustrative day has sunrise 06:00 and sunset 18:00, with approximately 45-minute smooth transitions inside daylight. At 21:00 the sun points below the horizon with exactly zero intensity, a dark background and reduced ambient fill. Pause freezes the source clock. Reset/scenario changes update existing lights without duplication.

There are 74 street/block lamp fixtures outside traffic paths. A shared baked irradiance texture lights road, pavement, building and vehicle materials in world space with distance/height falloff. This is surface illumination, not just glowing bulbs or overlay quads, and avoids 74 dynamic shadow passes. Eight headlight cones nearest the camera focus are pooled in the surface shader; all vehicles have visible night headlights/taillights. Signals, incident markers, selection and heatmaps use unlit materials for readability.

The lamp map approximates illumination without building occlusion, so light can reach surfaces behind structures. Distant headlight cones are omitted while their bulbs remain visible. This is a practical renderer, not a photometric or ray-traced model. Daylight retains the existing shadow shader, with bounds updated when the sun direction changes.

## Verification

```powershell
& '..\.venv\Scripts\python.exe' -m unittest discover -s tests -v
& '..\.venv\Scripts\python.exe' -m traffic.recovery_experiments
& '..\.venv\Scripts\python.exe' main.py --smoke-recovery
& '..\.venv\Scripts\python.exe' main.py --smoke-behaviour
```

Regressions cover membership-only/idempotent cleanup, several cars traversing a cleared site, endpoint wreck retention, 30-to-100 capacity admission, decrease/increase recovery, blocked-entry recovery and pause/reset. Wrong-way tests cover natural seeded selection, sustained return, reproducibility, reaction/braking bounds, oncoming contact, valid geometry and lighting transitions. The previous 43 tests remain, including overtaking, near misses and contact deduplication.

Exports in `artifacts/recovery/` include actual admitted traits, removal reasons, risky decisions, manoeuvres, incidents, exposure and admission blockers. Performance observations are from this machine, not frame-rate guarantees.

## Current results

**52 tests pass**, preserving all previous 43. All five ordinary runs below had zero invalid positions and zero interpenetrations. Active/admitted/removal counts reconcile, and removal IDs are unique. All runs use accident mode, seed shown, 30 s green and 45 s clearance.

| Scenario / seed / target | Seconds | Admitted Normal / Newbie / Drunk | Active / pending | Trips | Vehicle-km | Incidents / involved | Safety corrections |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Evening/night / 42 / 40 | 180 | 46 / 12 / 12 | 26 / 14 | 31 | 7.90 | 7 / 16 | 3 |
| Evening/night / 43 / 40 | 180 | 42 / 14 / 9 | 21 / 19 | 25 | 7.59 | 10 / 21 | 6 |
| Evening/night / 44 / 40 | 180 | 43 / 15 / 13 | 21 / 19 | 32 | 8.49 | 9 / 20 | 6 |
| Baseline / 42 / 100 | 120 | 69 / 0 / 0 | 39 / 61 | 30 | 7.23 | 0 / 0 | 15 |
| Evening/night / 42 / 100 | 120 | 52 / 9 / 12 | 36 / 64 | 23 | 6.46 | 6 / 14 | 3 |

Ordinary manoeuvre frequency: **zero overtaking and zero wrong-way assessments, attempts, completions or aborts** in all five runs. The three target-40 night runs cover nine simulated minutes and 34 admitted drunk drivers. The small map and excluded access roads constrain opportunities; these runs do not establish frequent natural wrong-way driving. Separately, the normally sampled seed-3 city fixture produced one assessment, one departure, one sustained episode and one return. Controlled tests also demonstrate overtaking, an abort and actual oncoming contact.

Target 100 did not reach 100 on the ordinary city: the final 120 s runs had 39 active in Baseline and 36 at night, with 61/64 pending. This is reported as entry-capacity blockage, not successful admission of 100. The long-corridor capacity regression reaches 100 through ordinary safe admission, including after a decrease/increase cycle.

Actual GUI checks passed for dark night and lamp illumination, day/night switching without duplicate fixtures, seeded wrong-way travel and return, a car traversing the cleared crash site, inspector/heatmap readability and population-slider admission. The overtaking GUI smoke also passed. Screenshots are saved as `artifacts/recovery-*.png` and `artifacts/driver-revision-pass.png`. The GUI report is `artifacts/recovery-gui.json`. Mouse dragging itself remains a manual interaction; automation invokes the real slider callback.

On this machine, the final GUI check rendered 40 active vehicles at a mean 14.42 ms per measured render call, and target 100 with **38 actually active** at 14.17 ms. These are 30 paused-scene render samples, not complete running-frame times or a benchmark of 100 active vehicles. Advancing the target-100 simulation for 60 simulated seconds took 6.97 wall seconds; it admitted 56 vehicles in total and ended with 62 pending. Full experiment wall times additionally include per-step geometry assertions and concurrent validation load, so they are not pure engine benchmarks.


## Retained metric definitions and limits

Distance is actual centre travel in vehicle-km. Waiting is speed below 0.05 m/s, including red lights and wrecks, excluding separately counted bus dwell. Waiting fraction divides by all active vehicle-seconds. Incident rates divide origins by vehicle-km; zero exposure reports N/A. Involved counts unique IDs. Road usage counts directed-lane entries once per route occurrence, including initial partial traversals. Accident cells count origins in 16 m cells and survive clearance. Reset starts fresh history.

Risk/contact association within two seconds is temporal evidence, not fault or unique causation. The model is not calibrated to real crash rates and does not model injury, deformation, pedestrians, towing, articulated vehicles or an empirical optimum. Results in [docs/driver-revision.md](docs/driver-revision.md) and earlier milestones predate this revision; fair queue rotation and new behaviours can change seeded runs.
