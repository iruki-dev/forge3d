# Changelog

All notable changes to forge3d are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## [2.1.1] — 2026-06-11

### Changed

- Package description and all in-code taglines updated to "own dynamics, own rules, no compromises."

---

## [2.1.0] — 2026-06-06 — API completeness and polish

Bug fixes, missing features, and consistency improvements discovered during development.

### Fixed

- **B-1** `add_terrain(material=Material(...))` custom material lost in snapshot — `TerrainSnapshot.material` / `BodySnapshot.material` fields now include the resolved `Material` object directly
- **B-2** `Body.name` was read-only — `name` setter added
- **B-3** `World.restore(path)` instance method added for in-place restore; existing classmethod `World.load()` retained
- Deferred renderer `Material.emissive` scalar → `(R,G,B)` conversion TypeError fixed

### Added

- `Body.shape_type`, `Body.shape_params`, `Body.rotation_matrix` properties
- `Body.on_collision_begin(cb)` / `on_collision_end(cb)` per-body collision callbacks
- `Material.emissive: float` — propagated through the full snapshot pipeline
- `Transform.quaternion` `[w,x,y,z]` / `Transform.matrix4` `(4,4)` properties
- `TriggerZone.set_position()`, `.set_half_extents()`, `.enabled` runtime manipulation
- `world.raycast_all(origin, dir, max_dist, layer_mask)` — full hit list
- `world.overlap_sphere(center, radius)` / `world.overlap_box(center, half_extents)` spatial queries
- `world.add_terrain(..., friction=0.8, layer=CollisionLayer.TERRAIN)` parameters
- `world.step(dt, substeps=1)` substep support
- `world.update(frame_dt)` fixed-timestep accumulator (`world.fixed_dt`, `world.max_substeps`)
- `world.add_character(position, height, radius)` → `CharacterController` (move/jump/glide)
- `world.profiler` → `PhysicsProfiler` — context manager for step timing
- `JointType` StrEnum (`HINGE`, `BALL`, `PRISMATIC`, `SPRING`, `FIXED`, `DISTANCE`)
- `CollisionLayer.mask_for(*layers)` bitmask helper
- `Viewer(shadow_resolution=N)` — configurable shadow resolution; default raised 512 → **1024**

### Changed

- `CollisionLayer.TERRAIN = 0x0008` (swapped with former `BULLET` value; `BULLET = 0x0020`)

---

## [2.0.0] — 2026-06-04 — v2.0: Python-first high-performance game/simulation engine

v2 advances v1 on three axes:

1. **Runtime performance** — Rust native extension (PyO3 + maturin), ≥10× physics hot-loop speedup
2. **Graphics pipeline** — Deferred PBR + CSM + SSAO + HDR + Bloom (OpenGL 4.3+)
3. **API ecosystem** — ECS, audio, animation, scene management, particles, UI, editor

**Full backward compatibility with v1 API**: `World`, `Body`, `Viewer`, `Recorder` signatures frozen.

### Added — P25: Rust native extension

- `forge3d._core` — PyO3 + maturin mixed build (Rust 1.96+)
- `forge3d._core.gjk_query(verts_a, verts_b)` — GJK + EPA collision detection
- `forge3d._core.bvh_build/bvh_query_pairs` — BVH broadphase (22× improvement at N=500)
- `forge3d._core.pgs_solve` — PGS contact solver Rust path
- `forge3d._core.se3_mul/quat_normalize/quat_mul` — SIMD math (glam-based)
- `USE_RUST_CORE=0/1` env var to force Python fallback

### Added — P26: Modern rendering pipeline

- `DeferredRenderer` — OpenGL 4.3 deferred rendering
    - G-Buffer 4 channels (position/normal/albedo-roughness/emissive-metallic)
    - CSM (Cascaded Shadow Maps) 4 cascades, PCF 9-tap
    - SSAO 64 samples + blur pass
    - HDR framebuffer + ACES tonemap + Kawase bloom
    - Instanced rendering
- `RenderPass` ABC — per-pass pipeline abstraction
- `forge3d.render.DeferredRenderer` publicly exported

### Added — P27: Entity Component System

