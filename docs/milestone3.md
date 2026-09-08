ï»¿# Crossing City â€” Python + Prolog Traffic Lab

Milestone 3 extends the existing nine-block city with independent vehicle and
driver properties, contextual curb demand, bus service, and inspectable risky
choices under temporary collision prevention. No accident counting or heatmaps.

## Launch and environment

From `traffic-simulator` in PowerShell:

```powershell
& '..\.venv\Scripts\python.exe' main.py
```

The existing Python 3.14.7 environment is unchanged. Dependencies remain Ursina
8.3.0, Panda3D 1.10.16, and janus-swi 1.5.3; see `requirements.txt`. SWI-Prolog
10.0.2 must be available through `swipl`. No Blender or downloaded models.
If packages need restoring, use the existing interpreter:

```powershell
& '..\.venv\Scripts\python.exe' -m pip install -r requirements.txt
swipl --version
```

Janus consults the project-relative `traffic/rules.pl` once at startup. Loading
errors produce an actionable terminal message; Python does not substitute rules.

## Controls

| Control | Effect |
| --- | --- |
| Global green slider | Primary experiment control: 5â€“120 simulated seconds |
| Click a signalized junction centre | Show its active/pending timing and local override slider |
| Use global timing | Remove the selected local override |
| Run setup | Open the separate scenario/population panel |
| Scenario button | Reset run, clock, seed, vehicles, statistics, signal timing and camera; retain your population target |
| Target population | 0â€“100; safely queue increases and let excess cars finish after decreases |
| Click any vehicle | Inspect type/profile, origin/destination, speed, reaction, gap, Prolog proposal, execution, intervention and bus status |
| Pause / Resume / Space | Freeze all simulation time, motion, signals, reactions and bus dwell |
| Reset / R | Restart the current scenario with target 40, its initial clock, seed 42, default timing and no overrides |
| Home view / H | Restore the fitted overview |
| WASD / arrows; mouse wheel | Bounded pan and zoom outside UI panels |

The original signal cycle remains NS green â†’ NS amber (3 s) â†’ all red (1 s) â†’
EW green â†’ EW amber (3 s) â†’ all red (1 s), default green 30 s. Requests apply at
the next green boundary, never mid-phase. Local overrides survive global edits.
Roundabouts have no timing slider. Gold outlines identify the current selection.

The header shows clock, elapsed seconds, active/target population, queued demand,
completed trips, safety interventions, violation attempts and live type/profile
counts. UI anchors were checked at 1440Ã—900 and 1000Ã—720. Zoom for model detail.

## Vehicle and driver assumptions

All parameters below are **illustrative modelling assumptions**, not empirically
validated statistics. Edit `traffic/parameters.json` and restart to configure
vehicle limits, bounded driver distributions, initial mix, fleet size and dwell.
The default 40-vehicle mix is 32 sedans, five trucks and three buses. The configured
initial mix must total 40. Smaller scenario-reset targets scale this mix; targets
over 40 start 40 vehicles and queue the remainder.

| Vehicle | Length Ã— width (m) | Acceleration / braking (m/sÂ²) | Nominal speed (m/s) | Minimum path radius (m) |
| --- | --- | --- | --- | --- |
| Sedan | 4.4 Ã— 1.8 | 2.4 / 4.5 | 10 | 2.5 |
| Truck | 7.2 Ã— 2.3 | 1.25 / 3.5 | 8 | 3.0 |
| Bus | 9.0 Ã— 2.3 | 1.1 / 3.5 | 8 | 3.5 |

These are rigid vehicles, including a compact bus and a rigid delivery truck.
They are not articulated models. Vehicle acceleration/braking limits are separate
from driver speed preference and acceleration multipliers. Requested acceleration
is capped at the vehicle engine limit, even for multipliers above one. Emergency
supervisor clamps can exceed ordinary braking limits; they are temporary
collision prevention, not a claim of physically realistic emergency braking.
The current connector pavement supports vehicles up to 9 m long and 2.3 m wide;
larger configured envelopes are rejected until geometry is extended.

| Profile | Desired-speed multiplier | Reaction delay (s) | Preferred gap (m) | Acceleration multiplier | Extra entry clearance (m) |
| --- | --- | --- | --- | --- | --- |
| Normal | 0.92â€“1.04 | 0.25â€“0.45 | 2.5â€“3.3 | 0.90â€“1.00 | 0â€“0.7 |
| Newbie | 0.75â€“0.92 | 0.70â€“1.20 | 3.8â€“5.3 | 0.65â€“0.82 | 2.0â€“3.5 |
| Drunk | 0.90â€“1.18 | 0.90â€“1.70 | 1.1â€“2.8 | 0.85â€“1.08 | 0â€“0.4 |

Individual parameters are sampled once from bounded uniform ranges. Separate,
seeded per-vehicle random streams sample behaviour episodes every 4â€“7 simulated
seconds, independent of rendering. Newbies have a 0.25 chance of a short 0.8â€“1.8 s
hesitation window per episode. Drunk profiles have 0.25 signal-risk and 0.35
unsafe-gap flags, an additional 0.85â€“1.15 speed multiplier, and a 0.05 hesitation
chance. These are conditional episode flags, **not crash probabilities or measured
rates**. Normal drivers have no intentional violation/gap-risk flags.

