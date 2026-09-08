# Crossing City ? Python + Prolog Traffic Lab

The original compact centre is restored: **64 m blocks**, the same central nine building plots and the original Home camera framing. Capacity work extends outward through a connected peripheral belt; it does not enlarge the central blocks. Admission, driver behaviour, incident cleanup and night lighting fixes are retained. No visual polish is included.

## Run

```powershell
& '..\.venv\Scripts\python.exe' main.py
& '..\.venv\Scripts\python.exe' main.py --population 100 --scenario Baseline
& '..\.venv\Scripts\python.exe' main.py --population 100 --scenario "Evening/night" --seed 42
```

The default GUI starts at target 40 in accident mode. Baseline uses only Normal drivers at noon; Evening/night starts at 21:00 with mixed drivers. `--compact-only` keeps the original road network with improved admission and four gates, without the outer belt. `--mode supervised` enables conservative diagnostic movement. No dependencies were added; use the existing parent virtual environment.

| Control | Effect |
| --- | --- |
| Run setup | Scenario, mode, target 0?100, current profiles and entry blockers |
| Pause / Space | Freeze traffic, clearance, demand and clock-driven lighting |
| Reset / R | Fresh run, target 40 and default 30 s green |
| Scenario or mode change | Fresh run retaining target |
| Click vehicle | Traits, perception, proposal/execution, manoeuvre and audited removal reason |
| Click junction | Local green override; Use global removes it |
| Global green | 5?120 s, applied at the next green boundary |
| None / Road usage / Accidents | Cumulative overlays since reset |
| WASD / arrows / wheel | Pan and zoom, including the peripheral roads |
| Home / H | Original compact-centre framing |

## Layout and admission

The rejected enlargement doubled road spacing while leaving the building plots unchanged, creating oversized grass areas. The centre is back at junction coordinates `(-96, -32, 32, 96)` and building centres `(-64, 0, 64)`. Pavement plots remain 48 m across, lawns 31 m, building footprints 9 m and roofs 10 m. Home framing no longer scales with the outer map extent.

A belt road sits outside the original city at ?160 m, with four connections to existing approaches. Four external gates/exits and four marked belt-frontage accesses serve real destination trips. Sixteen additional frontage plots use the original compact proportions. The belt provides 96?160 m straight lane sections for overtaking and wrong-way encounters. The central road and junction geometry remains unchanged.

The software investigation found no hidden 40-car cap or stale reservations in sampled runs. A blanket incoming-reservation spawn veto was replaced by route-distance, reaction and stopping-clearance checks. New demand weights account for existing pending tickets, while retries preserve ticket identity and rotate fairly. Physical overlap, following clearance, collision checks and valid trip completion remain enforced.

With all admission improvements and four gates, the compact-only six-minute probe peaked at **89** and ended at **87**, with 13 pending tickets, 46 completed trips and zero incidents. Repeated entry-spacing, occupancy and approaching-traffic blocks dominated. This establishes a local admission/queue bottleneck under that demand, not a proof that total road surface cannot hold 100 sedans. Independent frontage accesses make the belt's additional storage usable.

**Active = live on-road vehicles + uncleared wrecks.** Pending requests are never counted as active. Lowering the target drains through valid trip completion. Cleanup removes only due incident members and records every removal reason. Queue fairness does not guarantee a bounded wait at a physically blocked entry.

## Driver behaviour

All numerical behaviour settings are **configurable, illustrative project assumptions**, not real-world impairment statistics. Drunk drivers retain the 75% higher-risk / 25% less-aggressive split; newbies retain 70% cautious / 30% unsteady. Normal behaviour and all prior regression tests are preserved.

| Manoeuvre setting | Default |
| --- | --- |
| Eligibility | Higher-risk drunk sedans in accident mode |
| Passing willingness | 0.50 per driver/road/leader opportunity |
| Wrong-way willingness | 0.18 per driver/road opportunity; less aggressive 0 |
| Assessment | At least 0.4 s using delayed/biased perception |
| Lane shift / end buffer | 9 m / 4 m |
| Wrong-way initial room | 28 m minimum |
| Sustained wrong-way duration / desired speed | Sampled 2?4 s / 2.5 m/s, subject to physical braking |
| Passing leader | Moving 0.5?10 m/s, at least 2 m/s desired advantage, centre distance below 30 m |
| Access/bus-stop protection | 14 m either side, mirrored into both directions |