- `EntityWorld` — entity create/destroy, component CRUD, `query()`
- Built-in components: `Transform`, `Rigidbody`, `Collider`, `MeshRenderer`, `Script`, `CameraComponent`, `LightComponent`
- `System` ABC + `PhysicsSystem`, `RenderSystem`, `ScriptSystem`
- `body_to_entity()` — v1 Body → ECS bridge
- `save_scene()` / `load_scene()` — ECS scene JSON serialization
- `EntityNotFoundError` — clear error on destroyed-entity access

### Added — P28: Audio system

- `AudioClip` — WAV/OGG load + `from_sine()` factory
- `AudioSource`, `AudioListener` — ECS components
- `AudioSystem` — OpenAL auto-detect, `NullDriver` fallback in headless
- `AudioSystem.make_collision_handler()` — collision event → sound trigger factory

### Added — P29: Animation system

- `Skeleton`, `Bone` — skeleton hierarchy, FK world matrices
- `AnimationClip` — keyframe LERP/SLERP interpolation
- `AnimationPlayer`, `BlendTree` — ECS components
- `FABRIKSolver` — N-link FABRIK IK (convergence < 1e-4 m)
- `AnimationSystem` — ECS system
- `chain_from_ur5_joints()` — UR5 FK chain helper

### Added — P30: Scene management

- `SceneNode` — dirty-flag cache + parent/child hierarchy
- `Prefab` — JSON save/load/instantiate
- `SceneManager` — load/unload/additive scene transitions + callbacks

### Added — P31: Particle system

- `ParticleEmitter` — ECS component (rate/lifetime/gravity/restitution)
- `ParticleSystem` — NumPy vectorized + JAX vmap dual path (100k particles < 33 ms)
- VFX presets: `sparks`, `smoke`, `debris`, `rain`

### Added — P32: UI system

- `DebugPanel`, `InspectorPanel`, `HierarchyPanel` — ImGui panels (null fallback)
- `Canvas` — 2D overlay (clipping, NumPy rasterizer)
- `UISystem` — ECS system

### Added — P33: Scene editor

- `EditorApp` — Play/Pause/Step state machine
- `TranslateGizmo` — ray-sphere intersection selection + axis drag
- `EditorLayout` — 3-panel layout
- `screen_to_ray()` — screen coords → world ray

### Added — P34 (optional): wgpu backend

- `WgpuRenderer` — wgpu-py off-screen renderer, WGSL PBR shaders
- Automatic fallback to `DeferredRenderer` when wgpu is not available

---

## [1.1.0] — 2026-06-03 — Game-Ready Release

### Added

**Physics API extensions**

- `World.add_box(static=True)` — create static box via public API
- `World.add_capsule(static=True)` — static capsule support
- `Body.friction` / `Body.restitution` setters — change at runtime
- `Body.linear_damping` / `Body.angular_damping` — velocity decay coefficients
- `World.weld(body, anchor, local_rotation=...)` — preserve child body relative rotation
- `World.raycast(origin, direction, max_dist)` → `RayHit(body, point, normal, distance)`

**Rendering — Heightfield terrain visualization**

- `TerrainSnapshot` dataclass (`forge3d.TerrainSnapshot`)
- Automatically included in `SceneSnapshot.terrains` when `World.add_terrain()` is called
- `RealtimeRenderer` — heightfield triangle mesh generation and rendering (shadow pass included)
- `render.realtime.meshes.heightfield_mesh(heights, cell_size, origin)` public function

**Camera**

- `FollowCamera(frame="local")` — vehicle body-local frame offset
- `FollowCamera(smoothing_hz=6.0)` — FPS-independent exponential-decay smoothing
- `FollowCamera.to_snapshot(dt=...)` — dt parameter for FPS-independent smoothing

**Input**

- `forge3d.InputBuilder` — promoted to public class, auto-wired with glfw callbacks

**Viewer**

- `Viewer.draw_text(text, x, y, size, color, bg_alpha, anchor)` — HUD text overlay

**Serialization**

- `World.save()` — includes joint serialization (Hinge/Spring/Distance/Ball/Fixed/Prismatic)
- `World.load()` — automatically restores saved joints

### Performance

- Removed double `detect_contacts` call in `World.step()`: ~2× event dispatch speed improvement

### Fixed

- `World.add_terrain()` `material` parameter was not forwarded to heightfield rendering

---

## [1.0.0] — 2026-06-03 — Stable Release

### Added (P15 — MkDocs documentation site)

- MkDocs Material theme documentation site (`mkdocs.yml`, `docs_src/`)
- API reference, 4 tutorials, architecture overview page

### Added (P16 — Joint & constraint system)

