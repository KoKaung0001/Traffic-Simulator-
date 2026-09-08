# Compact city: capacity and natural manoeuvre verification

Recorded 2026-09-08. The 128 m block enlargement was rejected and is superseded. All final results use the restored compact centre with an outer belt and ordinary demand. Settings are illustrative, not calibrated traffic or impairment statistics.

## Geometry review and restoration

There is no Git repository in this workspace, so the review used the edited source and the original geometry constants, plus the supplied screenshot. The enlargement changed `network.block_spacing` from 64 to 128, moved the grid from ?96/?32 to ?192/?64, moved building centres from ?64/0 to ?128/0, and scaled Home camera FOV by map extent. Pavement plots and buildings retained their old dimensions; this mismatch caused the oversized grass areas.

The central nine blocks now retain their original 64 m spacing, 48 m pavement plots, 31 m lawns, 9 m building footprints and 10 m roofs. Central junction positions, central lane endpoints, building offsets and the Home framing formula are restored. The original two roundabouts and central signal geometry remain. Changes are confined to the affected geometry/rendering paths; admission, behaviour, cleanup, collision and lighting work is preserved.

The outer belt lies at ?160 m, one 64 m strip outside the old central boundary. Eight new junctions connect its corners and four radial approaches. The four external gate stubs extend to ?224 m. Sixteen frontage plots use the same proportions as the centre. Four marked frontage accesses serve belt homes, offices, pub and shops; four gates and exits provide external trips. These are connected directed lanes and valid routes, not extra disconnected spawn tracks.

The full network has 80 directed lanes, 4,160 lane-metres and 24 junctions. A nominal stationary sedan estimate is 408 slots, calculated as the sum of `floor((lane_length - 2)/8.9)`. This ignores moving headways, bus/truck mix, connector storage, turning conflicts and uneven queues; it is not a flowing-population guarantee. Peripheral straights have 96 or 160 m usable lane length while the central straight lengths stay 24?32 m.

Home keeps the original centre framing; zooming out shows the belt. Pan bounds, ground bounds and lamp coverage extend outward. [Compact centre](../artifacts/compact-centre-detail.png) and [outer belt](../artifacts/compact-outer-belt.png) were rendered and inspected. Results under `artifacts/expanded-rejected/` describe the discarded enlarged layout and do not establish acceptance for this one.

## Demand, admission and actual capacity limitation

The original compact network had 1,856 lane-metres, a nominal 168 stationary sedan slots, seven curb origins and four unused external approaches. The measured limitation was local entry storage and queue/admission throughput under that demand distribution, not a hidden 40-car quota or a demonstrated global inability to physically store 100 sedans.

Software restrictions were addressed first. Incoming reservations formerly blocked an entire exit lane regardless of approach distance. Spawning now accounts for actual route distance, reaction and stopping clearance, while retaining physical overlap and spacing checks. On the compact seed-42 probe, reservation rejections fell from 14,825 to 1,555, but entry-spacing and occupancy rejections remained dominant. Its peak rose from 45 to 49; that correction alone did not meet the target.

New ticket weights account for the number already pending at each origin. Existing tickets retain origin, identity and traits. Blocked tickets rotate fairly so one unavailable entry cannot block all other admissions. Four gates were then enabled on the original compact roads, before adding any belt geometry.

| Normal probe | Duration | Replacement admissions | Completed trips | Peak / final active |
| --- | --- | --- | --- | --- |
| Compact, original veto | 180 s | 42 (0.233/s) | 37 (0.206/s) | 45 / 45 |
| Compact, corrected reservation check | 180 s | 42 (0.233/s) | 34 (0.189/s) | 49 / 48 |
| Compact, corrected admission plus four gates | 360 s | 93 (0.258/s) | 46 (0.128/s) | 89 / 87 |
| Compact centre + belt, gates only | 600 s | 238 (0.397/s) | 187 (0.312/s) | 95 / 91 |

Probe evidence: [original compact](../artifacts/capacity-funnel-before.json), [reservation correction](../artifacts/capacity-software-fix.json), [compact with gates](../artifacts/compact-gates-probe.json), [belt before frontage accesses](../artifacts/peripheral-four-gates-before.json).

