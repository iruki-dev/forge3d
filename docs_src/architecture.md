# Architecture

forge3d is built around one principle: **physics and rendering never know about each other**.

---

## The SceneSnapshot contract

```
world.step()               # pure physics — no renderer import
snap = world.snapshot()    # SceneSnapshot — pure data, no physics
frame = renderer.render(snap)  # renderer only knows about data
```

`SceneSnapshot` is the sole bridge between physics and rendering. It contains:

- Per-body transforms (position + 3×3 rotation matrix)
- Shape descriptors (box / sphere / capsule / mesh)
- Material parameters (colour, roughness, metallic, emissive, texture path)
- Camera and light configuration
- Terrain heightfield data

This means you can swap renderers — or skip rendering entirely (headless training) — without touching any physics code.

```
Physics core               → SceneSnapshot →  RealtimeRenderer   (OpenGL 3.3, PBR)
(RNEA / CRBA / ABA)                       →  DeferredRenderer   (OpenGL 4.3, G-buffer)
                                           →  HQRenderer         (NumPy ray-tracer)
                                           →  headless / training (no snapshot needed)
```

---

## Layer diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          Public API (Facade)                                │
│   World · Body · Shape · Material · App · Viewer · Recorder                 │
│   Input · Key · OrbitCamera · FollowCamera · CharacterController            │
│   PhysicsProfiler                                                           │
├───────────────────────────────┬────────────────────────────────────────────┤
│   Advanced systems (v2.0)     │   Rendering layer                           │
│   ├─ ECS (EntityWorld)        │   Renderer (ABC)                            │
│   ├─ Animation (Skeleton,     │   ├── RealtimeRenderer (moderngl, PBR,      │
│   │    AnimationClip, FABRIK) │   │     PCF shadow, terrain)                │
│   ├─ Audio (AudioSystem,      │   ├── WindowedRealtimeRenderer (glfw, HUD)  │
│   │    AudioSource)           │   ├── DeferredRenderer (G-buf, SSAO, bloom) │
│   ├─ Particles (Emitter)      │   └── HQRenderer (NumPy ray-tracer)         │
│   ├─ Scene (SceneManager)     │                  ▲                          │
│   ├─ UI (Canvas, Panels)      │                  │  SceneSnapshot (data)    │
│   └─ Editor (EditorApp)       │──────────────────┘                          │
├───────────────────────────────┴────────────────────────────────────────────┤
│                          Physics core                                        │
│   math/        — SE3, quaternion, spatial algebra                           │
│   dynamics/    — RNEA, CRBA, ABA (Newton-Euler + Articulated-Body)          │
│   collision/   — SAT OBB-OBB, GJK+EPA, sphere/capsule analytic, heightfield│
│   contact/     — Impulse PGS solver, Coulomb friction, Baumgarte            │
│   constraints/ — Hinge, Prismatic, Ball, Fixed, Distance, Spring joints     │
│   model/       — URDF loader, DH kinematics, robot config                  │
│   sim/         — PhysicsWorld (step/CRUD/snapshot), JAX batch, domain rand │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Module map

| Module | Responsibility |
|--------|---------------|
| `forge3d.math` | SE3 transforms, quaternion operations, spatial vector algebra |
| `forge3d.dynamics` | RNEA (Newton-Euler), CRBA (composite-rigid-body), ABA (Articulated-Body) |
| `forge3d.collision` | SAT OBB-OBB, GJK+EPA convex narrow-phase, capsule/sphere analytic, AABB broad-phase, heightfield, raycast |
| `forge3d.contact` | Impulse PGS solver (6 iterations), Coulomb friction cones, Baumgarte position correction |
| `forge3d.constraints` | Sequential Impulse joint solver — Hinge, Prismatic, Ball, Fixed, Distance, Spring |
| `forge3d.model` | URDF loader, DH kinematics model, robot config |
| `forge3d.sim` | `PhysicsWorld` (step, CRUD, snapshot, sleeping), JAX batch step, domain randomization |
| `forge3d.render` | `Renderer` ABC, `SceneSnapshot` data contract, all renderers |
| `forge3d.robot` | `Robot` class, UR5 preset, FK/IK |
| `forge3d.io` | OBJ loader, `MeshData`, convex hull inertia |
| `forge3d.facade` | `World`, `Body`, `Shape`, `Material` — thin API wrappers |
| `forge3d.viewer` | `Viewer` (headless + windowed realtime loop) |
| `forge3d.recorder` | `Recorder` (video capture, policy rollout) |
| `forge3d.app` | `App` (game-loop abstraction) |
| `forge3d.input` | `Input` snapshot, `Key` constants, `InputBuilder` |
| `forge3d.camera` | `OrbitCamera`, `FollowCamera` |
| `forge3d.character` | `CharacterController` (capsule + ground raycast) |
| `forge3d.profiler` | `PhysicsProfiler`, `PhysicsProfile` |
| `forge3d.ecs` | `EntityWorld`, `Component`, `System`, built-in components |
| `forge3d.animation` | `Skeleton`, `AnimationClip`, `AnimationPlayer`, `BlendTree`, `FABRIKSolver` |
| `forge3d.audio` | `AudioSystem`, `AudioSource`, `AudioListener`, `AudioClip` |
| `forge3d.particle` | `ParticleEmitter`, `ParticleSystem`, presets |
| `forge3d.scene` | `SceneManager`, `SceneNode`, `Prefab` |
| `forge3d.ui` | `Canvas`, `DebugPanel`, `InspectorPanel`, `HierarchyPanel`, `UISystem` |
| `forge3d.editor` | `EditorApp`, `PlayState`, gizmos |
| `forge3d.errors` | `Forge3dError`, `ValidationError`, `PhysicsError`, `RenderError` |

---

## Design rules (enforced by tests)

1. **Physics core never imports render** — `grep -r "from forge3d.render" src/forge3d/{math,dynamics,collision,contact,model,sim}` must return nothing.
2. **Functional immutability** — physics functions take a state and return a new state. No in-place mutation.
3. **Both backends identical** — `ENGINE_BACKEND=numpy` and `ENGINE_BACKEND=jax` produce numerically equal results within float64 tolerance.
4. **Rust fallback** — `USE_RUST_CORE=0` must pass all tests. The Python path is always correct; Rust is only a speed accelerator.

---

## Backends

```bash
ENGINE_BACKEND=numpy python my_sim.py   # NumPy (default, always available)
ENGINE_BACKEND=jax   python my_sim.py   # JAX JIT + vmap (optional acceleration)
USE_RUST_CORE=1      python my_sim.py   # Enable Rust PGS + GJK (requires build)
USE_RUST_CORE=0      python my_sim.py   # Force Python fallback
```

The physics core uses a thin `backend.py` shim mapping `xp.array`, `xp.dot`, etc. to
either `numpy` or `jax.numpy`. JAX unlocks JIT compilation and `vmap` for batched
multi-environment rollouts, achieving ~2,000× throughput over single-step Python.

---

## Two-layer project structure

forge3d enforces a strict library / application separation:

```
src/forge3d/          ← Library (1st-class product)
  facade.py           ← Public World/Body/Shape/Material API
  sim/world.py        ← PhysicsWorld internal engine
  ...

apps/                 ← Application layer (uses library as external user)
  my_game/
    main.py           ← import forge3d  (never touches src/forge3d internals)
```

If writing an application requires changing the library internals, the abstraction has failed.
Stop and fix the API instead.
