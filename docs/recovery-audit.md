# Removal and admission audit

Before feature changes, seed 42, accident mode, initial 30, target raised to 100,
120 simulated seconds in Baseline and Evening/night reproduced the population
symptom. Baseline varied between 30 and 41 at the ten-second samples and ended
with 38 active, 62 waiting requests and 66 total admissions. Night ended with 33
active, 66 queued requests, one unfilled demand slot and 59 total admissions.
The original admission mechanism was operating, but only seven curb entrances
served all replacement traffic. Concentrated origin weights, safe stopping gaps
and incoming reservations limited throughput. There was no original-population
cap, and the three-bus fleet cap did not cap sedans or trucks. A requested target
is not guaranteed physical capacity on this compact road network.

The before-change trace is `artifacts/recovery-before.json`. All 28 baseline
removals were destination arrivals. Night removals were 19 destination arrivals
and seven incident members. No unrelated removal by an expired crash location
was reproduced. The implementation had no location-based deletion or scheduled
rendering cleanup callback. Rendering destroys only IDs absent from the active
registry; collision hash buckets and reservations are rebuilt from that registry.

A separate confirmed edge case existed: the route-advance loop could finish a
crashed vehicle at the endpoint. It now excludes wrecks. The former inspector
also labelled every absent ID as a completed trip. It now shows the audited
reason, time and destination.

All exits from the active registry now pass through `remove_vehicles`, which
records ID, time, reason, incident, path, position and destination once. Trip
completion increments completed trips once. Lower targets drain through normal
trip completions, without arbitrarily deleting on-road cars. Reset begins a new
run and resets its logs and IDs; it is not a completed trip or crash clearance.

Clearance iterates only active incident IDs and requires a still-crashed vehicle
with matching incident ID AND explicit membership. Each due record is finalized
once and removed from the active-ID set. History, heatmap cells and involved IDs
remain. A new contact joins an active incident explicitly and extends its timer;
linked existing incidents retain their own membership and history.

Demand reconciles active plus queued vehicles against the current target.
Blocked tickets keep their traits and rotate fairly between retries. The setup
panel reports pending demand, tickets, entry occupancy/reservation/approach
blocks, and whether resuming, waiting for clearance or lowering the target is
appropriate. Active means all admitted on-road vehicles, including wrecks;
the header separates live on-road vehicles and wrecks. No unsafe extra spawn
points or weakened spacing checks were introduced to make the counter reach 100.
