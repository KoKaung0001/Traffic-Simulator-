# Four-lane verification results

Measured 8-9 September 2026. These results describe the default compact four-lane network with its peripheral belt. Historical two-lane reports are separate.

## Ordinary traffic

Each run uses ordinary demand, seed-based personalities and 1/60 s physics with independent footprint/interpenetration checks every step. Target 100; accident mode; 30 s green; 45 s incident clearance; duration 240 simulated seconds. No constructed manoeuvre actors are injected into these runs.

Normal seed 42: first 100 at **48.92 s**; final 100 on-road vehicles; 50 completed trips; zero incidents, invalid positions or detected interpenetrations. Admitted 150; sampled stale reservations zero. The backlog comparison is retained in `artifacts/four-lane/normal-before-backlog.json`: 96 final active, 49 trips, zero incidents after 360 s.

The corrected demand backlog removes an artificial admission shortfall; it does not eliminate congestion. Final Normal mean speed was 0.38 m/s. Fourteen requests remained queued, including requests blocked for 240 s. These are not counted as active. Capacity is sufficient for 100, but short central storage, merge priorities, destination lanes and blocked exits limit circulation. No blocks were enlarged.

### Admitted mix and exposure

| Seed | Normal | Newbie (unsteady) | Drunk (higher risk) | Trips | Incidents | Final on-road + wrecks |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 42 | 125 | 30 (4) | 24 (16) | 42 | 18 | 94 + 6 |
| 43 | 126 | 23 (5) | 17 (12) | 34 | 19 | 91 + 9 |
| 44 | 142 | 34 (10) | 27 (22) | 46 | 30 | 93 + 7 |

Counts include the initial admitted population and replacement admissions, not merely the surviving driver mix at the end. Every night run reached 100 active; wrecks legitimately remain active until clearance. Crashes temporarily reduce moving throughput.

### Manoeuvre lifecycles

| Seed | All lane-change opportunities | Lane changes attempted / completed | Pass opportunities / attempts / completions | Pass aborts before / after departure | Return opportunities / attempts / completions |
| --- | ---: | --- | --- | --- | --- |
| 42 | 96 | 78 / 76 | 10 / 4 / 2 | 2 / 1 | 1 / 1 / 1 |
| 43 | 114 | 81 / 81 | 10 / 2 / 1 | 0 / 0 | 3 / 2 / 2 |
| 44 | 121 | 83 / 82 | 11 / 2 / 1 | 0 / 1 | 0 / 0 / 0 |

A lane change completes when its continuous lateral path ends. A pass completes only after the actor physically clears its leader by the required gap. An actor can complete the lateral change but fail to pass before routes diverge. Rejected gaps are not attempts. Seed 42 also had two passing decisions cancelled because the target lane offered no legal destination route. Planned pre-departure cancellations were 2, 1 and 2 respectively. Some manoeuvres remain in progress at the observation cutoff; completion/abort/contact counts need not sum to opportunities.

| Seed | Wrong-way opportunities / attempts / returns | First lane change / pass / wrong-way (s) | Contacts during pass / planned change / wrong-way |
| --- | --- | --- | --- |
| 42 | 6 / 0 / 0 | 2.88 / 13.28 / none | 0 / 0 / 0 |
| 43 | 4 / 1 / 0 | 3.27 / 12.98 / 52.90 | 1 / 0 / 1 |
| 44 | 3 / 0 / 0 | 3.68 / 10.17 / none | 0 / 1 / 0 |

**Wrong-way driving remains rare:** one attempt across these three ordinary runs, in seed 43 at 52.90 s, sustained at approximately 55.4 s and involved in contact at 62.10 s. Seeds 42 and 44 selected none. No ordinary wrong-way return was observed; return geometry and safety are covered by focused tests. Completed passing occurs in all three seeds. Contacts after an already completed passing episode are not attributed indefinitely to that manoeuvre. Counts describe association, not fault.

### Wrong-way eligibility funnel

| Seed | Drunk route encounters | Higher-risk sedan lane encounters | Wrong lane rejection | Insufficient remaining room | Access rejection | Eligible encounters | Declined / selected / executed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 42 | 88 | 41 | 26 | 23 | 17 | 6 | 6 / 0 / 0 |
| 43 | 79 | 35 | 20 | 25 | 5 | 4 | 3 / 1 / 1 |
| 44 | 95 | 39 | 29 | 28 | 18 | 3 | 3 / 0 / 0 |