Reaction delay is a timestamped observation queue. A driver responds to the
observation old enough for its sampled delay, not the latest signal/gap snapshot.
On entry to a new route segment it waits for a matching delayed observation.
`delayed_response`, `waiting_for_larger_gap`, `hesitating`,
`yielding_to_circulating_vehicle`, `unsafe_gap_accepted` and `signal_violation`
are real Prolog explanation codes shown by the inspector.

## Contextual demand, clock and buses

The presets select both a starting schedule time and a profile mixture:

- **Baseline:** 12:00, normal drivers only; all three vehicle types remain active.
- **Morning commute:** 07:30, apartment departures and office arrivals weighted
  higher; school/university demand increases. University departures have a larger
  newbie share during commute periods.
- **Evening/night:** 21:00, office departures and apartment arrivals weighted
  higher; pub departures include a larger drunk share, alongside normal/newbie
  drivers. No location uniquely determines a driver's profile.

`traffic/demand.py` contains explicit weights, seven named curb access points and
route connections. Normal/Newbie/Drunk mixed-preset weights are generally
0.78/0.17/0.05; university commute departures use 0.50/0.45/0.05 and pub evening/night
departures use 0.52/0.13/0.35. Depot requests favour trucks; terminal requests favour
buses. School demand represents **adults or driving-age students**, not children
operating vehicles. Day/night lighting is not simulated; the clock changes demand.

The clock advances exactly one second for each elapsed simulation second.
Signals, reaction queues, dwell, movement, episode durations and scheduling use
that same time base. Scenario starting time is separate from elapsed run time.
Demand weights are sampled when a trip request is created and do not change the
user's target. Selecting a scenario explicitly resets the run, preserving target.

Gold curb markings/signs identify road access for apartments, school, university,
offices, pub, depot and terminal. Trips originate on those valid directed lanes
and finish stopped at their destination curb. Curb arrivals leave the simulation;
parking manoeuvres, driveways and pedestrians are not modelled. The initial mix is
safely distributed midway along valid contextual routes rather than all appearing
at entrances. Vehicles never originate inside a building or on a sidewalk.

Queued requests retain their origin, destination, type and individual profile
while blocked. Admission checks actual dimensions, approaching traffic's stopping
distance and junction-exit reservations. The queue rotates across eligible access
points; it does not force entry through an occupied lane. Reducing target cancels
only unentered requests and lets active trips finish. **Target** is the desired
active population; **queued demand** is the set of fully specified, unentered
requests waiting for safe access. A shortage may briefly precede request creation
at the next 10 Hz decision step. High targets can remain partly queued.

The designated bus line follows connected perimeter lanes from Terminal around
the city and back to Terminal, with marked blue `B` stops at School, University,
Offices curb and Terminal. Stops dwell eight simulated seconds by default, once
per route occurrence. Buses initially placed past a stop have already served that
stop. The origin terminal is a departure point; the return terminal is served.
A configurable three-bus service fleet prevents endlessly accumulating buses on
the longer route; a new service starts when fleet capacity becomes available.

## Geometry, Prolog and temporary safety supervision

The original 14 signals, two roundabouts, right-hand lanes, seeded routing and
60 Hz fixed timestep remain. Prolog proposals run at 10 Hz and signal transitions.
Road rendering and routing share smooth BÃ©zier/arc geometry. Roundabout entry/exit
transitions were lengthened to 20 m from centre and reshaped for gentler curvature;
the ring radius remains 10 m. Islands are 6 m radius, and connector pavement widens
towards curved portions. Every current connector meets the configured radius
limits; sampled long-vehicle corner checks also verify island clearance.

Following calculations use both vehicles' half-lengths. Exit admission requires
room for the incoming vehicle's rear to clear, plus its preferred gap. Reservations
release only when the rear is at least 0.75 m beyond the connector exit. Conflicts
use actual vehicle bounding-circle envelopes plus the path-sampling allowance;
they do not assume every vehicle is a sedan. Nonconflicting roundabout paths may
still be occupied simultaneously. Reservations are deliberately conservative.

All decision observations use one pre-movement snapshot. Prolog owns discrete
signal/yield/driver decisions; Python computes geometric observations and executes
continuous acceleration and braking. Existing oldest-queue fairness is extended
with a claim on conflicting paths after 60 s, keeping a gap open long enough for
delayed observations to arrive. Existing circulating vehicles retain priority;
claims neither revoke a reservation nor reserve the entire roundabout.

`traffic/supervisor.py` is a separate, temporary supervisor. It validates proposed
entry against current reservations and exit room, caps physical following travel,
and tests simultaneous midpoint/end poses using oriented rectangles. Proposed
Prolog action/reason are never overwritten. The inspector separately reports
executed motion (proceed/brake/wait) and the intervention reason. An intentional
red-signal proposal can execute if current geometry is safe; conflicting traffic
is held by reservations. Stale, non-intentional red-entry proposals are stopped.

