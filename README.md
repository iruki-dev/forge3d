# forge3d

> **Pure-Python 3D game engine — easy like pygame, beautiful like simulation.**

[![PyPI version](https://img.shields.io/pypi/v/forge3d.svg)](https://pypi.org/project/forge3d/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-215%20passing-brightgreen.svg)](#testing)

forge3d is a batteries-included 3D physics and game engine written entirely in Python — no
external physics engines (no MuJoCo, PyBullet, or Bullet). Dynamics, collision, and contact are
all solved by forge3d's own code, backed by NumPy and optional JAX acceleration.

```
┌──────────────────────────────────────────────────────────────┐
│                     Public API (Facade)                       │
│  App · World · Body · Shape · Material · Viewer · Recorder    │
│         Input · Key · OrbitCamera · FollowCamera              │
└──────────────┬──────────────────────────┬────────────────────┘
     ┌──────────▼──────────┐   ┌──────────▼───────────────────┐
     │  Physics core        │   │   Rendering layer             │
     │  RNEA · CRBA · ABA   │   │   RealtimeRenderer (OpenGL)  │
     │  SAT · GJK/EPA       │   │   HQRenderer (ray-tracer)    │
     │  Impulse contact     │   │   SceneSnapshot contract      │
     └─────────────────────┘   └──────────────────────────────┘
```

---

## Features

| Category | Details |
|---|---|
| **Game loop** | `App` class — `@on_start` / `@on_update` / `@on_render` decorators |
| **Input** | `Input` snapshot — `key_held`, `key_pressed`, `mouse_pos`, `scroll_delta` |
| **Camera** | `OrbitCamera`, `FollowCamera` — orbit, zoom, pan, smooth follow |
| **Physics** | Rigid-body dynamics (RNEA / CRBA / ABA), semi-implicit Euler integrator |
| **Collision** | SAT OBB-OBB (15-axis), sphere, capsule, GJK/EPA convex-mesh; AABB broad-phase |
| **Contact** | Impulse solver, Coulomb friction, Baumgarte correction, warm-starting |
| **Grasping** | `weld` / `release` kinematic constraints; friction-based pinch grasp |
| **Robots** | UR5 6-DOF FK/IK, DH parameters, Jacobian |
| **Rendering** | Real-time PBR (Cook-Torrance, PCF shadows, albedo/normal textures); HQ software ray-tracer |
| **RL** | Gymnasium-compatible `ReachEnv` / `PickPlaceEnv` |
| **Performance** | JAX JIT+vmap: 2 000× throughput vs. NumPy; AABB broad-phase O(n log n) |
| **Testing** | 215+ automated tests; PyBullet baseline comparison |
| **Typed** | Fully annotated with `py.typed` marker |

---

## Installation

```bash
# Core library (physics + rendering)
pip install forge3d

# With rendering dependencies
pip install "forge3d[render]"

# With RL dependencies
pip install "forge3d[rl]"

# Everything
pip install "forge3d[all]"

# Development install
git clone https://github.com/your-org/forge3d
cd forge3d
pip install -e ".[dev]"
```

**Requirements:** Python 3.12+, NumPy, SciPy, JAX (CPU wheel)

---

## Quick start (15 lines)

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground()
box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)

viewer = f3d.Viewer(world, max_frames=90)
while viewer.is_open:
    world.step(dt=1 / 60)
    viewer.draw()

print(f"Box landed at z = {box.position[2]:.3f} m")
```

---

## App-style game loop

The `App` class wraps the game loop into a decorator-driven flow — just like popular game
frameworks, but with full 3D physics built in.

```python
import forge3d as f3d

app = f3d.App("Physics Sandbox", width=1280, height=720, fps=60)
ball = None  # filled in on_start

@app.on_start
def setup(world: f3d.World) -> None:
    global ball
    world.add_ground()
    ball = world.add_sphere(radius=0.4, position=(0, 0, 6),
                             material=f3d.Material(color="orange"))

@app.on_update
def update(world: f3d.World, dt: float, inp: f3d.Input) -> None:
    # Jump on space
    if inp.key_pressed(f3d.Key.SPACE):
        world.apply_impulse(ball, (0, 0, 8))
    # Nudge with arrow keys
    if inp.key_held(f3d.Key.RIGHT):
        world.apply_impulse(ball, (3 * dt, 0, 0))
    if inp.key_held(f3d.Key.LEFT):
        world.apply_impulse(ball, (-3 * dt, 0, 0))

app.run()
```

---

## Recording a high-quality video

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground(material=f3d.Material(color="ground", roughness=0.8))
world.add_sphere(radius=0.4, position=(0, 0, 4.4), mass=1.0,
                  restitution=0.8, material=f3d.Material(color="orange"))
world.set_camera(position=(4, -7, 3), target=(0, 0, 1))

rec = f3d.Recorder(world, mode="hq", resolution=(1920, 1080),
                   samples=16, output="bounce.mp4")
rec.run(duration=3.0, dt=1 / 240, fps=60)
```

The same `World` code — only the renderer changes. That is the SceneSnapshot contract working.

---

## Camera controls

```python
import forge3d as f3d

world = f3d.World()
world.add_ground()
ball = world.add_sphere(radius=0.5, position=(0, 0, 3))

# Orbit camera starts 10 m back, 30° elevation
cam = f3d.OrbitCamera(target=(0, 0, 1), distance=10, elevation=30)

viewer = f3d.Viewer(world, max_frames=300)
while viewer.is_open:
    inp = viewer.input          # per-frame Input snapshot
    cam.rotate(d_azimuth=inp.scroll_delta() * 5)
    if inp.mouse_button(1):     # right-drag to orbit
        dx, dy = inp.mouse_delta()
        cam.rotate(d_azimuth=dx * 0.5, d_elevation=-dy * 0.5)
    viewer.set_camera(cam.to_snapshot())
    world.step()
    viewer.draw()
```

---

## Robot arm control

```python
import numpy as np
import forge3d as f3d
import forge3d.robot as f3r

world = f3d.World()
world.add_ground()

arm = f3r.load("ur5", base_position=(0, 0, 0))
world.add(arm)

arm.set_joints([0.0, -np.pi/2, np.pi/2, -np.pi/2, -np.pi/2, 0.0])
world.step()

ee_pos, ee_rot = arm.ee_pose()
print(f"End-effector: {ee_pos.round(4)}")
```

---

## Reinforcement learning

```python
from apps.robot_rl.envs.reach_env import ReachEnv
from stable_baselines3 import PPO

env  = ReachEnv(render_mode=None)          # headless, fast
model = PPO("MlpPolicy", env, verbose=1)
model.learn(total_timesteps=200_000)
model.save("reach_policy")
```

JAX batch stepping — 2 000× throughput:

```python
import jax, jax.numpy as jnp
from forge3d.sim.jax_batch import batch_reach_reset, batch_reach_step

key = jax.random.PRNGKey(42)
q, tgt, obs = batch_reach_reset(key, n_envs=256)
q, obs, rew, done = batch_reach_step(q, tgt, jnp.zeros((256, 6)))
```

---

## API reference

### `forge3d.App`

| Member | Description |
|---|---|
| `App(title, width, height, fps, gravity)` | Create application |
| `@app.on_start` | `fn(world)` — called once before the loop |
| `@app.on_update` | `fn(world, dt, inp)` — called every frame before `step()` |
| `@app.on_render` | `fn(world, viewer)` — called after `draw()` |
| `app.world` | The managed `World` |
| `app.run(max_frames)` | Start the game loop |

### `forge3d.World`

| Member | Description |
|---|---|
| `World(gravity)` | Create world; default gravity `(0, 0, -9.81)` |
| `add_ground(material, size, height)` | Static ground plane |
| `add_box(size, position, mass, …)` | Dynamic box body |
| `add_sphere(radius, position, mass, …)` | Dynamic sphere body |
| `add_capsule(radius, half_length, …)` | Dynamic capsule body |
| `add_mesh(mesh_data, …)` | Dynamic convex-hull body |
| `remove(body)` | Remove a body from simulation |
| `clear(keep_statics)` | Remove all (or all dynamic) bodies |
| `get_body(name)` | Find body by name |
| `bodies` | `list[Body]` — all current bodies |
| `step(dt)` | Advance physics by `dt` s (default 1/60) |
| `snapshot()` | Build `SceneSnapshot` for rendering |
| `apply_impulse(body, impulse)` | Δv = impulse / mass |
| `teleport(body, position, quat)` | Instantly move a body |
| `weld(body, anchor, local_offset)` | Kinematic attachment |
| `release(body)` | Remove weld constraint |
| `set_camera(position, target, …)` | Default camera pose |
| `time` | Elapsed simulation time in seconds |

### `forge3d.Body`

| Member | Description |
|---|---|
| `position` | `(3,)` world-frame position |
| `velocity` | `(3,)` linear velocity m/s |
| `orientation` | `(4,)` quaternion `[w, x, y, z]` |
| `angular_velocity` | `(3,)` angular velocity rad/s |
| `name` | String label |
| `is_static` | `bool` |
| `mass` | float, kg |
| `apply_force(force)` | Accumulate force for next `step()` |
| `apply_torque(torque)` | Accumulate torque for next `step()` |
| `set_position(pos)` | Teleport shortcut |
| `set_velocity(vel)` | Velocity override |

### `forge3d.Input`

| Member | Description |
|---|---|
| `key_held(key)` | `bool` — key currently pressed |
| `key_pressed(key)` | `bool` — key just went down this frame |
| `key_released(key)` | `bool` — key just went up this frame |
| `mouse_pos()` | `(x, y)` pixels |
| `mouse_delta()` | `(dx, dy)` pixels since last frame |
| `mouse_button(n)` | `bool` — mouse button 0/1/2 |
| `scroll_delta()` | `float` — mouse wheel tick this frame |

### `forge3d.Key` — key name constants

```python
f3d.Key.SPACE, Key.ESCAPE, Key.ENTER, Key.BACKSPACE, Key.TAB
Key.UP, Key.DOWN, Key.LEFT, Key.RIGHT
Key.W, Key.A, Key.S, Key.D   # also Key.Q … Key.Z
Key.N0 … Key.N9
Key.F1 … Key.F12
Key.SHIFT, Key.CTRL, Key.ALT
```

### `forge3d.OrbitCamera`

| Member | Description |
|---|---|
| `OrbitCamera(target, distance, azimuth, elevation, fov_deg)` | Create camera |
| `rotate(d_azimuth, d_elevation)` | Orbit around target |
| `zoom(delta)` | Multiply distance; `delta > 0` → zoom in |
| `pan(dx, dy)` | Translate target in screen space |
| `position` | Current world-space eye position |
| `to_snapshot()` | `CameraSnapshot` for `viewer.set_camera()` |

### `forge3d.Shape`

```python
Shape.box(size=(1, 1, 1))
Shape.sphere(radius=0.5)
Shape.capsule(radius=0.2, half_length=0.5)
Shape.convex_mesh(mesh_data)          # from forge3d.io.load_obj()
```

### `forge3d.Material`

```python
Material(color="red")                 # built-in preset
Material(color=(0.9, 0.4, 0.1))       # RGB tuple in [0, 1]
Material(color="default", roughness=0.3, metallic=0.7)
Material(texture_path="wall.png")
```

Built-in colour presets: `"default"`, `"red"`, `"blue"`, `"green"`, `"orange"`,
`"ground"`, `"gold"`, `"white"`.

### `forge3d.Viewer`

```python
viewer = f3d.Viewer(world, width=1280, height=720, max_frames=None)
viewer.is_open          # False when window closed or max_frames reached
viewer.draw()           # render one frame → ndarray (H×W×3 uint8)
viewer.input            # current-frame Input snapshot
viewer.set_camera(cam)  # override camera (CameraSnapshot or OrbitCamera)
viewer.run(dt, max_frames, collect_frames)
viewer.close()
```

### `forge3d.Recorder`

```python
rec = f3d.Recorder(world, mode="realtime",        # or "hq"
                   resolution=(1920, 1080),
                   samples=64,                     # HQ only
                   output="sim.mp4")
rec.run(duration=5.0, dt=1/240, fps=60)
rec.run_policy(policy, env, duration=5.0)          # SB3-compatible
```

---

## Architecture

forge3d is designed around one principle: **physics and rendering never know about each other**.

```
world.step()                     # pure physics, no renderer import
snap = world.snapshot()          # SceneSnapshot — pure data
frame = renderer.render(snap)    # renderer consumes data only
```

The `SceneSnapshot` is the sole bridge. Swap the renderer without touching the physics.

```
Physics core        → SceneSnapshot →  RealtimeRenderer (OpenGL)
(RNEA/CRBA/ABA)                    →  HQRenderer       (ray-tracer)
                                   →  headless / training (no snapshot)
```

---

## Project structure

```
forge3d/
├── src/forge3d/
│   ├── __init__.py          # Public API: World, App, Body, Shape, Material…
│   ├── app.py               # App — game-loop abstraction
│   ├── input.py             # Input, Key, _InputBuilder
│   ├── camera.py            # OrbitCamera, FollowCamera
│   ├── facade.py            # World, Body, Shape, Material facades
│   ├── viewer.py            # Viewer (realtime render loop)
│   ├── recorder.py          # Recorder (video capture)
│   ├── backend.py           # NumPy ↔ JAX backend switch
│   ├── math/                # SE3, quaternion, spatial algebra
│   ├── dynamics/            # RNEA, CRBA, ABA
│   ├── collision/
│   │   ├── detection.py     # SAT + AABB broad-phase
│   │   ├── gjk.py           # GJK distance / intersection
│   │   └── epa.py           # EPA penetration depth
│   ├── contact/
│   │   └── solver.py        # Impulse solver (PGS + Coulomb friction)
│   ├── model/               # RigidBodyModel, DH joints, kinematics
│   ├── sim/
│   │   ├── world.py         # PhysicsWorld (step, snapshot, CRUD)
│   │   ├── jax_batch.py     # JAX JIT+vmap batch physics
│   │   └── domain_rand.py   # Domain randomisation
│   ├── robot/               # Robot, UR5 preset, FK/IK
│   ├── render/
│   │   ├── snapshot.py      # SceneSnapshot, Transform, Material…
│   │   ├── base.py          # Renderer ABC
│   │   ├── realtime/        # OpenGL rasteriser (PBR, PCF shadow)
│   │   └── hq/              # Software ray-tracer (Blinn-Phong, AO, AA)
│   ├── io/
│   │   ├── obj_loader.py    # Pure-Python OBJ parser
│   │   └── mesh_data.py     # MeshData, convex_hull_inertia
│   └── py.typed             # PEP 561 type marker
├── apps/robot_rl/            # RL application (Gymnasium envs, training)
├── examples/                 # Self-contained examples (≤15 lines each)
├── tests/                    # 215+ automated tests
├── validation/               # PyBullet / MuJoCo baseline comparison
├── assets/                   # 3D models, textures
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
└── pyproject.toml
```

---

## Validation

| Check | Result |
|---|---|
| PyBullet acceleration comparison (50 pairs) | `max_abs < 2e-11` ✅ |
| Energy conservation (torque-free, no damping) | deviation < 0.1 % ✅ |
| Pendulum period vs. closed-form | error < 0.01 % ✅ |
| JAX ↔ NumPy FK consistency | `max_diff < 1e-16` ✅ |
| Restitution coefficient vs. theory | error < 1.5 % ✅ |
| Coulomb friction threshold | ✅ |

---

## Backend switching

```bash
ENGINE_BACKEND=numpy python my_sim.py   # NumPy (default, CPU)
ENGINE_BACKEND=jax   python my_sim.py   # JAX JIT+vmap
```

The physics core is identical under both backends. JAX enables JIT compilation and
`vmap` for batched multi-environment rollouts.

---

## Testing

```bash
# Single file (recommended for iteration)
pytest tests/test_collision.py -q

# Full suite (skips slow training tests)
pytest tests/ --ignore=tests/test_p9_training.py -q

# With coverage
pytest --cov=forge3d tests/ -q
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short:

1. Fork → feature branch → PR
2. `ruff check . && ruff format .` must pass
3. `mypy src/` must pass
4. New physics code needs a conservation-law or analytical-solution test
5. New public API needs an example in `examples/`

---

## License

MIT — see [LICENSE](LICENSE).