The compact-with-gates run still had 13 pending tickets after six minutes. Its repeated blockers were entry spacing 29,112, occupied entry 25,417, approaching traffic 14,561 and incoming reservation 807; no stale reservation was found in ten-second samples. Admissions occurred at all 11 origins, but some requests waited the full run. Its final minute had no completions or admissions, consistent with congestion rather than missing demand.

The belt with only four gates completed many more trips and did not freeze, but still peaked at 95 after ten minutes. It had nine pending requests at the cutoff, with zero invalid geometry/interpenetrations and zero stale reservation samples. Adding storage without sufficiently distributed usable accesses was still inadequate. Four independent belt frontage accesses then made existing belt storage usable. Their night pub traffic also reaches a suitable straight naturally, rather than being confined to short central streets.

Demand fills the target deficit, with up to 30 route/type draws per ticket and at most four admissions every 0.1 s (40/s theoretical ceiling). The three-bus cap is separate. The gates-only belt run hit the per-tick ceiling just seven times in 600 s; physical entry blocks accounted for 78,430 checks. Sampled queues filled the active deficit. Generation/admission caps therefore did not explain the shortfall. Route failures retry; no pending request is counted as active.

Counts of blockers are repeated checks at 10 Hz per ticket, not unique vehicles or independent arrival probabilities. Fair retry does not guarantee bounded waiting at a blocked origin. The longest admitted waits were 257.3 s in the compact-with-gates probe and 376.8 s with belt gates alone.

No stale reservation was found in sampled runs. Occupancy and reservation processing derive from the active registry; existing regressions cover cleanup and cars traversing cleared sites. This is evidence for tested runs, not a proof against every stale-state bug. No vehicle is kept beyond valid trip completion to inflate occupancy. Active remains live on-road vehicles plus uncleared wrecks.

## Behaviour eligibility and scheduling

The compact night audit admitted 12 drunk drivers, ten higher-risk, and observed 11 higher-risk sedan lane encounters. All encountered insufficient remaining length at some point, seven encountered whole-road access exclusions and seven failed the old slow-leader filter. There was one eligible wrong-way encounter and no eligible overtake. Short central streets and the 0.4 s assessment made the original 28 m plan difficult to execute.

Manoeuvres now use clear peripheral sections. Access/bus-stop protection remains 14 m either side, mirrored into both directions, but excludes local sections rather than an entire long road. Both shifts and the return must fit within one clear section. An assessment already underway checks the remaining shift/return requirement rather than restarting the original full-length requirement after its delay. Overtaking considers moving leaders from 0.5?10 m/s, at least 2 m/s desired advantage and centre distance below 30 m. Junctions, roundabouts and portal roads remain excluded.

Personality weights and willingness remain unchanged: drunk drivers are sampled 75% higher-risk / 25% less aggressive, with passing willingness 0.50 and wrong-way willingness 0.18 for eligible higher-risk sedans. The belt pub uses the existing pub's illustrative night mix, including 35% drunk drivers; its demand follows the same clock weighting. Other belt activities generate varied traffic. Configurable settings are in `traffic/parameters.json`.

Lotteries are cached per meaningful encounter: driver/route occurrence/leader for passing, driver/route occurrence for wrong-way. Consumed opportunities cannot restart an attempt. Overtaking retains ownership of an assessment or manoeuvre before wrong-way is considered. Delayed/biased perception feeds Prolog transitions; installed-path and executed-motion counters show whether a selected decision actually moved. No fixed-time action, forced actor, per-frame reroll, removed oncoming traffic or disabled collision check is used.

An ordinary seed-42 path trace records driver 84 selecting wrong-way at 10.917 s and overtaking at 25.017 s, both on the peripheral straight `rSE>re`. It completed both returns without being constructed or repositioned: [path trace](../artifacts/peripheral-manoeuvre-paths.json). The GUI independently captured this driver in the opposing lane at 12.517 s: [night capture](../artifacts/compact-natural-wrong-way.png).

## Final ordinary-run measurements

