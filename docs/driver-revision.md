# Crossing City - Python + Prolog Traffic Lab

This revision changes driver behaviour before visual polish. It retains Milestone
4 collisions, incidents, heatmaps, metrics, contextual demand and the existing
city. Driver personalities are stable; temporary episodes and delayed perception
now affect actual acceleration/braking. Limited sedan overtaking uses explicit
paths in the opposing lane. There is no random accident generator.

## Launch and controls

```powershell
& '..\.venv\Scripts\python.exe' main.py
```

The GUI defaults to **accident mode**. The active mode is printed in the header
beside scenario and elapsed time, and in Run setup. Baseline starts at noon with
Normal drivers only. Choose Morning commute (07:30) or Evening/night (21:00) for
mixed drivers. Scenario changes reset the run; mode changes also reset it.

```powershell
& '..\.venv\Scripts\python.exe' main.py --mode supervised
& '..\.venv\Scripts\python.exe' main.py --clearance 60
```

| Control | Effect |
| --- | --- |
| Run setup | Scenario, active mode toggle, target population and current type/profile counts |
| Global green slider | 5-120 simulated seconds, applies at next green boundary |
| Click signal junction | Inspect phase; set local timing override or Use global |
| Click vehicle | Personality, speed, actual/perceived gap, reaction, episode, Prolog proposal/control, execution, passing state and incident |
| Click orange incident marker | Incident origin, time, involved IDs and clearance |
| None / Road usage / Accidents | Mutually exclusive cumulative overlays |
| Pause / Space | Freeze all simulated time and counters, including clearance |
| Reset / R | Current scenario/mode, target 40, default 30 s green, no overrides |
| Home / H | Fitted city overview |
| WASD / arrows / wheel | Pan/zoom outside the existing UI panels |

Scenario/mode resets retain target; the Reset button restores target 40. Normal
trip completion gradually reduces population after a target decrease. Safe
admission queues increases. The UI changes in this revision only expose required
behaviour diagnostics; assets, palette, scenery and layout have not been polished.

Use the existing parent environment. Dependencies remain Python 3.14.7, Ursina
8.3.0, Panda3D 1.10.16, janus-swi 1.5.3 and SWI-Prolog 10.0.2. No packages were
added. Janus loads `traffic/rules.pl`; Prolog failure does not fall back to Python.

## Audit of the previous decision path

Before editing behaviour, the unchanged engine ran every scenario for 300 seconds
with seeds 42/43/44, target 40, 30 s green, accident mode. The accident counts were:

| Scenario | Seed 42 | Seed 43 | Seed 44 |
| --- | --- | --- | --- |
| Baseline | 0 | 0 | 0 |
| Morning commute | 3 | 1 | 2 |
| Evening/night | 5 | 6 | 6 |

Thus the old physical collision path was reachable; absence of crashes in a manual
run did not establish a counter bug. The GUI default and visible mode were checked.
The exact manual run settings cannot be reconstructed from the report alone.
Different target, timing, pauses, exposure and admitted profiles can matter.
`artifacts/behaviour-before.json` records admitted profiles, risky decisions,
actual movement, trips, distance and interventions for the unchanged runs.

The complete path audit found these limitations:

1. Delayed observations reached Prolog, but almost every executed movement used
   the **current** following gap, immediate geometric wreck lookahead and a hard
   actual-gap travel cap. Only `unsafe_gap_accepted` bypassed those protections.
   A newbie could hesitate but could not physically brake late into a leader.
2. Current stop-line position caps could erase the consequence of late signal
   recognition. Current reservations were bypassed only for explicit drunk risk
   reason codes, even if other delayed decisions were unsafe.
3. Commitment refreshed all external observations, removing reaction delay inside
   an intersection. It should refresh only the driver's own commitment state.
4. Signal-risk flags were sampled again in each 4-7 s episode at the same approach.
   A driver waiting long enough could keep getting another chance to violate.
5. There was no overtaking path. A same-lane speed boost would not be overtaking.
6. There was no general pre-contact separation in accident mode: swept collision
   resolution itself was already active. Safe spawning was and remains mandatory.

Validation of the revision also caught a stop-margin error: reaching a planned
stopping margin could be mistaken for entering the junction. Commitment now
requires the vehicle's front to reach the physical stop line; a stopped compliant
driver holds position at red. A regression test covers this distinction.

The earlier Normal baseline audit is retained in
[docs/milestone4-audit.md](milestone4-audit.md): its 50 corrections were 45
reservation conflicts, four blocked exits and one stale signal response, not
50 independently established imminent accidents. Normal drivers remain the
regression reference.

