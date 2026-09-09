# Crossing City — Python + Prolog Traffic Lab

The default city now has **four actual lanes per ordinary road**: two in each direction, with right-hand traffic. The central nine blocks retain their 64 m spacing and original building scale. The outer belt provides longer passing corridors without stretching the centre.

## Run

From this project directory, using the existing parent virtual environment:

```powershell
& '..\.venv\Scripts\python.exe' main.py
& '..\.venv\Scripts\python.exe' main.py --population 100 --scenario Baseline
& '..\.venv\Scripts\python.exe' main.py --population 100 --scenario 'Evening/night' --seed 43
```

No dependencies were added. SWI-Prolog and `janus_swi` must be available in that interpreter. Defaults: target 40, Normal drivers at noon, accident mode, performance lighting, VSync off, frame limit 144. A frame limit is **not an achieved FPS claim**. Use `--fps 0` for uncapped measurement, `--vsync` for synchronized presentation, or `--lighting quality` for daytime sun shadows. Both lighting presets retain street illumination and eight nearby headlight cones. `--mode supervised` remains a conservative diagnostic mode. `--compact-only` removes the belt while retaining four-lane central roads; the measured capacity results below use the default belt.

| Control | Effect |
| --- | --- |
| Run setup | Scenario, mode, population, admitted mix and entry blockers |
| Pause / Space | Freeze simulation time, traffic, demand and clearance |
| Reset / R | Fresh run, target 40 and default 30 s green |
| Scenario / mode change | Fresh run retaining the population target |
| Click vehicle | Traits, actual/perceived gap, Prolog proposal, executed action, incident history |
| Click junction | Local green override; Use global removes it |
| Global green | 5–120 s, applied at the next green boundary |
| Road usage / Accidents | Lane passages / unique incident origins since reset |
| Scale /2, Scale x2 | Adjust fixed display thresholds; counts stay unchanged |
| Click coloured lane / cell | Exact count, direction or cell, and accumulation period |
| Manoeuvre feed | Select a passing, return or wrong-way event |
| Follow selected / latest | Follow the selected/event vehicle |
| Escape / Stop following / Home / manual pan or zoom | Cancel following |
| WASD / arrows / wheel | Pan and zoom every rendered frame |
| Home / H | Compact-centre framing |

## Geometry and movement policy

Each lane is 3.5 m wide; ordinary roads are 14 m wide. Inner centres lie 1.75 m from the centre line, outer centres 5.25 m. Double yellow separates opposing directions; dashed white separates lanes in the same direction. Vehicle dimensions remain sedan 4.4 × 1.8 m, truck 7.2 × 2.3 m and bus 9 × 2.3 m. Central junction coordinates remain `(-96, -32, 32, 96)`; plots remain 48 m across, lawns 31 m, building footprints 9 m and roofs 10 m. Roadside poles and stops are set back from the wider road. Terminal access moved to the adjacent depot road, and Apartments access moved off a roundabout taper.

The default graph has 40 two-way roads, 224 directed lane segments, 328 junction connectors and 32 continuous lane-change links. IDs identify road, direction, lane and segment. Short central streets have no lane-change link. Longer streets have entry, 20 m change zone and exit segments. Routes select the required approach lane upstream.

| Approach lane | Legal movement | Destination |
| --- | --- | --- |
| Inner | Straight | Inner |
| Outer | Straight | Outer |
| Inner | Left | Planned inner **or outer** lane, reserved before turning |
| Outer | Right | Outer |

The explicit left-turn destination choice permits curb destinations on short streets where a post-turn lane change cannot fit. Those alternative left-turn paths share a reservation conflict; vehicles cannot take both simultaneously. Opposing straight/right traffic has priority over left turns under the signal scheme. Signals, exit-space checks, rear clearance and global/local duration controls remain active.

Roundabouts are an exception: single-lane counterclockwise circulation. Both approach lanes physically converge through marked 16 m tapers, followed by 4 m of shared approach. A deterministic owner holds the other approach before the taper. Departures share one physical lane and split continuously over 16 m. Following queries include vehicles assigned to the other destination lane until they clear the shared departure. Either departure lane may be selected through this shared split.

If a required lane change is unavailable, routing searches for a legal forward alternative. At a boundary lane with **no legal forward exit**, the vehicle waits upstream and reassesses every two seconds; it cannot continue legally without that change. This is a remaining topology tradeoff, not permission to cut across a junction. Compact central queues and roundabout merges limit throughput even when total road storage is ample.

## Admission and capacity

The network contains approximately 8,324 directed lane-metres. A simple straight-road packing estimate gives 816 nominal sedan positions at 8.9 m spacing, **before** accounting for shared tapers, mixed vehicle lengths, junction clearance and moving headways. It is not an operational capacity guarantee.

