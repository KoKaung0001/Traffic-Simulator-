# Crossing City ? Python + Prolog Traffic Lab

Milestone 4 adds physical contacts, persistent crash incidents, clearance,
road-usage and accident-location overlays, exposure metrics, and reproducible
headless comparisons to the existing city. Procedural sedan/truck/bus models,
contextual demand, driver profiles, Janus Prolog decisions, signal controls,
inspection, seeded behaviour and 60 Hz simulation remain.

## Launch

From `traffic-simulator` in PowerShell, using the existing environment:

```powershell
& '..\.venv\Scripts\python.exe' main.py
```

The GUI starts in **accident mode**, Baseline (normal drivers), target 40.
Choose Evening/night or Morning commute under Run setup for mixed drivers.
No packages were added: Python 3.14.7, Ursina 8.3.0, Panda3D 1.10.16,
janus-swi 1.5.3, SWI-Prolog 10.0.2. `requirements.txt` retains the dependencies.
Janus consults `traffic/rules.pl`; unavailable Prolog produces an actionable
startup error, not a Python fallback.

```powershell
& '..\.venv\Scripts\python.exe' main.py --mode supervised
& '..\.venv\Scripts\python.exe' main.py --clearance 60
```

`--clearance` is a positive duration in simulated seconds (default 45).
There is no accident-probability control.

## Controls

| Control | Effect |
| --- | --- |
| Global green slider | 5?120 simulated seconds, applied at the next green boundary |
| Click a signalized junction | Inspect active/pending timing and set a local override |
| Use global timing | Remove selected local override |
| Run setup | Scenario, gradual target population (0?100), mode switch |
| Scenario or mode button | Reset run/clock/randomness/statistics/overlays/signals; retain population target |
| None / Road usage / Accidents | Select exactly one overlay |
| Click vehicle | Type/profile, trip, speed, reaction/gap, proposed and executed actions, safety correction, bus or incident state |
| Click orange incident marker | Incident ID, origin/time, involved vehicles, scheduled clearance |
| Pause / Space | Freeze motion, signals, demand, dwell, reactions, metrics and clearance |
| Reset / R | Restart current scenario and mode, target 40, default 30 s green, no local overrides |
| Home / H | Restore fitted full-city view |
| WASD / arrows / wheel | Bounded pan and zoom outside UI panels |

Signals retain NS green ? NS amber (3 s) ? all red (1 s) ? EW green ?
EW amber (3 s) ? all red (1 s). Local overrides survive global timing edits.
Roundabouts have no timing slider. Gold outlines indicate selection.
Reducing target lets ordinary trips finish; increasing target safely queues
requests. Wrecks remain active population until clearance.

## Safety audit and mode policy

The unchanged Milestone 3 Baseline run was reproduced before enabling accidents:
**134 trips, 50 interventions, zero signal attempts** over 600 seconds,
seed 42, target 40, 30 s green. The interventions were:

- 45 reserved conflicts: 32 `roundabout_gap` and 13 `green_and_clear` proposals.
- Four blocked exits: `green_and_clear` proposals.
- One stale red entry: `amber_committed` proposal.
- Zero physical following clamps and zero overlap-prevention interventions.

All were `proceed` proposals corrected using newer reservation, exit or signal
state than the driver's delayed observation. They do not imply 50 crashes.
The two roundabouts accounted for 32 corrections. No baseline following,
braking, geometry or timestep defect was identified that required a correction.
The current-state checks were retained. See [the detailed cause/location audit](docs/milestone4-audit.md)
and `artifacts/safety-audit-m4-before.json` for individual records.

| Protection | Supervised | Accident |
| --- | --- | --- |
| Safe spawn admission / physical clearance | Always | Always |
| Normal yielding, red checks, exit room and reservation arbitration | Retained | Retained |
| Unsafe-gap or intentional signal-violation entry | Subject to current reservations/exit room | May bypass entry compliance |
| Preferred and emergency following gap | Retained | Unsafe-gap proposal may bypass; retained otherwise |
| Movement overlap prevention | Diagnostic midpoint/end prevention | Swept physical contact creates wrecks |
| Perception of stationary wrecks | Available | Route queue plus geometric crossing-path lookahead |