Manoeuvres must fit within a single clear road section, including return. Junctions, roundabouts and portal roads remain excluded. Peripheral straights provide usable room without widening central blocks. The belt pub follows the same illustrative night driver mix as the existing pub; admissions and traits remain random. No manoeuvre is scheduled at a fixed time, no opportunity is rerolled every frame, and oncoming vehicles remain present.

The observational funnel records admitted mix, road encounters, overlapping rejection reasons, eligible opportunities, personality declines, selected assessments, installed paths, actual motion, returns and collisions. Installed-path and motion counts distinguish selected decisions from execution. Prolog still controls transitions; physical collision detection remains independent of perceived safety.

## Night lighting

Clock-based daylight, street illumination, pooled headlight cones, night bulbs and readable signals/incident markers are retained. Ground and lightmap bounds cover the belt; Home framing stays on the compact centre. Illumination is approximate and lacks building occlusion; eight nearby headlight cones are pooled rather than giving every car a dynamic light.

## Verification and evidence

```powershell
& '..\.venv\Scripts\python.exe' -m unittest discover -s tests -v
& '..\.venv\Scripts\python.exe' -m traffic.capacity_experiments --scenario Baseline --duration 360
& '..\.venv\Scripts\python.exe' -m traffic.capacity_experiments --seed 42 --duration 180
& '..\.venv\Scripts\python.exe' -m traffic.capacity_experiments --seed 43 --duration 180
& '..\.venv\Scripts\python.exe' -m traffic.capacity_experiments --seed 44 --duration 180
& '..\.venv\Scripts\python.exe' main.py --smoke-layout
& '..\.venv\Scripts\python.exe' main.py --smoke-capacity
```

Current exports use `artifacts/capacity-final/`. Each acceptance experiment checks geometry and interpenetration every 1/60 s step, population/removal accounting and sampled reservation validity. Normal acceptance additionally requires 100 active vehicles and zero incidents. The GUI capture uses ordinary seeded runs without inserted actors.

**Verified:** ordinary Normal seed 42 reached 100 at **95.3 s** and completed **94 trips in six minutes**, with zero incidents or overlaps. Three ordinary 180 s night runs recorded **one completed overtake and five executed wrong-way manoeuvres** (one returned, three collided, one unfinished). Seed 43 selected neither manoeuvre. **All 59 regression tests and the GUI checks passed.**

See [the capacity and funnel report](docs/capacity-funnel.md) for final measurements, rates and limitations. Layout captures: [compact centre](artifacts/compact-centre-detail.png), [outer belt](artifacts/compact-outer-belt.png). Results under `artifacts/expanded-rejected/` used the discarded 128 m layout and are **not acceptance evidence for this layout**.

## Retained metric definitions and limitations

Distance sums actual centre travel in vehicle-km. Waiting is speed below 0.05 m/s, including red lights and wrecks but excluding separately counted bus dwell. Incident rates use incident origins per vehicle-km; zero exposure is N/A. Involved counts unique vehicle IDs. Road usage counts directed-lane entries per route occurrence; accident heatmaps retain historical origins after clearance. Reset clears run history.

A target is not a guarantee of continuous exact occupancy. Valid trip completion, safe admission and night crashes make active counts fluctuate. Short seeded demonstrations show reachability and variation, not calibrated behaviour frequencies. Routing retains randomized breadth-first search over junction hops, not travel-time optimization. The peripheral layout changes travel distances and destinations, so earlier milestone exposure and throughput figures are not directly comparable.

Previous work: [driver revision](docs/driver-revision.md), [incident/removal audit](docs/recovery-audit.md), [earlier recovery revision](docs/recovery-revision.md).