## Stable personalities and temporary episodes

All values in `traffic/parameters.json` are **illustrative project assumptions,
not real-world statistics**. Each immutable personality is sampled once when a
vehicle is created, and queued requests retain it. Vehicle type is independent.

Drunk defaults are 75% higher-risk and 25% less-aggressive. Newbies are 70% cautious
and 30% unsteady. These are weights, not a forced exact mixture in each run.

| Profile / subgroup | Weight | Speed multiplier | Reaction s | Preferred gap m | Desired acceleration multiplier |
| --- | --- | --- | --- | --- | --- |
| Normal / standard | 100% | 0.92-1.04 | 0.25-0.45 | 2.5-3.3 | 0.90-1.00 |
| Drunk / higher_risk | 75% | 1.10-1.45 | 0.90-1.80 | 0.7-1.6 | 1.00-1.25 |
| Drunk / less_aggressive | 25% | 0.90-1.08 | 0.70-1.30 | 2.0-3.8 | 0.75-1.00 |
| Newbie / cautious | 70% | 0.88-1.05 | 0.45-0.95 | 3.2-5.3 | 0.65-1.00 |
| Newbie / unsteady | 30% | 0.92-1.15 | 0.80-1.50 | 2.2-4.0 | 0.85-1.15 |

Additional junction-entry margins are 0-0.7 m for Normal, 0-0.3 / 0.3-1.0 m
for the two drunk groups, and 1.5-3.5 / 0-1.5 m for the two newbie groups.

| Subgroup | Applied braking / physical maximum | Gap estimate multiplier | Closing-speed estimate multiplier | Signal / unsafe-entry opportunity probabilities | Pedal overshoot episode probability |
| --- | --- | --- | --- | --- | --- |
| Higher-risk drunk | 0.45-0.80 | 1.10-1.50 | 0.45-0.85 | 0.35 / 0.40 | 0.25 |
| Less-aggressive drunk | 0.75-1.00 | 1.00-1.20 | 0.80-1.00 | 0.08 / 0.12 | 0.08 |
| Cautious newbie | 0.90-1.00* | 0.85-1.05 | 0.90-1.15 | 0 / 0 | 0.08 |
| Unsteady newbie | 1.00 | 1.05-1.40 | 0.55-1.00 | 0 / 0.12 | 0.30 |

*Newbies use maximum vehicle braking once they issue a braking command. Their
error is recognition/timing and pedal control, rather than universally weak brakes.
The cautious multiplier influences the perceived braking threshold. No newbie
intentionally ignores a red signal in these defaults, but late recognition can
still produce an unintentional entry.

Episodes last 4-7 simulated seconds. Hesitation can occupy 0.8-1.8 s; an unsteady
newbie may then accelerate excessively for the remaining episode. Drunk surge
episodes temporarily multiply desired speed by 1.03-1.15. Hesitation probabilities
are 0.04/0.10 for the two drunk groups and 0.25/0.30 for newbie groups. Surges are
selected with conditional probability 0.30 after no hesitation/overshoot episode
was selected. There are no per-frame random draws.

Desired acceleration can exceed the engine preference, but **actual acceleration
never exceeds the vehicle limit**. Pedal overshoot means asking for full engine
acceleration instead of the driver's usual lower value. Nominal sedan/truck/bus
speeds remain 10/8/8 m/s; these are cruise references, not a hard top-speed cap.
Dimensions are 4.4x1.8, 7.2x2.3 and 9x2.3 m; acceleration limits 2.4/1.25/1.1
m/s^2 and braking limits 4.5/3.5/3.5 m/s^2. Contact can stop a vehicle abruptly.

Signal compliance is sampled once when the driver first perceives red on that
route occurrence. Refusal is not rerolled while waiting, even across multiple
signal cycles. Unsafe junction-gap choice is latched per approach; longitudinal
unsafe-gap choice is latched per encountered leader and route occurrence.
Passing willingness is similarly latched per encountered leader. Episode changes
do not reroll these compliance decisions. Not every drunk speeds, violates or crashes.

## Perception, Prolog and physical execution

At 10 Hz, Python forms timestamped signal, leader, closing-speed and wreck
observations. Each mixed driver uses the sample old enough for their reaction
delay and applies their stable estimation biases. The inspector's actual forward
gap is current bumper clearance along the route/forward projection; perceived gap
is the delayed, biased value. On curved/crossing geometry these are longitudinal
estimates, not the exact separating distance between polygons. SAT determines
actual physical contact independently.

