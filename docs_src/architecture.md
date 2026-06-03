# Architecture

forge3d is built around one principle: **physics and rendering never know about each other**.

---

## The SceneSnapshot contract

```
world.step()                     # pure physics, no renderer import
snap = world.snapshot()          # SceneSnapshot — pure data
frame = renderer.render(snap)    # renderer consumes data only
```

The `SceneSnapshot` is the sole bridge between physics and rendering. It contains:

- Per-body transform matrices (position + orientation)
- Shape descriptors (box/sphere/capsule/mesh)
- Material parameters (colour, roughness, metallic, texture)
- Camera and light configuration

Swap the renderer without touching the physics:

```
Physics core        → SceneSnapshot →  RealtimeRenderer (OpenGL)
(RNEA/CRBA/ABA)                    →  HQRenderer       (ray-tracer)
                                   →  headless / training (no snapshot)
```

---

## Layer diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Public API (Facade)                       │
│   World · Body · Shape · Material · App · Viewer · Recorder   │
│         Input · Key · OrbitCamera · FollowCamera              │
└───────────────┬─────────────────────────┬────────────────────┘
     ┌──────────▼──────────┐   ┌──────────▼───────────────────┐
     │  Physics core        │   │   Rendering layer             │
     │  math/               │   │   Renderer(ABC)               │
     │    se3, quaternion   │   │   ├── RealtimeRenderer        │
     │    spatial algebra   │   │   │     moderngl, PBR shader  │
     │  dynamics/           │   │   │     PCF shadow, MSAA      │
     │    RNEA, CRBA, ABA   │   │   └── HQRenderer              │
     │  collision/          │   │         NumPy ray-tracer      │
     │    SAT, GJK/EPA      │   │         Blinn-Phong + AO + AA │
     │    AABB broad-phase  │   └───────────────────────────────┘
     │  contact/            │             ▲
     │    Impulse PGS       │             │  SceneSnapshot
     │    Coulomb friction  │   ──────────┘  (pure data)
     │  sim/                │
     │    PhysicsWorld      │
     │    JAX batch         │
     └─────────────────────┘
```

---

## Module map

| Module | Responsibility |
|--------|---------------|
| `forge3d.math` | SE3, quaternions, spatial vector algebra |
| `forge3d.dynamics` | RNEA, CRBA, ABA (robot dynamics) |
| `forge3d.collision` | SAT OBB-OBB, sphere, capsule, GJK/EPA, AABB broad-phase |
| `forge3d.contact` | Impulse PGS solver, Coulomb friction, Baumgarte |
| `forge3d.model` | URDF loader, DH kinematics, robot config |
| `forge3d.sim` | `PhysicsWorld` (step, CRUD, snapshot), JAX batch, domain rand |
| `forge3d.render` | `Renderer` ABC, `SceneSnapshot`, realtime + HQ renderers |
| `forge3d.robot` | `Robot` class, UR5 preset, FK/IK |
| `forge3d.io` | OBJ loader, `MeshData`, convex hull inertia |
| `forge3d.facade` | `World`, `Body`, `Shape`, `Material` (thin API wrappers) |
| `forge3d.viewer` | `Viewer` (realtime render loop + input) |
| `forge3d.recorder` | `Recorder` (video capture) |
| `forge3d.app` | `App` (game-loop abstraction) |
| `forge3d.input` | `Input`, `Key` |
| `forge3d.camera` | `OrbitCamera`, `FollowCamera` |

---

## Design rules (enforced by tests)

1. **Physics core never imports render** — `grep -r "from forge3d.render" src/forge3d/{math,dynamics,collision,contact,model,sim}` must return nothing.
2. **Apps use library as external user** — `apps/` never imports `src/forge3d` internals (only public `forge3d.*` API).
3. **In-place mutation forbidden** — physics functions take state and return new state.
4. **Both backends identical** — `ENGINE_BACKEND=numpy` and `ENGINE_BACKEND=jax` produce numerically equal results (within float64 tolerance).

---

## Backends

```bash
ENGINE_BACKEND=numpy python my_sim.py   # NumPy (default)
ENGINE_BACKEND=jax   python my_sim.py   # JAX JIT + vmap
```

The physics core (`math/`, `dynamics/`, etc.) uses a thin `backend.py` shim that maps `xp.array`, `xp.dot`, etc. to either `numpy` or `jax.numpy`. JAX enables JIT compilation and `vmap` for batched multi-environment rollouts (2,000× throughput).