A signal violation alone does not bypass longitudinal following. Intentional
unsafe gap execution can cause a rear-end contact or enter conflicting traffic.
Other drivers still obey their own rules and may react to that movement. Normal
emergency gap clamps remain conservative and may exceed nominal braking limits.
This is an explicit modelling choice, not a calibrated crash-risk model.

`Simulation` defaults to supervised mode for existing headless callers/tests;
the GUI and experiment command default to accident mode. Safety intervention
and attempted-violation counters remain separate from physical accident counts.
Interventions deduplicate by vehicle, route occurrence and cause; near-stop-line
signal attempts deduplicate by vehicle/approach occurrence.

## Collision and incident definitions

Positions and vehicle dimensions use metres. Actual rigid, oriented rectangles
are tested, not centre-distance accidents or random crash probabilities.
`collisions.py` inserts swept bounds into a **16 m spatial hash**, deduplicates
candidate pairs, and performs separating-axis tests. Motion is split at every
sampled path vertex and route boundary. Within each interval, the existing path
model has linear translation and a constant heading, so swept SAT solves the
whole time interval analytically. Fast vehicles cannot skip a narrow obstacle
between sampled frames. Boundary headings are checked as well.

The earliest contact stops the involved vehicles; remaining trajectories are
rechecked against the newly stationary wrecks in the same timestep. Cars retain
valid path coordinates and dimensions. A touching boundary is contact; a
positive separating gap is a near miss. Geometry validation separately rejects
non-finite/off-path positions and penetration beyond a 1 mm numerical tolerance.
The polyline heading changes are still discrete approximations of the drawn
curves; there is no rigid-body rotation, deformation, rebound or injury model.

An incident records its unique ID, first contact step/time, midpoint between
contacting centres (the **recorded origin**, not a forensic impact point),
vehicle IDs/types/profiles, recent proposed/executed actions, current and delayed
signal observations, contact pairs, and scheduled/actual clearance times.
Times are elapsed simulated seconds, quantized to the contact step (1/60 s).
Logs describe preceding actions and physical involvement, not legal fault.

Simultaneous contact components receive one incident ID regardless of pair
iteration order. Repeated stationary contact does not create another incident.
A new vehicle physically contacting an active wreck joins that incident and
extends clearance to 45 seconds after the latest contact (configurable).
There is **no proximity-only merging**. If an unusual later bridge connects two
already established incidents, both historical origins/IDs remain counted and
the log links them; a new arrival joins the oldest physically contacted origin.
This preserves two historically separate accidents rather than rewriting their
origin heatmap. IDs and unique involved-vehicle counts persist until reset.

At clearance, all wrecks assigned to that incident leave together. Clearance
uses simulation time and freezes on pause. Removals open population capacity;
queued replacement demand uses the same safe admission checks, with no immediate
replacement at the crash site. Crashed trips are not counted as completed trips.
Wrecks hold their last path/entry state and physically obstruct following traffic.
There is no rerouting, tow-truck animation, overtaking or road closure editor.

## Heatmaps and metrics

Both overlays accumulate **since reset**, with the elapsed period in the legend.
Road usage counts an entry into each **directed lane**, once per vehicle route
occurrence. Initial partial traversals count once. A repeat traversal later in a
route counts again. Junction/roundabout connectors are excluded. Waiting on a
road never increments this count; it is usage, not occupancy or congestion.

Accident locations count each incident origin once in fixed world-aligned
16 ? 16 m cells, including negative coordinates using floor division. Pile-up
arrivals and repeated contact do not add origins. History remains after clearance.
The two layers are mutually exclusive and drawn at road height, below vehicles,
signals and selection highlights. Fixed shared bins apply across every run:

| Layer | Colour bins from blue-grey to yellow, orange, red |
| --- | --- |
| Road usage | 0 / 1?24 / 25?49 / 50+ entries |
| Accident cells | 0 / 1?2 / 3?4 / 5+ incident origins |

