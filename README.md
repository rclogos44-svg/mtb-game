# MTB Dirt Jump — bike, suspension and rider

First playable piece of the mountain bike sandbox: a 29" trail/enduro bike with
real suspension kinematics, a rider in a full-face helmet who pedals with the
cranks, a flat baseplate (plus rollers and a small drop), and a short trail:
a climb, a rock-garden descent and a tabletop jump with a long landing.

## Play it

1. Install **Godot 4.4** (standard build, not .NET): https://godotengine.org/download
2. Open Godot → **Import** → pick `game/project.godot` → **Edit**, then press **F5**.

| Keyboard | Controller | Action |
|---|---|---|
| W | RT | Pedal (shifts through a 12-speed 10–51 cassette by itself) |
| S | LT | Brake |
| A D / ← → | Left stick | Steer; in the air, spin |
| ↓ ↑ | Right stick | ↓ leans back: W + ↓ = wheelie (coasting: manual), in the air a backflip. ↑ in the air: frontflip |
| Space (hold, release) | A | Load the suspension, then pop a bunny hop |
| R | Y | Reset |
| 2 / G, 1 | | Go to the top of the trail, back to the baseplate |
| 3 / P | | Top of the big slope line |
| C | X | Camera: chase → side (best for watching suspension) → orbit |
| T | Back | Slow motion |
| Right-drag, mouse wheel | | Look around, zoom |

On a phone or tablet, on-screen buttons appear instead (turn the phone
sideways): a d-pad for the left thumb (steer/spin, wheelie/flips), PEDAL / BRAKE / HOP with the right, and
CAM / TRAIL / BASE / RESET along the top. Several fingers work at once.

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
* **Wheels** (`game/scripts/bike.gd`): each wheel is a real unsprung mass
  (4.5 kg rear, 3.5 kg front) between the tyre (a ~120 N/mm spring) and the
  suspension, integrated in 8 substeps per physics tick. A fan of rays round
  the tyre finds the ground; each hit counts only as far as that point really
  touches the tyre, so rocks and roller edges are felt without flinging the bike.
* **Springs and dampers** (`game/scripts/suspension.gd`): coil spring with a
  progressive bottom-out bumper; air fork with positive and negative chambers;
  two-stage (low/high speed) compression and rebound damping.
* **Setup like a real bike**: spring rate and fork pressure are chosen from the
  rider's weight to hit 24 % rear / 17 % front sag (set firm, "pumped up"),
  with two volume tokens in the fork; damping is set as a
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

## Helmet

Built in `art/helmet.py` (run `HELMET_STAGE=blockout` to get the grey
silhouette-only version; `art/render_helmet.py` renders front/side/rear views).
Construction follows real full-face MTB helmets, read from the reference photos:

* **Shell** (IXS side/rear/top views): one moulded piece, longer than wide,
  flattened crown, small rear lip, coverage low behind the head, jawline
  rising toward the ear; black EPS liner and rubber trim at every edge.
* **Peak** (IXS top & 3/4, Fox): bolted at both temples and the centre, sweeps
  down at the sides, projects forward with a centre rib and two vent cut-outs.
* **Chin bar** (IXS 3/4 & side, Fox): wide and solid, flat front, level
  underside, large mouth opening backed by mesh with two moulded bars, side vents.
* **Vents** (IXS top, Fox, IXS rear): real openings - brow intakes under the
  peak, crown vents, rear exhausts, chin vents.
* Open eye port for separate goggles (none fitted), padding at the cheeks and
  neck, one restrained side graphic.

## Tests

```bash
godot --headless --path game -s tests/sim_test.gd
```

Rides the bike with an autopilot and checks: sag, standing still, pedalling up
to speed, crank cadence, steering and leaning, braking in a corner, hard
braking without an endo, a 1 m drop, a bunny hop, riding into a wall, knees
staying put while pedalling crouched, the rear wheel tracking the rollers, and
the whole trail (rock garden + jump) at three pedalling efforts.

## The trail

`game/scripts/trail.gd` builds a hill from a centre-line profile: climb at
~13 %, a flat top, a 3 m descent with a rock garden in its steep middle, a
run-in, a 1 m takeoff at 28°, a 2.6 m table, and a 30° landing that runs down
to the ground. Coasting rolls the table; a light pedal lands on the sweet spot;
flat-out overshoots to the bottom, like a real tabletop.

## Tricks

* **Wheelie**: pedal and hold ↓. The rider leans back and holds the bike just
  short of its balance point (~30°); coasting gives a lower manual that fades.
* **Flips**: ↓ / ↑ in the air throw a backflip / frontflip (up to 6 rad/s, about a second per flip).
* **Spins**: ← / → in the air spin the bike; the camera keeps facing the direction of travel.
* Let go near the end: the rider spots the landing and stops the rotation
  lined up with the flight path. The tabletop on the trail has enough air for
  a backflip, frontflip or 360 at a moderate pedal.

## The big line

`game/scripts/big_line.gd` builds a 68 m start tower on a 15% hillside with
five huge jumps (12 m to 23 m gaps, up to ~7 m of air), a berm and a
run-out, behind the rollers. Press 3 (or P) to drop in.

Ride it pedalling and pop every lip (hold Space up the takeoff, let go at the
top): each gap was sized by riding the line in the game that way until every
jump touched down about 40% of the way down its landing. Pedalling without a
pop also rides clean (landing nearer the knuckle); coasting is too slow.

Landings are shaped like built ones: a flat knuckle that rolls over into the
landing angle, a straight steep part, then a curve whose slope eases evenly
into the trail. The design lives in `game/assets/big_line.json`, which the
blueprint (`design/big_line_blueprint.html`) reads too; both build the same
profile and fly the rider over it with air drag to get each speed window.