Prolog `behave/19` chooses signal/yield behaviour. `drive/10` chooses longitudinal
control from perceived gap, speed, closing speed, hesitation and episode.
`passing/8` chooses overtaking transitions. Python integrates those choices at
60 Hz with vehicle acceleration/braking limits and records proposals separately
from actual motion. Examples include `late_braking`, `acceleration_overshoot`,
`signal_violation`, `unsafe_gap_accepted` and `overtaking_gap_misjudged`.
`late_signal_entry` records a physically executed late entry, not a new random draw.

| Protection | Normal drivers | Mixed drivers, accident mode | Supervised diagnostic mode |
| --- | --- | --- | --- |
| Safe spawn admission | Always | Always | Always |
| Prolog compliance decisions | Retained | Perceived/biased observations | Retained |
| Actual following-gap travel clamp | Retained | Removed | Retained |
| Instantaneous wreck braking | Retained | Wreck observation is delayed | Retained |
| Current reservation/exit veto | Retained | Cannot override a genuine perceived proceed decision | Retained |
| Stop-line position clamp | Retained | Removed; braking is a physical response | Retained |
| Contact handling | Actual geometry | Actual geometry | Diagnostic overlap prevention |

Mixed drivers still brake for perceived red lights, leaders and obstacles; they
are not simply released through all rules. If braking is too late, motion can
cross the stop line and encounter another vehicle. The crossing is registered
as commitment so other drivers can perceive it. Bus service stops/destinations
remain planned constraints. No pre-contact projection separates moving cars.

One extended morning run exposed a polyline-heading boundary issue: rotating the
rectangle directly into the next heading left a small penetration. Resolution
now retains the **first-touch orientation** during that angular transition. Wreck
position/orientation are frozen, and a deterministic roundabout regression covers
it. Swept translation still splits every route/vertex boundary; spatial hashing
and actual-sized SAT remain independent of behaviour. Invalid positions and
penetration beyond 1 mm are checked separately from valid touching contacts.

## Limited overtaking

Only higher-risk drunk **sedans** can attempt it. No truck/bus passing, ghost lane,
teleport or speed-only substitution is used. The state sequence is
`follow -> assess -> move_out -> pass -> return`, with abort returns when feasible.
Prolog can order braking if a perceived oncoming hazard leaves no clear return.

Eligibility requires a moving leader at 0.5-2.5 m/s, at least 4 m/s desired speed
advantage, a leader within 14 m and own speed at least 2 m/s. Willingness is 0.50
per eligible leader opportunity. Assessment lasts at least 0.4 s. It may begin on
entry to the straight road, but lateral movement starts only after a 3 m buffer.

The plan needs two 9 m longitudinal shifts, 6 m passing allowance and a 4 m end
buffer. The sampled cubic paths move 5 m into the real opposing lane and match
lane tangents. Return is installed only after Prolog selects it; centre position
is continuous and vehicle progress follows the new path's actual arc length.
The temporary path is local to that simulation and retains the original route
for return. The base directed-road usage count is not incremented by a lane change.

Both directions of a road with an access/spawn point or bus stop are excluded,
as are portal roads and junction/roundabout connectors. No current mid-block
crossing is present. The state remains on the straight road, before its junction
buffer. Actual opposing vehicles are never removed or reserved away. Their
estimated arrival time uses delayed gap and closing-speed biases, so a perceived
safe pass can encounter oncoming traffic and crash.

Return/abort path construction checks geometry and the current return slot; it
does not reserve future clearance or guarantee avoiding contact. If return cannot
be made, the driver brakes on the opposing lane before the road-end buffer. A
last numerical end guard is logged if reached; it does not move the vehicle back
to safety. It remains exposed to oncoming traffic.

The city is compact: interior straight paths are 24-32 m, and many contain access
points. Natural passing opportunities are therefore narrow. Tests include a
successful pass on an **existing 32 m city segment**, longer controlled opposing-
traffic encounters, and a completed abort. Ordinary runs need not contain a pass.
Validity checks explicitly permit an active manoeuvre in the opposing lane while
checking its full rectangle stays inside the road envelope. Other unexplained
temporary paths/off-road positions remain invalid.

## Incidents, heatmaps and metrics retained