Zero accident cells are transparent. With no incidents the accident map is blank
and the legend explicitly states this; the scale never rescales to a run maximum.
Road usage is already nonzero at a normal reset because initial admissions count.
A target-zero reset has zero usage and zero exposure.

| Dashboard / exported metric | Definition |
| --- | --- |
| Total accidents | Distinct incident origins since reset |
| Active incidents | Origins whose wrecks have not cleared |
| Vehicles involved | Unique physical vehicle IDs in incidents since reset |
| Active / target | All present vehicles, including wrecks / desired population |
| Completed trips | Ordinary destination arrivals; excludes clearance removals |
| Mean speed | Arithmetic mean m/s across currently active vehicles, including stopped/wrecked |
| Waiting vehicle-seconds | Speed below 0.05 m/s; includes red-light waits and wreck time; excludes scheduled bus dwell |
| Waiting fraction | Waiting vehicle-seconds / all active vehicle-seconds, including dwell/wreck exposure |
| Bus dwell vehicle-seconds | Separate accumulated scheduled dwell; fixed-step accounting |
| Distance | Sum of actual centre travel through contact or arrival, reported as vehicle-km |
| Accidents / 1,000 vehicle-km | Incident origins ? 1,000 / distance in vehicle-km; N/A (CSV blank, JSON null) at zero distance |

Average speed is a snapshot; waiting and distance are cumulative. These measures
have different denominators and should not be interpreted interchangeably.

## Reproducible headless experiments

```powershell
& '..\.venv\Scripts\python.exe' -m traffic.experiments --scenario 'Evening/night' --seed 42 --duration 600 --green 30 --mode accident
& '..\.venv\Scripts\python.exe' -m traffic.experiments --scenario Baseline --seed 42 --duration 600 --green 30 --mode supervised
& '..\.venv\Scripts\python.exe' -m traffic.experiments --scenario 'Evening/night' --seed 42 --duration 180 --compare --output artifacts/milestone4-comparison
```

Also accepts `--population` (default 40), `--clearance` (45), and `--output`.
`--compare` runs 15, 30 and 60 seconds green, each with seeds 42/43/44 when
`--seed 42` is used. Scenario, target, start clock, initial state for each seed,
duration and mode are held fixed. All local overrides are cleared. Each headless
run starts its first green at the requested duration; interactive slider edits
still apply at the next phase boundary.

Each run exports a CSV row and a JSON incident/configuration log. `results.csv`
collects the rows; `comparison.json` contains means, sample standard deviations
and ranges. JSON includes the full parameter configuration, units/metric
definitions, fixed timestep, seed, starting time, elapsed duration, local override
state, road counts, incident cells and safety corrections. Use a distinct output
directory for separate experiment batches; a batch replaces its results table.

Initial seeding retains the original distribution algorithm. After initialization,
individual driver parameter sampling uses a separate seed+7919 stream; demand
and routing retain the seed stream. Behaviour episodes use per-vehicle
seed?1000003+ID streams. Random choices occur in simulation decisions, not render
frames. Traffic evolution can still change request creation, admitted IDs,
realized driver samples and vehicle-distance exposure. Paired seeds do not imply
identical populations throughout a run, or isolate a causal driver-profile effect.

### Recorded comparison

Evening/night, start 21:00, target 40, accident mode, clearance 45 s, **180 seconds
per run**, seeds 42, 43 and 44; no local overrides or parameter tuning:

| Green | Incidents by seed | Incidents mean ? sample SD | Trips mean ? SD | Distance mean vehicle-km | Waiting fraction mean |
| --- | --- | --- | --- | --- | --- |
| 15 s | 5, 5, 2 | 4.00 ? 1.73 | 42.00 ? 2.00 | 10.22 | 58.4% |
| 30 s | 3, 4, 4 | 3.67 ? 0.58 | 38.67 ? 3.06 | 9.18 | 64.4% |
| 60 s | 2, 3, 4 | 3.00 ? 1.00 | 31.67 ? 2.31 | 7.55 | 71.4% |

The counts overlap across timings and distance exposure differs substantially.
Three short runs per setting do not establish an optimum. The assumptions are
illustrative; the resulting rates are not real-world accident predictions.
CSV and detailed logs are in `artifacts/milestone4-comparison/`.

