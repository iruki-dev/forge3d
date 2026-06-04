# forge3d

**Pure-Python 3D physics game engine — easy like pygame, beautiful like simulation.**

[![PyPI version](https://img.shields.io/pypi/v/pyforge3d.svg)](https://pypi.org/project/pyforge3d/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/iruki-dev/forge3d/blob/main/LICENSE)
[![CI](https://github.com/iruki-dev/forge3d/actions/workflows/ci.yml/badge.svg)](https://github.com/iruki-dev/forge3d/actions/workflows/ci.yml)

---

## What is forge3d?

forge3d is a batteries-included 3D physics engine written **entirely in Python** — no MuJoCo, no PyBullet, no Bullet. Dynamics, collision, and contact are all solved by forge3d's own code, backed by NumPy and optional JAX acceleration.

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

## Two faces, one API

| Mode | Purpose | Speed |
|------|---------|-------|
| **Realtime** (`Viewer`) | Interactive simulation, game loop | 60 FPS |
| **High-Quality** (`Recorder`) | Offline video, research figures | Seconds / frame |

The physics code never changes — only the renderer does. That is the [SceneSnapshot contract](architecture.md).

---

## Feature highlights

| Category | Details |
|---|---|
| **Physics** | Rigid-body (RNEA / CRBA / ABA), semi-implicit Euler, SAT OBB-OBB, sphere, capsule, GJK/EPA |
| **Contact** | Impulse PGS solver (10 iterations), Coulomb friction, Baumgarte, angular impulse |
| **Rendering** | Real-time PBR (OpenGL via moderngl); HQ software ray-tracer; **heightfield terrain rendering** |
| **Joints** | Hinge, Prismatic, Ball, Fixed, Distance, Spring — serialized in `World.save/load` |
| **Robots** | UR5 FK/IK, DH parameters, Jacobian |
| **RL** | Gymnasium-compatible `ReachEnv` / `PickPlaceEnv` |
| **Performance** | JAX JIT + vmap: 2,000× throughput; AABB broad-phase; contact cache (no double detection) |
| **Typed** | Full `py.typed` — works with mypy, pyright |

### New in v1.1.0 — Game-Ready

| Feature | API |
|---------|-----|
| Static bodies everywhere | `add_box(static=True)`, `add_capsule(static=True)`, `add_static_box()` |
| Runtime physics properties | `body.friction = 0.1`, `body.restitution = 0.9` |
| Per-body damping | `body.linear_damping = 1.0`, `body.angular_damping = 2.0` |
| Terrain rendering | `add_terrain()` now appears in `Viewer` as a shaded mesh |
| Local-frame camera | `FollowCamera(frame="local")` — always follows from behind a vehicle |
| Raycast | `world.raycast(origin, direction, max_dist)` → `RayHit` |
| pygame input bridge | `InputBuilder.feed_pygame_event(event)` |
| HUD text | `viewer.draw_text(text, x, y, size, color)` |
| Weld rotation | `world.weld(child, parent, local_rotation=...)` |
| Joint save/load | `World.save()` now includes all joint types |

---

## Installation

```bash
pip install pyforge3d                # Core (physics only)
pip install "pyforge3d[render]"      # + Realtime & HQ rendering
pip install "pyforge3d[rl]"          # + Gymnasium / SB3 RL
pip install "pyforge3d[all]"         # Everything
```

!!! note "설치 이름 vs import 이름"
    PyPI 배포명은 `pyforge3d`이지만 코드에서는 기존과 동일하게 `import forge3d`를 사용합니다.

→ [Full installation guide](install.md)

---

## Quick links

- [**Quickstart** — 15-line examples](quickstart.md)
- [**Tutorials** — step-by-step guides](tutorials/01_physics.md)
- [**API Reference** — complete class / method docs](api/world.md)
- [**Architecture** — how physics and rendering are decoupled](architecture.md)
- [**Changelog**](changelog.md)
