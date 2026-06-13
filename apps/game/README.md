# FORGE RUNNER

A 3D physics platformer built on **[forge3d](https://iruki.dev/forge3d/)**
(`pyforge3d`), using as much of the engine as possible: heightfield terrain,
the capsule character controller, trigger zones, collision layers & events,
motorised hinge joints, raycast queries, kinematic platforms, an OrbitCamera
rig, and physics-debris VFX.

Collect **5 energy cores** scattered across a valley — over a lava lake, a
shuttle-platform chasm and a windmill bridge — then escape through the
extraction gate on the high shelf. Magenta sentries patrol the route and
chase you on sight.

## Install & run

```bash
pip install "pyforge3d[render]"
python main.py
```

Requires Python 3.12+ and a machine that can open an OpenGL window
(the engine uses glfw + moderngl).

No display? Verify everything headlessly (runs a scripted bot and saves
screenshots):

```bash
python main.py --smoke 600
```

## Controls

| Input | Action |
|---|---|
| `W A S D` | Move (camera-relative) |
| `SPACE` | Jump → double jump; **hold** while falling to glide |
| `SHIFT` | Dash (1.1 s cooldown) |
| `Q / E`, right-mouse drag | Rotate camera |
| `R / F` | Camera pitch |
| Mouse wheel | Zoom |
| `ENTER` | Start / retry |
| `ESC` | Quit |

## The route

1. **Start plateau** — first checkpoint; a core sits on a nearby hill.
2. **Lava lake** — hop the stepping stones; a core waits atop a pillar
   mid-lake (jump for it). Touching lava costs 25 HP and sends you back.
3. **Shuttle chasm** — two counter-phased moving platforms ferry you across;
   a bonus core floats over the middle.
4. **Windmill bridge** — two motorised blades sweep the deck; time your run.
   A blade hit costs 10 HP and knocks you flying.
5. **Spring pad → summit** — the green pad launches you up the cliff. Two
   sentries guard the summit cores.
6. **Extraction gate** — opens (red beam drops) once all 5 cores are online.
   Finish fast for a time bonus.

## Project layout

| File | Role |
|---|---|
| `settings.py` | Every tuning constant (movement, camera, damage, scoring) |
| `level.py` | Terrain sculpting + all scripted geometry (platforms, windmill, springs, lava, cores, checkpoints, gate) |
| `player.py` | Character controller wrapper: coyote time, double jump, glide, dash, terrain contact |
| `enemies.py` | Patrol/chase sentries with line-of-sight checks |
| `camera_rig.py` | Third-person orbit camera with occlusion handling |
| `vfx.py` | Physics-debris particle bursts on the DEBRIS layer |
| `hud.py` | All `draw_text` / `draw_rect` overlays |
| `game.py` | State machine (menu/playing/dead/win) + trigger/collision event wiring |
| `main.py` | Entry point: windowed game loop and `--smoke` headless test |

## forge3d engine notes (discovered while building)

Two engine limitations shaped the implementation — both verified
empirically against `pyforge3d 2.1.1`:

* **Capsules do not collide with heightfields** (only spheres/boxes do), and
  **rays do not hit heightfields** either. The player capsule therefore does
  its own terrain contact: `Level.ground_height()` (bilinear sampling of the
  height array) is the ground truth, and `player.py` snaps the capsule onto
  it. The same sampling powers camera occlusion and sentry line-of-sight.
* **Heightfield arrays are indexed `[row=y, col=x]`** — `level.py` generates
  and samples `[x, y]` and hands the engine the transpose.

Other engine behaviours used deliberately: static bodies moved via
`set_position` act as kinematic platforms (the player is carried manually,
since a static body reports zero velocity to the friction solver);
`ignore_collision` keeps the windmill's hinge motors from stalling on
scenery; and `collision_mask = 0` turns boxes into render-only decoration
(core markers, checkpoint flags, lava glow).