Physical contacts create incidents with stable IDs, start/location, involved
IDs/types/profiles, recent actions/signals and scheduled/actual clearance. A
connected simultaneous pile-up is one incident. Later contact with an active wreck
joins it; stationary contact is not counted again. Separate origins retain their
history if a later bridge links them. Clearance defaults to 45 simulated seconds
after last contact, pauses with simulation time, and removes wrecks without
counting their trips as completed. Replacement demand uses safe admission.

Road usage counts each directed-lane entry once per route occurrence, including
initial partial traversals, excluding connectors. Accident cells count each
incident origin once in fixed 16x16 m cells, surviving clearance. Both accumulate
since reset. Shared colour bins remain 0 / 1-24 / 25-49 / 50+ lane entries and
0 / 1-2 / 3-4 / 5+ incident origins. Zero accident cells are transparent.

Distance is actual vehicle-centre travel in vehicle-km. Waiting is speed below
0.05 m/s, including red lights and wreck time, excluding separately counted bus
dwell. Waiting fraction divides by all active vehicle-seconds including dwell.
Mean speed is a current snapshot including stopped/wrecked vehicles. Incident
rate is accidents * 1000 / vehicle-km, with N/A at zero exposure. Involved counts
unique vehicle IDs since reset; active population includes wrecks until clearance.

## Reproducible validation and exports

```powershell
& '..\.venv\Scripts\python.exe' -m unittest discover -s tests -v
& '..\.venv\Scripts\python.exe' -m traffic.behaviour_experiments --seeds 42 43 44 --duration 300
& '..\.venv\Scripts\python.exe' main.py --smoke-behaviour
& '..\.venv\Scripts\python.exe' main.py --smoke-m4
```

The matrix command runs all three scenarios, fixed target 40, green 30 s, no local
overrides. It also accepts `--green`, `--population`, `--mode` and `--output`.
`results.csv` and per-run JSON files include actual admitted profiles/traits,
trips, distance, risky decisions by type, execution/conflicting-exposure evidence,
overtaking assessments/attempts/completions/aborts, incidents and safety corrections.
`summary.json` reports means and ranges. Event logs flag whether the involved
vehicle contacted within two seconds of a recorded risk command; this is temporal
association, not a claim of fault or unique causation.

Signal/unsafe-entry events deduplicate per driver/route occurrence. Acceleration,
surge and late-braking commands deduplicate per behaviour episode. Late-braking
risk counts require a moving vehicle and actual forward clearance below its
maximum-braking stopping distance; normal red-light stops/creeping are excluded.
A conflicting exposure means a current stopping-distance deficit or occupied
junction/exit when the decision is proposed. An executed event requires positive
travel under the command; late entries are measured after physical entry.

Stable traits use seeded creation draws; subsequent driver-parameter draws use
seed+7919 independently of demand/routing. Each vehicle's episode/opportunity
stream is seeded with seed*1000003+ID. Rendering never consumes simulation RNG.
Same seed/configuration reproduces motion and incident logs. Different traffic
still changes admissions/exposure; before/after mixed runs are not identical
populations because personality sampling and behaviour have changed.

**43 tests pass**, preserving the original 30. Added checks cover stable subgroup
weights, one decision per red approach, holding position at red, late/insufficient braking, newbie overshoot,
signal-crossing contact, safe and misjudged overtaking, actual-city passing,
abort return, repeatability and the angular-contact regression. Existing tests
retain near misses, repeated-contact deduplication, signal timing, safe spawning,
clearance, reset, population controls and original geometry constraints.

The GUI was checked in accident mode with the required personality/perception
fields, and during an actual-city lateral path and completed return. Screenshots:
`artifacts/driver-revision-inspector.png`, `driver-revision-pass.png`, and
`driver-revision-return.png`. The existing incident/overlay/resize smoke also passed.
No appearance polish was performed. Physical mouse interactions remain manual.

## Recorded revised runs

All runs: 300 simulated seconds, seeds 42/43/44, target 40, green 30 s,
accident mode, clearance 45 s, no local overrides. Counts below include **actual
admissions**, not unentered demand or the requested mixture.