Interventions count once per vehicle, route occurrence and cause; repeated 60 Hz
clamps or refreshed behaviour samples do not inflate that episode. Attempted
signal violations count a Prolog `signal_violation` proposal near the stop line
once per approach occurrence. These are **supervised behavioural events, not
accidents**. This stage cannot measure accident rates. Zero interventions would
not establish realistic behaviour or validate these assumptions.

A future accident-mode supervisor can replace entry/movement/following prevention
while retaining `spawn_clear`. No accident mode is exposed in this milestone.

## Modules

| Module | Responsibility |
| --- | --- |
| `profiles.py`, `parameters.json` | Independent immutable driver/type specifications and sampled configuration |
| `demand.py` | Scenario weights, curb accesses, requests, bus route and stops |
| `network.py`, `lanes.py` | Directed paths, geometry, conflict separation and metre-based constants |
| `simulation.py` | State, reaction histories, fixed updates, demand admission, dwell and kinematics |
| `signals.py` | Active/pending global and local timing state |
| `prolog.py`, `rules.pl` | Janus bindings and discrete Prolog policies |
| `supervisor.py` | Explicit temporary physical safety and event deduplication |
| `rendering.py`, `ui.py`, `main.py` | Procedural assets, scene, controls, inspection and application lifecycle |
| `verification.py`, `tests/` | Headless scenario audits and regression checks |

## Verification

```powershell
& '..\.venv\Scripts\python.exe' -m unittest discover -s tests -v
& '..\.venv\Scripts\python.exe' -m traffic.verification --seconds 600 --scenario Baseline
& '..\.venv\Scripts\python.exe' -m traffic.verification --seconds 600 --scenario 'Morning commute' --drain
& '..\.venv\Scripts\python.exe' -m traffic.verification --seconds 600 --scenario 'Evening/night'
& '..\.venv\Scripts\python.exe' main.py --smoke-test
```

Twenty tests cover the original phase/routing/yield/timing/reset checks plus
parameter bounds, independent driver/type combinations, delayed observations,
persistent randomness, reproducibility, controlled Prolog behaviour differences,
contextual weights, long-vehicle radii/rear clearance, bus routes/dwell, safe entry,
gradual population reduction and event deduplication. Prior curb-entry and yield
reason assertions were updated for the new access points and explanation codes.

Final runs used seed 42, target 40, default signal timing and 600 simulated seconds:

| Scenario | Trips completed | Final active / queued | Max stationary wait | Waiting fraction | Safety interventions | Signal attempts |
| --- | --- | --- | --- | --- | --- | --- |
| Baseline | 134 | 29 / 11 | 91.03 s | 62.0% | 50 | 0 |
| Morning commute | 95 | 16 / 24 | 255.22 s | 71.5% | 39 | 9 |
| Evening/night | 115 | 25 / 15 | 126.45 s | 59.0% | 83 | 18 |

All three audits found **zero physical overlaps and zero invalid positions**.
Baseline and morning runs observed two vehicles using a roundabout simultaneously.
The morning run had seven vehicles with waits over 180 s; all seven completed by
600 s. Switching its target to zero then drained every remaining trip in 259.07 s.
No sustained network-wide lack of completion was detected. The transient morning
queue is retained and reported, not hidden with forced departures.

The initial diagnostic caught accumulating bus services and insufficient
long-vehicle exit accounting. The final implementation uses the explicit service
fleet cap and rear-clearance checks described above. A separate starvation check
also led to keeping claimed gaps open through reaction delays.

The audits check actual-sized oriented rectangles and finite path positions at
every fixed step. A three-minute individual wait is a recorded queue warning;
six stationary minutes or three minutes without any completed trip fail the audit.
The morning queue warning was investigated by tracing the affected vehicles and
running the remaining demand down to zero; no teleportation or forced deletion
was used. Waiting fraction is stopped non-dwelling vehicle-seconds divided by
observed vehicle-seconds, not a driver-profile congestion score.

These runs vary demand, trip lengths, vehicle mix and driver samples together.
They do not isolate a causal driver-profile effect. Do not infer that any profile
always causes more congestion, or convert intervention counts into accident rates.

The GUI was launched and visually inspected in overview and resized views, during
a truck's roundabout turn and a bus's actual stop dwell. Smoke checks also cover
scenario reset/target preservation, old timing controls, pause, reset and Home.
Screenshots are saved as `artifacts/milestone3*.png`. Physical mouse interactions
remain a short manual check: click each vehicle type, drag timing controls, select
a roundabout, open Run setup and resize; confirm panels block camera input.

## Remaining limitations

Rigid sedan/truck/bus models, conservative whole-connector reservations and
lane-centred bus dwell simplify real traffic. Dwell blocks its lane; no pull-in
animation, overtaking, dynamic rerouting, passengers or parking simulation.
Context is weighted curb demand, not a calibrated population/activity model.
Traffic can queue for minutes and active count can remain below target while safe
entry is blocked. Full map fitting makes vehicles small; use zoom for inspection.
Shadows depend on graphics support; long window stalls can require timestep
catch-up. There are no crashes, accident counter, heatmaps, pedestrians, road
editor or empirically calibrated claims.
