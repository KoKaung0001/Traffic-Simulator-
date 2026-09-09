# Invisible vehicle regression

The rendering cache stored a live Ursina/Panda scene node and assigned that same node to multiple entities. Ursina's model setter reparents a supplied `NodePath`; it does not create a new instance. Creating another vehicle with the same type/colour therefore moved the first vehicle's body to the new owner. Lamp meshes had the same ownership defect, while shader-generated headlights could remain visible without a body.

The cache now holds detached templates. Each vehicle receives its own copied scene nodes through `copyTo`; Panda can share immutable geometry buffers, but parentage, visibility, colour and removal are independent. A vehicle's wheels are part of its combined body mesh, and its bulb mesh is a child of the same vehicle root. Body geometry remains opaque and normally lit. Normal culling stays enabled.

The audit also corrected two alignment issues: the selection highlight now uses the body's interpolated pose, and headlight cones originate at the interpolated front bumper rather than the cabin centre. Crashes switch the complete visual to the exact contact pose. Collision detection still uses authoritative fixed-step footprints; ordinary interpolation has one fixed step of visual latency and does not change physics.

## Fresh-process verification

```powershell
& '..\.venv\Scripts\python.exe' -m traffic.visibility_checks
& '..\.venv\Scripts\python.exe' main.py --smoke-capacity --fps 0
```

The dedicated real-window check passed all 12 combinations of sedan/truck/bus, day/night and close/distant zoom (55/220). Each type has two identical cached assets visible simultaneously. It checks unique body/lamp nodes, correct parents, visibility, full opacity, positive scale, model bounds, road clearance and body/light/highlight transforms. Close captures retain visible wheels and normal shaded surfaces; distant bodies remain present without disabling culling.

Hiding, tinting and destroying one duplicate leaves its sibling intact. Recreating a vehicle from that cache still works. Additional checks cover all vehicle types on lateral paths, sedan wrong-way geometry, exact crash poses and isolated removal. The final result records 432 ownership checks across the display cases, plus the lifecycle checks.

Ordinary GUI verification also validates scene ownership and transforms during natural passing, roundabout movement, wrong-way travel, crashes and replacement admissions. Physics and seeded driver decisions are unchanged by these renderer fixes.

Evidence: `artifacts/visibility/results.json` and the 12 screenshots in that directory. Examples: [day buses](../artifacts/visibility/day-bus-55.png), [night buses](../artifacts/visibility/night-bus-55.png), [night trucks](../artifacts/visibility/night-truck-55.png), [day sedans](../artifacts/visibility/day-sedan-55.png), [distant night view](../artifacts/visibility/night-sedan-220.png).

## Performance correction

The earlier optimized FPS measurements are invalid: not every active vehicle had a visible body. They are retained only as rejected evidence under `artifacts/four-lane/invalid-visibility`. The corrected benchmark validates model ownership and records an independent body-node count of 40 or 100, matching the measured active population. Use the replacement figures in [four-lane results](four-lane-results.md), not the earlier reported 67 FPS night-pan result.
