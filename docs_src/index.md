# forge3d

**Pure-Python 3D physics game engine — own dynamics, own rules, no compromises.**

[![PyPI version](https://img.shields.io/pypi/v/pyforge3d.svg)](https://pypi.org/project/pyforge3d/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/iruki-dev/forge3d/blob/main/LICENSE)
[![CI](https://github.com/iruki-dev/forge3d/actions/workflows/ci.yml/badge.svg)](https://github.com/iruki-dev/forge3d/actions/workflows/ci.yml)

---

## What is forge3d?

forge3d is a batteries-included 3D physics game engine written **entirely in Python** — no MuJoCo, no PyBullet, no external physics engines. Dynamics, collision detection, and contact resolution are all handled by forge3d's own code, backed by NumPy and optional JAX acceleration.

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground()
box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)

viewer = f3d.Viewer(world, max_frames=90)
while viewer.is_open:
    world.step(dt=1/60)
    viewer.draw()

print(f"Box final z = {box.position[2]:.2f} m")
```

---

## Core philosophy

forge3d is built around three rules:

1. **Physics and rendering never know about each other.** The only bridge is `SceneSnapshot` — a pure-data object. You can swap renderers without touching physics.
2. **No external physics engines.** Every dynamics algorithm (RNEA, CRBA, ABA, GJK+EPA, PGS) is implemented in forge3d's own codebase. The project is its own physics engine.
3. **Python is the first-class language.** All user-facing API is Python. Performance-critical inner loops optionally compile to native via JAX JIT or Rust (PyO3).

---

## Feature highlights

### Physics core

| Feature | Implementation |
|---------|---------------|
| Rigid-body dynamics | Semi-implicit Euler, functional immutability |
| Robot dynamics | RNEA (Newton-Euler), CRBA (composite-rigid-body), ABA (Articulated-Body) |
| Broad-phase | AABB overlap culling |
| Narrow-phase | SAT (OBB-OBB), GJK+EPA (convex shapes), sphere/capsule analytically |
| Contact solver | Impulse-based PGS (6 iterations), Coulomb friction, Baumgarte stabilization |
| Heightfield terrain | Collision + rendering (32×32 to 512×512) |
| Joints | Hinge, Prismatic, Ball, Fixed, Distance, Spring |
| Raycasts | `world.raycast()` / `world.raycast_all()` |
| Overlap queries | `world.overlap_sphere()` / `world.overlap_box()` |
| Collision layers | Bit-field filtering (PLAYER, ENEMY, TERRAIN, TRIGGER, BULLET, …) |
| Character controller | Capsule body with `move()` / `jump()` / `is_grounded` |
| Sleeping | Automatic idle detection to skip inactive bodies |
| Serialization | `world.save()` / `world.load()` (JSON, includes joints) |

### Game framework

| Feature | API |
|---------|-----|
| App game loop | `App("My World")` with `@app.on_start`, `@app.on_update`, `@app.on_render` |
| Realtime viewer | `Viewer(world)` — headless (offscreen) or windowed (real OS window) |
| Video recorder | `Recorder(world, mode="hq")` → MP4/GIF/PNG sequence |
| Keyboard + mouse | `Input.key_held()`, `key_pressed()`, `mouse_delta()`, `scroll_delta()` |
| Camera controllers | `OrbitCamera`, `FollowCamera` (world or body-local frame) |
| HUD text overlay | `viewer.draw_text(text, x, y, size, color, anchor)` |
| Physics profiler | `world.profiler` context manager → `PhysicsProfile` timing data |

### Advanced systems (v2.0+)

| System | Key classes |
|--------|-------------|
| Entity-Component (ECS) | `EntityWorld`, `Transform`, `Rigidbody`, `MeshRenderer`, `Script`, `PhysicsSystem` |
| Skeletal animation | `Skeleton`, `AnimationClip`, `AnimationPlayer`, `BlendTree`, `FABRIKSolver` |
| 3D audio | `AudioSystem`, `AudioSource`, `AudioListener`, `AudioClip` (WAV/OGG) |
| Particle system | `ParticleEmitter`, `ParticleSystem` + presets (`sparks`, `smoke`, `rain`) |
| Scene management | `SceneManager`, `SceneNode`, `Prefab` |
| In-engine editor | `EditorApp` — scene editor with play/pause/step, transform gizmos |
| UI overlay | `Canvas`, `DebugPanel`, `InspectorPanel`, `HierarchyPanel` |

### Rendering

| Renderer | Mode | Notes |
|----------|------|-------|
| `RealtimeRenderer` | Headless | OpenGL 3.3 via moderngl, PBR, PCF shadows — offscreen FBO |
| `WindowedRealtimeRenderer` | Windowed | glfw OS window, live input, cached HUD text |
| `DeferredRenderer` | Headless | OpenGL 4.3, G-buffer, SSAO, CSM shadows, bloom + ACES tonemapping |
| `HQRenderer` | Offline | NumPy software ray-tracer, Blinn-Phong + ambient occlusion |

### Performance

| Technique | Benefit |
|-----------|---------|
| JAX JIT + `vmap` | 2,000× throughput for batch RL rollouts |
| AABB broad-phase | Skips ~80% of collision pair checks |
| Contact cache | Suppresses duplicate pair detection |
| Body sleeping | Skips physics for idle objects |
| Rust PyO3 core (optional) | Native-speed PGS solver, GJK/EPA, BVH |

---

## Installation

```bash
pip install pyforge3d                # Core (physics only)
pip install "pyforge3d[render]"      # + Realtime & HQ rendering
pip install "pyforge3d[rl]"          # + Gymnasium / SB3 RL environments
pip install "pyforge3d[all]"         # Everything
```

!!! note "Package name vs import name"
    The PyPI distribution is `pyforge3d`, but you always `import forge3d` in code.

→ [Full installation guide](install.md)

---

## Quick examples

=== "Falling box"

    ```python
    import forge3d as f3d

    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground()
    box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)

    viewer = f3d.Viewer(world, max_frames=180)
    while viewer.is_open:
        world.step(dt=1/60)
        viewer.draw()

    print(f"Box landed at z = {box.position[2]:.3f} m")
    ```

=== "App game loop"

    ```python
    import forge3d as f3d

    app = f3d.App("Physics Sandbox", width=1280, height=720)
    ball = None

    @app.on_start
    def setup(world: f3d.World) -> None:
        global ball
        world.add_ground()
        ball = world.add_sphere(radius=0.4, position=(0, 0, 6))

    @app.on_update
    def update(world: f3d.World, dt: float, inp: f3d.Input) -> None:
        if inp.key_pressed(f3d.Key.SPACE):
            world.apply_impulse(ball, (0, 0, 8))

    app.run()
    ```

=== "HQ video"

    ```python
    import forge3d as f3d

    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground(material=f3d.Material(color="ground"))
    world.add_sphere(
        radius=0.4, position=(0, 0, 4.4), mass=1.0, restitution=0.8,
        material=f3d.Material(color="orange"),
    )
    world.set_camera(position=(4, -7, 3), target=(0, 0, 1))

    rec = f3d.Recorder(world, mode="hq", resolution=(1920, 1080),
                       samples=64, output="bounce.mp4")
    rec.run(duration=3.0, dt=1/240, fps=60)
    ```

=== "ECS scene"

    ```python
    import forge3d as f3d

    ew = f3d.EntityWorld()

    e = ew.create_entity(
        f3d.Transform(position=[0, 0, 3]),
        f3d.Rigidbody(mass=1.0),
        f3d.MeshRenderer(shape="box", size=(1, 1, 1)),
    )

    ew.step(dt=1/60)
    tf = ew.get_component(e, f3d.Transform)
    print(f"Entity z = {tf.position[2]:.3f}")
    ```

---

## Quick links

- [**Installation guide**](install.md) — pip, optional extras, GPU notes
- [**Quickstart**](quickstart.md) — 3 working examples in 15 lines
- [**Physics tutorial**](tutorials/01_physics.md) — gravity, collisions, joints, raycasts
- [**Rendering tutorial**](tutorials/02_rendering.md) — cameras, materials, terrain, HUD
- [**API Reference**](api/world.md) — complete class and method documentation
- [**Architecture**](architecture.md) — SceneSnapshot contract, module map, design rules
- [**Changelog**](changelog.md)
