# Changelog

All notable changes to forge3d are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## [0.4.0] — 2026-06-03

### Added (P14 — PyPI 배포 인프라)
- GitHub Actions CI 워크플로우 (Python 3.12/3.13, push/PR 자동 테스트)
- GitHub Actions Release 워크플로우 (tag → TestPyPI → PyPI OIDC Trusted Publisher)
- GitHub Actions Docs 워크플로우 (main 브랜치 → GitHub Pages)
- `pyproject.toml` 저자·URL 정비 (`authors`, `project.urls`)
- `[project.optional-dependencies.docs]` — `mkdocs-material`, `mkdocstrings`
- `[tool.hatch.build.targets.sdist]` exclude 패턴 (테스트·앱·문서 제외)
- `.readthedocs.yaml` ReadTheDocs 설정
- `.github/ISSUE_TEMPLATE/` — bug report / feature request 템플릿

### Changed
- Version bump: `0.3.0` → `0.4.0`
- `.gitignore` 확장 (`.states`, `.npz`, `site/`, `*.ppm` 등)

### Added
- `App` class — high-level game-loop abstraction with `@on_start` / `@on_update` / `@on_render` decorators
- `Input` class — per-frame keyboard/mouse state snapshot (`key_held`, `key_pressed`, `key_released`, `mouse_pos`, `mouse_delta`, `scroll_delta`)
- `Key` — named key constant class (`Key.SPACE`, `Key.W`, `Key.ESCAPE`, …)
- `OrbitCamera` — orbit-around-target camera with `rotate()`, `zoom()`, `pan()`, `to_snapshot()`
- `FollowCamera` — smooth camera that tracks a `Body` from a fixed offset
- `world.bodies` property — list of all `Body` handles currently in the world
- `world.remove(body)` — remove a body from the world mid-simulation
- `world.clear()` — remove all dynamic bodies (keep statics if desired)
- `world.get_body(name)` — look up a body by name
- `body.name` — readable name set at creation
- `body.is_static` — True if the body does not move under physics
- `body.mass` — body mass in kg
- `body.apply_force(force)` — accumulate a world-frame force applied during the next `step()`
- `body.apply_torque(torque)` — accumulate a world-frame torque applied during the next `step()`
- `body.set_position(pos)` / `body.set_orientation(quat)` — teleport shortcuts
- `body.set_velocity(vel)` / `body.set_angular_velocity(omega)` — velocity override
- AABB broad-phase pre-filter in `collision.detection` — O(n²) → O(n log n) contact detection
- `src/forge3d/py.typed` — PEP 561 type marker (inline types exported)
- MIT `LICENSE` file
- `CONTRIBUTING.md` — contribution guide

### Changed
- `World.__repr__` now includes body count and gravity vector
- `Body.__repr__` now includes name and velocity magnitude
- `Viewer` now integrates `Input` state; pass `viewer.input` to access current frame
- `pyproject.toml` upgraded to full PyPI metadata: classifiers, keywords, URLs, readme, license

### Improved
- Broad-phase AABB filter reduces GJK calls from O(n²) to only overlapping pairs
- `world.update_body_pose` uses body-id index cache (O(1) lookup instead of O(n) scan)
- `world.apply_impulse` likewise O(1) lookup
- `Viewer.draw()` returns the rendered frame as `ndarray` consistently

---

## [0.2.0] — 2026-05

### Added
- `Shape.capsule(radius, half_length)` — capsule rigid body
- `Shape.convex_mesh(mesh_data)` — convex-hull body from OBJ file
- `world.add_capsule()` / `world.add_mesh()` facade helpers
- `forge3d.io.load_obj(path)` → `MeshData` — pure-Python OBJ parser
- `MeshData.hull_vertices` / `.hull_faces` — precomputed convex hull
- `convex_hull_inertia()` — exact inertia via signed-tetrahedra method
- GJK extended: support functions for "mesh" and "capsule" shapes
- EPA (`collision/epa.py`) — penetration depth + contact normal for intersecting convex bodies
- `gjk_contact()` — public GJK+EPA interface returning `(depth, normal)`
- PBR shader (Cook-Torrance BRDF): GGX NDF, Smith geometry, Fresnel-Schlick
- PCF shadow map upgraded to 2 K resolution
- Reinhard tone mapping + gamma correction
- Albedo texture support: PNG/JPEG via `imageio`
- `Material.texture_path` / `.normal_map_path` fields
- Sample models: `assets/models/cube.obj`, `assets/models/tetrahedron.obj`
- Capsule VAO cached by `(radius, half_length)` key
- Mesh VAO cached by `mesh_id`

### Changed
- Vertex layout: 6 floats → 8 floats `[px, py, pz, nx, ny, nz, u, v]`

---

## [0.1.0] — 2026-03

### Added
- `World`, `Body`, `Shape`, `Material`, `Viewer`, `Recorder` — public API
- Rigid-body physics: RNEA, CRBA, ABA; semi-implicit Euler integrator
- Collision detection: SAT OBB-OBB (15-axis), sphere-sphere, sphere-box,
  capsule-sphere, capsule-box, capsule-capsule
- Impulse-based contact solver with Coulomb friction and Baumgarte correction
- Weld constraints (`world.weld` / `world.release`) for kinematic grasping
- `world.teleport`, `world.apply_impulse`
- UR5 6-DOF robot model with forward kinematics and Jacobian
- `RealtimeRenderer` — OpenGL 3.3 rasteriser via `moderngl` + Xvfb headless
- `HQRenderer` — software ray-tracer (Blinn-Phong, AO, MSAA)
- `SceneSnapshot` — pure-data physics↔renderer contract
- Gymnasium-compatible `ReachEnv` and `PickPlaceEnv`
- JAX JIT+vmap batch physics (`sim/jax_batch.py`) — 2000× throughput
- SHAC: analytic policy gradients via FK auto-diff
- Domain randomisation (`sim/domain_rand.py`)
- NumPy ↔ JAX backend switch via `ENGINE_BACKEND` env-var
- 215 automated tests

[Unreleased]: https://github.com/your-org/forge3d/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/your-org/forge3d/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/your-org/forge3d/releases/tag/v0.1.0