The latest bottleneck was software demand generation: the request queue was capped to the active deficit. When only four vehicles were missing, four blocked curb requests could leave other entrances unused. Four-lane demand now maintains a bounded backlog of at least 15 tickets while below target, independent of the admission limit. Stable requests retain their traits and age; rotating retries examine all tickets, and at most four safely enter per 0.1 s admission tick. The active population never exceeds the target through admission. Existing reaction/stopping checks, nearby occupancy checks and reservation checks remain mandatory.

The comparison run with the deficit-sized queue ended at 96 active after 360 s, with 49 completed trips and zero incidents. With the backlog correction, ordinary **Normal seed 42 reached 100 at 48.92 s** and finished 240 s with **100 on-road vehicles, 50 completed trips, zero incidents and zero independently detected interpenetrations**. Sampled stale reservations were zero. No additional map enlargement was needed.

This is a congested 100-vehicle run, not free-flow traffic: the final mean speed was about 0.38 m/s, and some curb tickets waited the full four minutes. The admission correction uses clear entrances; it does not make a blocked curb physically usable or guarantee bounded waits. Mixed-night collisions and cleanup create additional temporary bottlenecks.

**Active = on-road vehicles + uncleared wrecks.** Pending demand is never active. The UI separately shows the population deficit and queued tickets. Valid trips still finish. Cleanup removes only due incident members. Lowering the population target lets existing trips drain normally.

## Drivers, passing and wrong-way travel

All numerical behaviour assumptions in `traffic/parameters.json` are configurable and **illustrative, not calibrated traffic statistics**. Personalities stay fixed; decisions use per-vehicle seeded randomness. Drunk drivers retain a 75% higher-risk / 25% less-aggressive split; newbies retain a 70% cautious / 30% unsteady split. Admission weights vary by scenario and origin.

Normal drivers prefer the outer lane when useful, use the inner lane to pass a slower moving leader, and return when the next movement and gaps permit. Planned turns, queues and bus service take priority. Lane changes use a smooth quintic lateral path, front and rear stopping/reaction gaps, both-lane occupancy, deterministic competing claims, and a final gap check before departure. A six-second cooldown limits repeated switching. Access protection and roundabout tapers exclude opportunistic changes.

Higher-risk drunk drivers can accept smaller biased gaps, accelerate within vehicle limits, follow closely and brake late. Newbies can hesitate or mistime acceleration/braking. Prolog chooses the action; Python supplies observations and executes bounded physical motion. Actual contact detection stays active over every manoeuvre.

Wrong-way travel is separate from passing. A higher-risk drunk sedan must reach an eligible inner lane on a long peripheral straight, have at least 52 m of usable room, and pass a once-per-encounter decision and delayed oncoming assessment. Default willingness is 0.18; assessment is 0.4 s. A 16 m continuous crossing reaches the adjacent opposing inner lane; it does not jump over the road. The sustained episode is sampled at 2–4 s with a 2.5 m/s desired speed, followed by a continuous return when space permits. Full vehicle envelopes and collision checks remain enabled. No actor is forced at a fixed time, no per-frame rerolls occur, and oncoming vehicles remain present.

Ordinary night measurements, lifecycle counts, admitted mix and timing are documented in [the four-lane results](docs/four-lane-results.md). Passing completions require physically clearing the leader; merely reaching the inner lane is reported separately. Pre-departure cancellations and aborted passes are distinct from contact. Planned lane changes may incidentally pass another vehicle; the overtaking count deliberately tracks selected passing episodes.

## Collision audit

Each admitted actor keeps up to four seconds of 10 Hz pre-contact history: actual/perceived gaps, speed and acceleration, braking limit, path/lane, manoeuvre, lead vehicle/actions, Prolog proposal, executed control and the physical rectangle corners. Histories are copied into incident exports and survive cleanup. Visual body geometry and selection rectangles use the physical dimensions; decorative windows and lamps stay within those dimensions.

The audit found and fixed a real roundabout-departure bug: an outer-destination connector could miss an inner-destination vehicle stopped in their shared departure. The new regression reproduces this case. Normal steady following remains collision-free in the ordinary run and focused checks. Delayed-braking fixtures still produce physical rear-end contact, and ordinary night histories show substantial perceived clearance after the actual gap has almost vanished. The audit does not infer fault solely from involvement.

Swept rectangle collision detection checks path intervals, lane changes, wrong-way movement and junctions. It resolves first contact without disabling collision checks or limiting incidents to junctions. Persistent contact and pile-up membership do not create extra origins; separate incidents retain separate origins. Wrecks obstruct traffic until their recorded clearance time.