Final tables follow the completed acceptance exports in `artifacts/capacity-final/`. All runs use ordinary initial distribution of 40 vehicles, target 100, accident mode, 30 s green and 45 s clearance. Baseline starts at noon; night starts at 21:00. The Normal run lasts 360 s, and each night seed lasts 180 s. Geometry and independent rectangle interpenetration are checked every 1/60 s step. Contact incidents are valid; significant interpenetration is not.

**Ordinary Normal seed 42 reached 100 active vehicles at 95.317 simulated seconds.** At first reaching 100 it had completed 21 valid trips; the full six-minute run completed 94, admitted 192 in total and ended with 98 active plus two pending. There were zero incidents, invalid positions or interpenetrations. Replacement admissions were 152 / 360 = 0.422/s versus 94 / 360 = 0.261 completed trips/s. Valid trip completion continued after reaching 100.

All 15 origins admitted replacement vehicles. The final Normal run recorded 9,794 occupied-entry checks, 3,691 entry-spacing blocks, 2,008 approaching-traffic blocks, 97 incoming-reservation blocks, 38 tick-limit blocks and 152 admissions. Its longest admitted wait was 97.4 s; the oldest still-pending ticket at the cutoff was 158.3 s. Physical retry checks remained frequent despite reaching the target.

| Run | Admitted Normal / Newbie / Drunk | Higher / lower risk drunk | Peak / final active | Live / wrecks at end | Trips | Incidents / involved |
| --- | --- | --- | --- | --- | --- | --- |
| Normal 42 (360 s) | 192 / 0 / 0 | 0 / 0 | 100 / 98 | 98 / 0 | 94 | 0 / 0 |
| Night 42 (180 s) | 128 / 27 / 25 | 20 / 5 | 95 / 94 | 88 / 6 | 38 | 25 / 54 |
| Night 43 (180 s) | 126 / 25 / 8 | 4 / 4 | 99 / 99 | 97 / 2 | 39 | 11 / 23 |
| Night 44 (180 s) | 128 / 28 / 21 | 17 / 4 | 96 / 96 | 86 / 10 | 40 | 22 / 51 |

Admitted counts include the initial distribution and actual subsequent entries, never pending tickets. Newbie cautious/unsteady admissions were 17/10, 20/5 and 17/11 for night seeds 42, 43 and 44.

| Night seed | Replacement admission rate | Trip-completion rate | Crash removals | Longest admitted wait | Oldest pending at end |
| --- | --- | --- | --- | --- | --- |
| 42 | 0.778/s | 0.211/s | 48 | 176.1 s | 60.3 s |
| 43 | 0.661/s | 0.217/s | 21 | 173.8 s | 6.2 s |
| 44 | 0.761/s | 0.222/s | 41 | 112.3 s | 180.0 s |

Night throughput is reported separately because collisions and clearance change both active population and available entrances. All ten-second reservation samples in all four final runs had zero stale reservations.

| Funnel stage | Pass 42 | WW 42 | Pass 43 | WW 43 | Pass 44 | WW 44 |
| --- | --- | --- | --- | --- | --- | --- |
| Drunk route encounters, including connectors | 44 | 44 | 10 | 10 | 29 | 29 |
| Higher-risk sedan lane encounters | 20 | 20 | 5 | 5 | 20 | 20 |
| Eligible encounters | 1 | 8 | 0 | 4 | 3 | 13 |
| Decision opportunities | 1 | 8 | 0 | 4 | 3 | 13 |
| Personality declines | 0 | 5 | 0 | 4 | 2 | 11 |
| Selected assessments | 1 | 3 | 0 | 0 | 1 | 2 |
| Assessment subsequently declined | 0 | 0 | 0 | 0 | 1 | 0 |
| Attempts / installed paths | 1 | 3 | 0 | 0 | 0 | 2 |
| Physically executed motion | 1 | 3 | 0 | 0 | 0 | 2 |
| Completed return | 1 | 1 | 0 | 0 | 0 | 0 |
| Manoeuvring actors in contact | 0 | 1 | 0 | 0 | 0 | 2 |

