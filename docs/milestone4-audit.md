# Safety intervention audit

Before changing movement, an instrumented copy of the Milestone 3 simulation
ran Baseline, seed 42, target 40, global green 30 seconds, for 600 simulated
seconds. Logging wrapped `SafetySupervisor.record` without changing decisions.
It reproduced **134 completions and exactly 50 interventions**.
Full event records: `artifacts/safety-audit-m4-before.json` (time, vehicle ID,
directed approach, world position, cause, proposal, reason and speed).

| Cause | Count | Proposal / reason | Classification and response |
| --- | ---: | --- | --- |
| Reserved conflict | 32 | proceed / roundabout_gap | Conflicting entry proposals from delayed observations; conservative current reservation correction. Retain for compliant entry. |
| Reserved conflict | 13 | proceed / green_and_clear | Conflicting junction/merge proposals, including reservations acquired since the driver's observation. Retain current-state arbitration. |
| Blocked exit | 4 | proceed / green_and_clear | Exit room changed since the delayed observation. Expected current-state safety correction; retain for compliant entry. |
| Stale signal response | 1 | proceed / amber_committed | Driver still responding to an amber observation after the light became red. Retain current-red entry check. |
| Physical following gap | 0 | — | No following/braking defect detected by this audit. |
| Physical overlap prevention | 0 | — | No geometry/timestep overlap correction detected by this audit. |

All 50 proposals were `proceed`. These are unique corrections per vehicle, route
occurrence and cause, not 50 independent imminent physical crashes. Whole-path
reservation envelopes are conservative: a reservation conflict does not establish
that the two moving rectangles would contact.

| Junction | Reserved conflict | Blocked exit | Stale signal | Total |
| --- | ---: | ---: | ---: | ---: |
| 11 (roundabout) | 20 | 0 | 0 | 20 |
| 22 (roundabout) | 12 | 0 | 0 | 12 |
| 12 | 4 | 0 | 1 | 5 |
| 32 | 4 | 0 | 0 | 4 |
| 00 | 0 | 2 | 0 | 2 |
| 10 | 0 | 2 | 0 | 2 |
| 23 | 2 | 0 | 0 | 2 |
| 21 | 1 | 0 | 0 | 1 |
| 31 | 1 | 0 | 0 | 1 |
| 02 | 1 | 0 | 0 | 1 |

No baseline defect requiring a geometry or braking change was identified. The
50 corrections were therefore not removed merely to produce accidents. The
diagnostic supervisor and safe admission remain. Accident mode permits only
explicit `signal_violation` / `unsafe_gap_accepted` entry proposals to bypass
reservation/exit compliance; unsafe-gap execution may also bypass longitudinal
gap caps. Actual swept contact then determines the incident.

The Milestone 3 midpoint/end prevention routine remains available for diagnostics.
The accident engine instead splits motion at every polyline vertex and route
boundary and performs continuous swept SAT within each interval, removing the
sampling/tunnelling limitation. Spatial hashing selects candidate pairs. Normal
drivers also perceive wrecks on crossing paths through geometric lookahead.

The new separate driver-parameter RNG changes subsequent demand evolution relative
to Milestone 3. A fresh 600-second Baseline run in each new mode completed 117
trips, with 50 current-state corrections, zero accidents, and identical distance
and waiting metrics. This is a regression comparison between the two new modes;
the historical 134-trip result above is retained separately, not overwritten.