Funnel counts are once per actor/route occurrence; rejection reasons overlap. The exported funnel also includes personality, vehicle-type and connector exclusions. Inner-lane eligibility, short protected central streets and available return room are the dominant geometric restrictions. The long peripheral corridor makes the behaviour reachable without altering the compact blocks. Seeded willingness is assessed once per encounter, not rerolled while waiting.

## Collision credibility

The new audit reproduced a Normal contact at 112.88 s in the earlier implementation: an outer-destination roundabout connector failed to see a stopped inner-destination car in their still-shared departure. The corrected index shares that occupancy until the split clears; the dedicated regression and the 240 s Normal run pass. A 12 m taper also allowed a bus corner to exceed the 14 m road envelope by about 14 mm; replacing it with a 16 m taper corrected the geometry without shrinking the vehicle or relaxing the envelope check.

Ordinary straight-road contacts have bounded pre-histories. Examples immediately before contact:

| Seed / incident | Driver speed | Actual gap | Perceived gap | Recorded control |
| --- | ---: | ---: | ---: | --- |
| 42 / 1 | 4.54 m/s | 0.29 m | 7.38 m | late_braking |
| 43 / 1 | 5.34 m/s | 0.10 m | 9.88 m | late_braking |
| 44 / 1 | 6.13 m/s | 0.02 m | 8.92 m | late_braking |

These traces are consistent with delayed/insufficient braking into a stationary leader. They do not establish blame for every participant. The audit also checks lane-specific neighbours, refreshed occupancy, safe admission, continuous route joins, actual vehicle dimensions and bounded acceleration/braking. Separate focused cases retain unsafe lane-change, wrong-way, delayed-braking and junction contact, pile-up deduplication, incident-only clearance and population recovery.

## Real-window performance

1440 x 900, Windows 11 build 26200, Intel Core i9-13900HX, **NVIDIA GeForce RTX 4060 Laptop GPU**, OpenGL NVIDIA driver 592.82. VSync disabled, uncapped. Each case records eight wall-clock seconds after ordinary safe admission and a settling interval. The same warmed target state is reused for comparable camera/lighting cases. Actual populations were exactly 40 or 100 throughout these measurement intervals; no collisions occurred. Day/night performance cases use Normal traffic to isolate lighting costs; mixed-driver behaviour is measured above.

The reference configuration enables per-frame UI work, separate vehicle parts/bulbs and shadow rendering/sampling. The optimized configuration uses cached combined assets, rate-limited UI, stable light selection and performance lighting. Both use the completed four-lane physics, shared static geometry and collision checks. Thus this is a controlled rendering comparison, not a comparison against historical two-lane FPS.

| Lighting / population / view | Before median / p95 / p99 (ms) | Corrected after median / p95 / p99 (ms) | After median FPS |
| --- | --- | --- | ---: |
| Day / 40 / stationary | 23.56 / 26.34 / 27.42 | 9.71 / 13.82 / 15.92 | 103.0 |
| Day / 40 / pan + zoom | 25.48 / 28.26 / 29.41 | 11.09 / 15.38 / 18.01 | 90.1 |
| Day / 100 / stationary | 41.53 / 47.85 / 50.90 | 15.02 / 22.35 / 26.19 | 66.6 |
| Day / 100 / pan + zoom | 43.70 / 50.13 / 63.04 | 16.06 / 25.07 / 27.87 | 62.3 |
| Night / 40 / stationary | 29.72 / 32.55 / 33.77 | 10.32 / 14.62 / 17.80 | 96.9 |
| Night / 40 / pan + zoom | 31.67 / 35.52 / 39.44 | 11.51 / 15.98 / 18.69 | 86.9 |
| Night / 100 / stationary | 57.19 / 64.27 / 133.73 | 16.53 / 25.53 / 28.16 | 60.5 |
| Night / 100 / pan + zoom | 59.51 / 69.21 / 149.34 | 18.66 / 27.32 / 29.29 | 53.6 |

The 6.94 ms / 144 FPS target is **not met**. Earlier optimized results, including the approximately 67 FPS night-pan figure, are withdrawn because shared scene nodes left some vehicles invisible. The replacement after-results above verify 40/100 independently owned, visible body nodes for 40/100 active vehicles. Corrected night panning at 100 measures 18.66 ms median (53.6 FPS). The unoptimized reference used separately constructed models and was unaffected by this cache bug. See [the visibility investigation](visibility-regression.md).

Inclusive component timings for the 100-vehicle night pan:

| Component | Before median / p95 (ms) | Corrected after median / p95 (ms) |
| --- | --- | --- |
| simulation | 17.064 / 22.967 | 3.986 / 10.450 |
| prolog | 0.905 / 1.056 | 0.000 / 0.929 |
| collisions | 3.707 / 4.700 | 1.068 / 2.200 |
| render_submit | 28.970 / 31.430 | 8.253 / 11.767 |
| scene_sync | 3.223 / 3.716 | 1.251 / 1.430 |
| lighting | 0.997 / 1.154 | 0.099 / 0.257 |
| ui | 1.752 / 2.004 | 0.007 / 1.693 |
| heatmaps | 0.011 / 0.014 | 0.009 / 0.011 |

These costs are inclusive and must not be added: Prolog/collisions are inside simulation; lighting/heatmaps are inside scene sync. `render_submit` brackets Panda's draw task and can include GPU synchronization; it is not an independent GPU timer. Zero median Prolog cost means most render frames have no 10 Hz decision tick. Frame-time distributions include the work when those ticks occur.

Controlled shadow and active-overlay probes, also eight seconds per case at 100 active vehicles during pan/zoom:

| Probe | Median / p95 / p99 frame (ms) |
| --- | --- |
| Day / shadows on | 24.77 / 32.46 / 37.06 |
| Day / shadows off | 16.05 / 24.55 / 27.71 |
| Night / shadows on | 27.85 / 36.02 / 39.33 |
| Night / shadows off | 19.79 / 28.23 / 30.57 |
| Day / road usage overlay | 19.66 / 26.96 / 29.16 |
| Night / road usage overlay | 22.19 / 30.26 / 35.32 |

Shadow-off versus shadow-on is a controlled end-to-end cost comparison, not an additive isolated GPU estimate. In the active road-usage overlay probe, heatmap CPU p95 was approximately 2.3 ms versus approximately 0.01 ms while the overlay was off. Street illumination and moving headlight cones remain active in all night cases. Results are short samples from this laptop, not guarantees for other hardware or long thermally steady sessions.

## Tests and GUI inspection

**75 simulation tests passed**, including the historical 59 checks and 16 new four-lane checks. Coverage includes lane connectivity/policy, smooth changing and both-lane occupancy, relative-speed rear gaps, deterministic competing changes, safe passing/return, unsafe contact, truck/bus envelopes, merge ownership and shared departure queues, delayed braking, wrong-way crossing/return/contact, bus stop preservation during rerouting, demand backlog semantics, heatmap counts and observational interpolation.

The real GUI run reached 100 Normal vehicles at 48.92 s without contact. It observed an ordinary seed-42 pass at 13.3 s and a physically completed pass at 125.12 s, and seed-43 sustained wrong-way movement at 55.42 s. Follow cancellation and three seconds of live night pan were exercised. Extra rendering calls with both settings left vehicle state and RNG state unchanged.

Inspected captures: [compact layout](../artifacts/four-lane-compact-detail.png), [truck at a roundabout taper](../artifacts/four-lane-turn.png), [natural pass](../artifacts/four-lane-pass.png), [completed pass](../artifacts/four-lane-passed.png), [wrong-way](../artifacts/four-lane-wrong.png), [100 Normal vehicles](../artifacts/four-lane-normal.png). Explicitly labelled synthetic heatmap fixtures show [1 passage](../artifacts/four-lane-frequency-0.png), [25 passages](../artifacts/four-lane-frequency-1.png), [50 passages](../artifacts/four-lane-frequency-2.png), and [5 separate incident origins](../artifacts/four-lane-frequency-5.png). Counts were added through the passage/incident accounting APIs, not by changing display scale.

Raw evidence: `artifacts/four-lane/normal-100-seed42.json`, `night-100-seed42/43/44.json`, `frames-before.json`, `frames-after.json`, `shadows-after.json`, `heat-after.json`, `gui.json` and `storage.json`. Night exports include parameters, complete event lists, admitted traits, removals, usage and bounded pre-contact histories.

Fresh-process visibility verification additionally passed 12 type/day-night/zoom combinations, 432 ownership checks, duplicate hide/delete/reuse isolation, lateral/wrong-way alignment and exact crash/clearance transforms. [Visibility report](visibility-regression.md).

## Remaining limits

- Wrong-way travel is observable but rare; only one of the three night seeds attempted it. No ordinary return was observed in this sample.
- High population causes central congestion and potentially very long curb waits. Some boundary approach lanes cannot continue legally after a missed change and must wait for that change.
- Passing uses marked mid-road change zones on sufficiently long roads. It is not an unrestricted lane-changing model; central short streets deliberately remain protected.
- Night illumination is approximate, with no building occlusion and only eight selected dynamic headlight cones. Performance mode omits sun shadows.
- 144 FPS is not achieved on this measured laptop. Remaining rendering and simulation decision-frame costs limit both median FPS and smoothness.