A separate 600-second Baseline check at seed 42 and 30 s green completed 117 trips
with 50 safety corrections and **zero accidents in both modes**. The two modes
matched traffic metrics. Changed subsequent random-stream allocation explains
why this new run differs from the archived Milestone 3 134-trip run.

## Validation

```powershell
& '..\.venv\Scripts\python.exe' -m unittest discover -s tests -v
& '..\.venv\Scripts\python.exe' main.py --smoke-m4
& '..\.venv\Scripts\python.exe' main.py --smoke-test --mode supervised
```

**30 tests pass**, including all original 20. New deterministic checks cover swept crossing and
rear-end contacts, truck/bus dimensions, fast motion, path bends, near misses,
persistent contact deduplication, pile-up association versus separate nearby
origins, road passage counts, zero exposure, wreck queues, pause, clearance,
reset, safe spawning around wrecks, simultaneous multi-car component identity,
and explicit unsafe admission. All nine recorded comparison runs and the
600-second accident-mode Baseline check reported **zero invalid positions and
zero interpenetrations**, independently of valid contact counts.

GUI smoke captures inspect a naturally occurring incident from the seeded mixed
scenario, its wreck and following queue, incident/vehicle details, both overlays,
legends, a 1000?720 resize, pause/reset and an empty accident map. Screenshots are
`artifacts/milestone4-*.png`. The Windows drawable initially returned black
captures; explicitly rendering before capture resolved this. Physical mouse
clicks/drags are not automated; callbacks and panel layout are checked.
The retained GUI smoke also passed signal controls, target-preserving scenario
reset, truck roundabout turns and actual bus dwell.

## Retained modelling assumptions and modules

`traffic/parameters.json` configures illustrative driver distributions, independent
vehicle limits, initial 32-sedan/5-truck/3-bus mix, behaviour intervals and 8 s bus
dwell. Rigid vehicle dimensions are Sedan 4.4?1.8 m, Truck 7.2?2.3 m, Bus 9?2.3 m;
nominal speeds 10/8/8 m/s. Larger than the verified 9?2.3 m pavement envelope is
rejected. Newbie hesitation and Drunk risk flags affect actions, not accident
probabilities. Driver profiles never establish fault.

Baseline starts at noon with Normal drivers. Morning commute starts at 07:30;
Evening/night at 21:00. Contextual access weights distinguish Apartments, School,
University, Offices, Pub, Depot and Terminal. School traffic represents adults or
driving-age students. Queued requests retain their sampled traits. The initial
mix is distributed safely midway along valid routes. Curb arrivals leave without
parking animation. The three-bus fleet follows a connected perimeter route with
marked stops; lane-centred dwell blocks following traffic. Day/night lighting,
empirical demand calibration, pedestrians and passengers are not modelled.

| Module | Responsibility |
| --- | --- |
| `network.py`, `lanes.py` | Shared metre-based road paths, supported curvature and reservation conflicts |
| `profiles.py`, `parameters.json`, `demand.py` | Vehicle/profile specifications, seeded contextual trips and bus service |
| `simulation.py`, `signals.py` | Fixed-time state, motion, demand, signal cycles and integration |
| `prolog.py`, `rules.pl` | Real Janus/Prolog discrete proposals and explanations |
| `supervisor.py` | Diagnostic protection, safe spawn and auditable corrections |
| `collisions.py`, `incidents.py` | Spatial hash, swept SAT, contact lifecycle and exposure metrics |
| `rendering.py`, `ui.py`, `main.py` | Procedural city, vehicle models, controls, overlays and inspection |
| `experiments.py`, `verification.py`, `tests/` | Exported comparisons, legacy supervised audits and regression checks |

Whole-connector reservations remain conservative for compliant drivers. Traffic
may queue for minutes and safe admissions may keep active population below target.
No model here is calibrated for real traffic-safety conclusions. The detailed
Milestone 3 assumptions and original verification are preserved in
[docs/milestone3.md](docs/milestone3.md) as historical documentation.