| Scenario / seed | Admitted Normal / Newbie / Drunk | Trips | Vehicle-km | Accidents / involved | Safety corrections | Pass attempts / completions / aborts |
| --- | --- | --- | --- | --- | --- | --- |
| Baseline / 42 | 79 / 0 / 0 | 51 | 12.73 | 0 / 0 | 25 | 0 / 0 / 0 |
| Baseline / 43 | 101 / 0 / 0 | 65 | 15.17 | 0 / 0 | 22 | 0 / 0 / 0 |
| Baseline / 44 | 90 / 0 / 0 | 65 | 15.33 | 0 / 0 | 25 | 0 / 0 / 0 |
| Morning commute / 42 | 56 / 11 / 8 | 41 | 9.43 | 10 / 20 | 12 | 0 / 0 / 0 |
| Morning commute / 43 | 57 / 15 / 3 | 39 | 10.08 | 7 / 15 | 15 | 0 / 0 / 0 |
| Morning commute / 44 | 55 / 23 / 9 | 43 | 10.28 | 11 / 24 | 5 | 0 / 0 / 0 |
| Evening/night / 42 | 62 / 16 / 13 | 53 | 13.78 | 8 / 17 | 11 | 0 / 0 / 0 |
| Evening/night / 43 | 61 / 17 / 10 | 39 | 12.17 | 13 / 27 | 7 | 0 / 0 / 0 |
| Evening/night / 44 | 60 / 18 / 16 | 53 | 13.37 | 11 / 24 | 7 | 0 / 0 / 0 |

All nine runs had **zero invalid positions and zero interpenetrations**. Normal
runs matched the unchanged audit exactly for admissions, trips, distance and
interventions. Morning accidents ranged 7-11 and night 8-13. These are illustrative
outcomes, not validation of real crash rates or a target accident count.

Risk command totals across the three seeds in each mixed scenario:

| Scenario / command | Decisions | Executed with motion | Encountered conflicting exposure | Associated with contact within 2 s |
| --- | --- | --- | --- | --- |
| Morning commute / acceleration_overshoot | 83 | 83 | 37 | 14 |
| Morning commute / late_braking | 88 | 88 | 88 | 26 |
| Morning commute / late_signal_entry | 4 | 4 | 1 | 0 |
| Morning commute / signal_violation | 4 | 4 | 4 | 2 |
| Morning commute / speed_surge | 2 | 2 | 2 | 2 |
| Morning commute / unsafe_gap_accepted | 11 | 11 | 11 | 7 |
| Evening/night / acceleration_overshoot | 81 | 81 | 34 | 10 |
| Evening/night / late_braking | 97 | 97 | 97 | 28 |
| Evening/night / late_signal_entry | 6 | 6 | 1 | 0 |
| Evening/night / signal_violation | 8 | 8 | 6 | 4 |
| Evening/night / speed_surge | 34 | 34 | 15 | 9 |
| Evening/night / unsafe_gap_accepted | 13 | 13 | 11 | 9 |

Risk commands demonstrably reached motion and encountered other traffic. Several
commands can precede one incident, so the last column must not be summed as an
accident count or used to assign fault. Normal-driver risk command counts were zero.
Late signal entries count conflicting exposure only when another committed
vehicle occupies a conflicting junction path.

No natural overtaking assessments or attempts occurred in these nine short-city
runs. This is reported as zero, not replaced by the deterministic fixture results.
The narrow geometry/speed/encounter requirements limit opportunities; overtaking
is supported and tested, but these ordinary runs do not establish its frequency.
Safe passing on a current city segment, an abort, and an oncoming collision were
demonstrated separately in constructed tests. There was no tuning to force a
natural pass or any desired accident ranking.

Full per-run counts, individual traits, temporal action evidence and incident
logs are in `artifacts/driver-revision/`. The pre-change nine-run audit is
`artifacts/behaviour-before.json`.


## Assumptions and limits

These project weights and reaction/braking models are not calibrated traffic
safety statistics. Zero accidents do not validate a model; more accidents do not
prove it better. Individual traits do not determine legal fault. There is no
rigid-body deformation, injury model, articulated vehicle, route diversion,
parking manoeuvre, tow-truck service, pedestrian simulation or empirical optimum.
Road curves remain densely sampled polylines. Normal traffic deliberately retains
conservative instantaneous safety corrections as the regression reference.

Contextual curb demand, adult/driving-age school trips, the three-bus fleet with
8 s stops, 14 signals, two roundabouts and their existing parameters remain.
For archived Milestone 4 controls/definitions and timing comparison see
[docs/milestone4.md](milestone4.md); Milestone 3 details are in
[docs/milestone3.md](milestone3.md). Those results predate this revision.

Main modules: `profiles.py`/`parameters.json` (traits), `behaviour.py` (perception,
opportunities and audit), `rules.pl`/`prolog.py` (behaviour selection),
`overtaking.py` (state and explicit paths), `simulation.py` (physical execution),
`collisions.py`/`incidents.py` (contacts/lifecycle), and the existing renderer/UI.