Eligible encounters are observed before ownership/consumed-opportunity guards, so they need not equal actual decision opportunities. Encounter counters deduplicate per vehicle/route occurrence; passing opportunities additionally distinguish leaders. Rejections overlap, can occur after earlier eligibility, and are not a sequential partition. The current runs' installed-path counts match the separate attempt counters. Contact counts describe manoeuvring actors, not fault or necessarily unique incident origins.

| Rejection | Pass 42 | WW 42 | Pass 43 | WW 43 | Pass 44 | WW 44 |
| --- | --- | --- | --- | --- | --- | --- |
| connector | 5 | 5 | 1 | 1 | 3 | 3 |
| crashed | 15 | 15 | 4 | 4 | 17 | 17 |
| entry reservation | 0 | 8 | 0 | 2 | 0 | 5 |
| leader distance | 10 | 0 | 3 | 0 | 12 | 0 |
| leader speed | 15 | 0 | 5 | 0 | 15 | 0 |
| no leader | 4 | 0 | 0 | 0 | 0 | 0 |
| own speed | 18 | 16 | 5 | 4 | 17 | 17 |
| personality | 9 | 9 | 4 | 4 | 6 | 6 |
| protected zone | 16 | 16 | 3 | 3 | 16 | 16 |
| remaining length | 17 | 17 | 4 | 4 | 10 | 10 |
| speed advantage | 4 | 0 | 1 | 0 | 4 | 0 |
| vehicle type | 10 | 10 | 0 | 0 | 0 | 0 |
| wreck leader | 1 | 0 | 0 | 0 | 6 | 0 |

Seed 42 completed one overtake and executed three sustained wrong-way episodes: one returned, one collided and one remained unfinished at 180 s. Seed 43 had no passing opportunity and declined all four wrong-way opportunities. Seed 44 executed two sustained wrong-way episodes, both colliding; its selected overtake assessment was declined before departure. Thus all-seed totals are one executed/completed overtake, five executed wrong-way manoeuvres, one wrong-way completion and three wrong-way actors involved in contact. One wrong-way manoeuvre remained unfinished at the cutoff. There is no promise of both behaviours in every short seed.

Exact settings, admitted traits, per-origin checks, removals, incidents and complete funnels: [Normal 42](../artifacts/capacity-final/baseline-42-100.json), [night 42](../artifacts/capacity-final/evening-night-42-100.json), [night 43](../artifacts/capacity-final/evening-night-43-100.json), [night 44](../artifacts/capacity-final/evening-night-44-100.json).

## Verification and remaining tradeoffs

**All 59 regression tests passed**, including all 52 existing tests and seven new capacity/funnel tests: [test log](../artifacts/capacity-final/regression-tests.txt). The tests cover preserved central geometry and connected gate routing, safe reservation-aware admission, local access protection, observational instrumentation, ordinary Normal population 100, ordinary overtaking completion and ordinary sustained wrong-way return. The protected-zone test fixture was corrected to isolate its synthetic access from the newly added real frontage; production protection was retained.

The GUI also passed on the final layout: [100 Normal vehicles](../artifacts/compact-normal-100.png), [natural belt wrong-way driver](../artifacts/compact-natural-wrong-way.png), [GUI observations](../artifacts/capacity-final/gui.json). There are 158 street/block lamp fixtures. The captures use accelerated ordinary fixed steps, without inserted actors, changed probabilities or simulated trip retention.

The additional road capacity is outside the centre, so the overall footprint and number of junctions/plots increase. This is a belt-road solution, not a claim that the unchanged original network now sustains 100. It preserves the central nine blocks' proportions and supplies both distributed access and suitable straight sections. These experiments establish the observed admission bottleneck and a working remedy, not a mathematically minimal expansion.

Reaching 100 does not mean maintaining exactly 100 at every instant or for every seed, signal timing or compact-only configuration. Long entry waits remain, especially behind crashes. The belt changes trip distances and destinations; routing still minimizes junction hops using randomized BFS rather than travel time. Earlier milestone rates are therefore not directly comparable. Three short night seeds demonstrate reachability and variation, not reliable per-run frequency or real-world calibration. Opposing-lane manoeuvres can remain stopped or unfinished when return is blocked; no timeout teleports actors or removes oncoming traffic to manufacture a completion.