- `forge3d.constraints` package: Sequential Impulse constraint solver
- `FixedJoint`, `BallJoint`, `HingeJoint` (motor + limits), `PrismaticJoint`, `DistanceJoint`, `SpringJoint`
- `World.add_joint(type, body_a, body_b, ...)` unified API; `World.remove_joint(handle)`
- `forge3d.JointHandle` handle class

### Added (P17 — Collision event callbacks)

- `forge3d.CollisionEvent`, `forge3d.CollisionHandler`
- `World.on_collision_begin`, `on_collision_stay`, `on_collision_end` decorators
- `World.add_collision_handler(body_a, body_b)` pair-wise handler
- `World.add_trigger_zone(position, size)` pure-data zone (no physics collision)

### Added (P18 — Scene serialization)

- `World.save(path)` → JSON save
- `World.load(path)` classmethod → World restore
- `forge3d.StateRecorder` — per-frame state recording + npz save/replay

### Added (P19 — Collision layers & masks)

- `forge3d.CollisionLayer` bitfield constants
- `Body.collision_layer`, `Body.collision_mask` properties

### Added (P20 — API hardening)

- `forge3d.errors` module: `Forge3dError`, `ValidationError`, `PhysicsError`, `RenderError`
- Argument validation for `World()`, `add_box()`, `add_sphere()`

### Added (P21 — Heightfield terrain)

- `World.add_terrain(heights, cell_size, origin)` → Heightfield
- Sphere vs heightmap, box vs heightmap collision detection (bilinear interpolation)

### Added (P23 — Island sleeping)

- Body sleep counter, `Body.is_sleeping` property, `PhysicsWorld.wake_body()`

### Changed

- Version bump: `0.4.0` → `1.0.0` (first stable release)
- Baumgarte bias sign fix (significant constraint solver stability improvement)

---

## [0.4.0] — 2026-06-03

### Added (P14 — PyPI distribution infrastructure)

- GitHub Actions CI/Release/Docs workflows
- OIDC Trusted Publisher (TestPyPI → PyPI)
- `.readthedocs.yaml`, `.github/ISSUE_TEMPLATE/`

### Added

- `App` class — `@on_start` / `@on_update` / `@on_render` decorator-based game loop
- `Input` class — per-frame keyboard/mouse state snapshot
- `Key` — key constants (`Key.SPACE`, `Key.W`, `Key.ESCAPE` …)
- `OrbitCamera`, `FollowCamera`
- `world.bodies`, `world.remove()`, `world.clear()`, `world.get_body(name)`
- AABB broadphase pre-filter: O(n²) → O(n log n)

---

## [0.2.0] — 2026-05

### Added

- `Shape.capsule()`, `Shape.convex_mesh()` — capsule and convex mesh support
- `forge3d.io.load_obj(path)` → `MeshData` — pure-Python OBJ parser
- GJK extension: mesh/capsule support, EPA (`collision/epa.py`)
- PBR shader (Cook-Torrance BRDF): GGX NDF, Smith geometry, Fresnel-Schlick
- PCF shadow map 2K, Reinhard tonemap, albedo texture support

---

## [0.1.0] — 2026-03

### Added

- `World`, `Body`, `Shape`, `Material`, `Viewer`, `Recorder` — public API
- Rigid-body physics: RNEA, CRBA, ABA; semi-implicit Euler
- Collision detection: SAT OBB-OBB, sphere, capsule
- Impulse-based contact solver (Coulomb friction + Baumgarte)
- UR5 6-DOF robot model (FK + Jacobian)
- `RealtimeRenderer` (OpenGL 3.3 + moderngl), `HQRenderer` (software ray-tracer)
- `SceneSnapshot` — physics↔render pure-data contract
- JAX JIT+vmap batch physics (2000× throughput)
- NumPy ↔ JAX backend switch (`ENGINE_BACKEND`)
- 215 automated tests

[Unreleased]: https://github.com/iruki-dev/forge3d/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/iruki-dev/forge3d/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/iruki-dev/forge3d/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/iruki-dev/forge3d/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/iruki-dev/forge3d/compare/v0.4.0...v1.0.0
[0.4.0]: https://github.com/iruki-dev/forge3d/compare/v0.2.0...v0.4.0
[0.2.0]: https://github.com/iruki-dev/forge3d/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/iruki-dev/forge3d/releases/tag/v0.1.0