## Frequency overlays

Counts accumulate since reset. Directed lane-segment passages are counted once per vehicle route occurrence, including initial partial passages and the portions traversed during a lane change. Later traversals count again. Wrong-way physical passages are mapped to the occupied directed lane, even when traversed against its direction. Junction connectors do not add lane passages.

| Overlay | Transparent | Yellow | Orange | Red |
| --- | --- | --- | --- | --- |
| Lane passages, scale 1 | 0 | 1–24 | 25–49 | 50+ |
| Unique incident origins per 16 m cell, scale 1 | 0 | 1–2 | 3–4 | 5+ |

Scale buttons multiply thresholds, never data. The numeric legend labels the scale and period. Colours are unlit and stable, without per-frame normalization. Overlay meshes follow the widened lane paths; unchanged data reuses pooled geometry. The GUI verification includes explicitly labelled synthetic repeated-passage and separate-incident fixtures to check visible yellow/orange/red progression; ordinary-run evidence is recorded separately.

## Rendering and performance

The invisible-vehicle regression was caused by reparenting a cached scene node into successive vehicles. Each vehicle now owns separate body and lamp nodes copied from detached templates; only immutable geometry buffers are shared. Hiding, tinting or destroying one instance cannot affect another. Bodies remain opaque and normally lit, with normal culling. Body/wheels, lamps and the selection highlight share the interpolated transform; headlight cones originate at the matching front bumper. Crashed vehicles use their exact contact pose. Physics still uses fixed-step footprints; interpolation adds at most one step of visual latency and does not change collision detection.

Fresh-process visibility checks cover duplicate sedans/trucks/buses by day/night at close and distant zoom, instance deletion/reuse, lane changes, wrong-way geometry and crash clearance. The earlier optimized FPS figures were invalid because bodies were missing; corrected measurements require independent visible body nodes for every active vehicle. Rejected measurements are retained under `artifacts/four-lane/invalid-visibility`.

Physics remains fixed at 60 Hz; behavioural observations run at 10 Hz. Rendering interpolates the two most recent physical poses with one fixed step of visual latency. Camera movement uses render-frame elapsed time. Pausing and contacts display the exact physical pose.

Immutable scenery is batched. Eighteen vehicle type/colour assets are prepared before traffic starts; a car uses one shared body/trim mesh and one shared bulb mesh. Street illumination is a baked irradiance texture applied in world space to roads and vehicles. Eight nearby headlights use 10 Hz selection with a 12 m retention preference, and their positions update every rendered frame. UI text updates at up to 10 Hz; heatmaps update when their data or settings change. Signal colours update on change. Performance lighting skips shadow sampling and the shadow pass; quality adds daytime sun shadows. The sun casts no shadows after sunset. Night illumination is approximate and lacks building occlusion.

The real-window benchmark records day/night, actual 40/100 populations and stationary/pan-zoom cases at 1440 × 900, uncapped with VSync off. Hardware: Intel Core i9-13900HX, NVIDIA RTX 4060 Laptop GPU, Windows 11. [Results](docs/four-lane-results.md) include before/after median, p95 and p99 frame times and inclusive component costs. **144 FPS has not been achieved across these workloads.** No traffic reduction, collision disabling or simulation time dilation is used to improve the figures.

## Verification

```powershell
& '..\.venv\Scripts\python.exe' -m unittest discover -s tests -v
& '..\.venv\Scripts\python.exe' -m traffic.verify_four_lane --normal --duration 240 --seeds 42
& '..\.venv\Scripts\python.exe' -m traffic.verify_four_lane --duration 240 --seeds 42 43 44
& '..\.venv\Scripts\python.exe' main.py --smoke-capacity --fps 0
& '..\.venv\Scripts\python.exe' -m traffic.visibility_checks
& '..\.venv\Scripts\python.exe' -m traffic.render_benchmark --phase before --seconds 8
& '..\.venv\Scripts\python.exe' -m traffic.render_benchmark --phase after --seconds 8
& '..\.venv\Scripts\python.exe' -m traffic.render_benchmark --phase after --shadow-probe --seconds 8
& '..\.venv\Scripts\python.exe' -m traffic.render_benchmark --phase after --heat-probe --seconds 8
```

The legacy two-lane `Network` remains for historical regression fixtures. The application and new ordinary-run verification use `FourLaneNetwork`. Historical results in `docs/capacity-funnel.md` and `artifacts/capacity-final` describe the previous network and are not four-lane acceptance evidence. The source snapshot before this update is `artifacts/before-four-lane.zip`.
