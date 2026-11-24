# MTB Dirt Jump — bike, suspension and rider

First playable piece of the mountain bike sandbox: a 29" trail/enduro bike with
real suspension kinematics, a rider in a full-face helmet who pedals with the
cranks, and a flat baseplate (plus a few rollers and a small drop) to test on.

## Play it

1. Install **Godot 4.4** (standard build, not .NET): https://godotengine.org/download
2. Open Godot → **Import** → pick `game/project.godot` → **Edit**, then press **F5**.

| Keyboard | Controller | Action |
|---|---|---|
| W / ↑ | RT | Pedal |
| S / ↓ | LT | Brake |
| A D / ← → | Left stick | Steer |
| Space (hold, release) | A | Load the suspension, then pop a bunny hop |
| R | Y | Reset |
| C | X | Camera: chase → side (best for watching suspension) → orbit |
| T | Back | Slow motion |
| Right-drag, mouse wheel | | Look around, zoom |

The panel in the corner shows live fork and shock travel, spring rate, air
pressure and leverage ratio.

## How the suspension works

* **Geometry** (`art/geometry.py`) defines the frame's hard points and solves
  the rear linkage: chainstay on a main pivot, seatstay link, rocker on the
  seat tube, and a coil shock running forward to a brace under the top tube.
  It writes `game/assets/geometry.json`, which both Blender and the game read,
  so the model and the physics always match.
  * Rear: 161 mm travel from a 210×55 coil shock, leverage 3.1 → 2.8 (progressive).
  * Front: 160 mm air fork, 65° head angle, 44 mm offset.
* **Springs and dampers** (`game/scripts/suspension.gd`): coil spring with a
  progressive bottom-out bumper; air fork with positive and negative chambers;
  two-stage (low/high speed) compression and rebound damping.
* **Setup like a real bike**: spring rate and fork pressure are chosen from the
  rider's weight to hit 28 % rear / 20 % front sag; damping is set as a
  fraction of critical. All exposed on the `Bike` node.
* **Wheels** (`game/scripts/bike.gd`): each wheel ray-casts the ground, models
  the tyre as a torus (so leaning is right), compresses the suspension through
  the linkage, and applies slip-angle cornering, rolling resistance, pedalling
  (power- and cadence-limited) and braking inside a friction circle. The rider
  modulates the brakes short of an endo or a skid and absorbs pitch.

## Rebuild the 3D models (optional)

The Blender files are in `art/` (`bike.blend`, `rider.blend`). Models are built
by scripts, so changes are repeatable:

```bash
cd art
python3 geometry.py                 # frame + linkage -> geometry.json
blender -b -P build_bike.py         # -> game/assets/bike.glb
blender -b -P build_rider.py        # -> game/assets/rider.glb (+ pedalling animation)
```

The pedalling animation is one crank revolution; the game seeks it to the
bike's real crank angle, so the feet stay locked to the pedals.

## Tests

```bash
godot --headless --path game -s tests/sim_test.gd
```

Rides the bike with an autopilot and checks: sag, standing still, pedalling up
to speed, crank cadence, steering and leaning, braking in a corner, hard
braking without an endo, a 1 m drop, a bunny hop, and riding into a wall.
