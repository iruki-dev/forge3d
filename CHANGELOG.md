# Changelog

All notable changes to forge3d are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## [2.1.0] — 2026-06-06 — API completeness and polish

Bug fixes, missing features, and consistency improvements discovered during development.

### Fixed

- **B-1** `add_terrain(material=Material(...))` 커스텀 재질이 스냅샷에 유실되던 문제 — `TerrainSnapshot.material` / `BodySnapshot.material` 필드에 resolved `Material` 객체 직접 포함
- **B-2** `Body.name` 읽기 전용 — `name` setter 추가
- **B-3** `World.restore(path)` 인스턴스 메서드 추가 (in-place 복원); 기존 classmethod `World.load()`는 유지
- deferred renderer `Material.emissive` scalar → `(R,G,B)` 변환 TypeError 수정

### Added

- `Body.shape_type`, `Body.shape_params`, `Body.rotation_matrix` 프로퍼티
- `Body.on_collision_begin(cb)` / `on_collision_end(cb)` 개별 바디 충돌 콜백
- `Material.emissive: float` — 스냅샷 전체 파이프라인 전파
- `Transform.quaternion` `[w,x,y,z]` / `Transform.matrix4` `(4,4)` 프로퍼티
- `TriggerZone.set_position()`, `.set_half_extents()`, `.enabled` 런타임 조작
- `world.raycast_all(origin, dir, max_dist, layer_mask)` — 전체 히트 리스트
- `world.overlap_sphere(center, radius)` / `world.overlap_box(center, half_extents)` 공간 쿼리
- `world.add_terrain(..., friction=0.8, layer=CollisionLayer.TERRAIN)` 파라미터
- `world.step(dt, substeps=1)` 서브스텝 지원
- `world.update(frame_dt)` 고정 타임스텝 누산기 (`world.fixed_dt`, `world.max_substeps`)
- `world.add_character(position, height, radius)` → `CharacterController` (move/jump/glide)
- `world.profiler` → `PhysicsProfiler` — context manager로 step 타이밍 측정
- `JointType` StrEnum (`HINGE`, `BALL`, `PRISMATIC`, `SPRING`, `FIXED`, `DISTANCE`)
- `CollisionLayer.mask_for(*layers)` 비트마스크 헬퍼
- `Viewer(shadow_resolution=N)` — 그림자 해상도 지정; 기본값 512 → **1024**으로 상향

### Changed

- `CollisionLayer.TERRAIN = 0x0008` (기존 `BULLET` 값과 교환; `BULLET = 0x0020`)

---

## [2.0.0] — 2026-06-04  🚀 v2.0 — Python-first 고성능 게임/시뮬레이션 엔진

### 핵심 변화

v2는 세 가지 축으로 v1을 고도화한다:
1. **런타임 성능** — Rust 네이티브 확장 (PyO3 + maturin)으로 물리 핫루프 ≥10× 가속
2. **그래픽 파이프라인** — 지연 PBR + CSM + SSAO + HDR + Bloom (OpenGL 4.3+)
3. **API 생태계** — ECS, 오디오, 애니메이션, 씬 관리, 파티클, UI, 에디터

**v1 API 완전 하위 호환**: `World`, `Body`, `Viewer`, `Recorder` 시그니처 동결.

### Added — P25: Rust 네이티브 확장

- `forge3d._core` — PyO3 + maturin 혼합 빌드 (Rust 1.96+)
- `forge3d._core.gjk_query(verts_a, verts_b)` — GJK + EPA 충돌 감지
- `forge3d._core.bvh_build/bvh_query_pairs` — BVH 광역단계 (N=500에서 22× 향상)
- `forge3d._core.pgs_solve` — PGS 접촉 솔버 Rust 경로
- `forge3d._core.se3_mul/quat_normalize/quat_mul` — SIMD 수학 (glam 기반)
- `USE_RUST_CORE=0/1` 환경변수로 Python 폴백 강제 가능
- `pyproject.toml` 빌드 시스템: `hatchling` → `maturin`

### Added — P26: 모던 렌더링 파이프라인

- `DeferredRenderer` — OpenGL 4.3 지연 렌더링
  - G-Buffer 4채널 (위치/법선/알베도-roughness/emissive-metallic)
  - CSM (Cascaded Shadow Maps) 4 cascade, PCF 9-탭
  - SSAO 64샘플 + blur 패스
  - HDR 프레임버퍼 + ACES 톤맵 + Kawase 블룸
  - 인스턴스 렌더링
- `RenderPass` ABC — 파이프라인 패스 단위 추상
- `forge3d.render.DeferredRenderer` 공개

### Added — P27: Entity Component System

- `EntityWorld` — 엔티티 생성/소멸, 컴포넌트 CRUD, `query()`
- 내장 컴포넌트: `Transform`, `Rigidbody`, `Collider`, `MeshRenderer`, `Script`, `CameraComponent`, `LightComponent`
- `System` ABC + `PhysicsSystem`, `RenderSystem`, `ScriptSystem`
- `body_to_entity()` — v1 Body → ECS 브릿지
- `save_scene() / load_scene()` — ECS 씬 JSON 직렬화
- `EntityNotFoundError` — 소멸된 엔티티 접근 명확한 오류

### Added — P28: 오디오 시스템

- `AudioClip` — WAV/OGG 로드 + `from_sine()` 생성
- `AudioSource`, `AudioListener` — ECS 컴포넌트
- `AudioSystem` — OpenAL 자동 감지, 헤드리스 시 `NullDriver` 폴백
- `AudioSystem.make_collision_handler()` — 충돌 이벤트 → 사운드 트리거 팩토리

### Added — P29: 애니메이션 시스템

- `Skeleton`, `Bone` — 골격 계층, FK 월드 행렬
- `AnimationClip` — 키프레임 LERP/SLERP 보간
- `AnimationPlayer`, `BlendTree` — ECS 컴포넌트
- `FABRIKSolver` — N링크 FABRIK IK (오차 < 1e-4m 수렴)
- `AnimationSystem` — ECS 시스템
- `chain_from_ur5_joints()` — UR5 FK 체인 헬퍼

### Added — P30: 씬 관리

- `SceneNode` — dirty flag 캐시 + 부모/자식 계층
- `Prefab` — JSON save/load/instantiate
- `SceneManager` — load/unload/additive 씬 전환 + 콜백

### Added — P31: 파티클 시스템

- `ParticleEmitter` — ECS 컴포넌트 (rate/lifetime/gravity/restitution)
- `ParticleSystem` — NumPy 벡터화 + JAX vmap 이중 경로 (10만 파티클 < 33ms)
- VFX 프리셋: `sparks`, `smoke`, `debris`, `rain`
- GLSL 4.3 컴퓨트 셰이더 (`update_particles.comp`)

### Added — P32: UI 시스템

- `DebugPanel`, `InspectorPanel`, `HierarchyPanel` — ImGui 패널 (null 폴백)
- `Canvas` — 2D 오버레이 (클리핑, NumPy 래스터화)
- `UISystem` — ECS 시스템

### Added — P33: 씬 에디터

- `EditorApp` — Play/Pause/Step 상태 머신
- `TranslateGizmo` — 레이-구 교차 선택 + 축 드래그
- `EditorLayout` — 3패널 레이아웃
- `screen_to_ray()` — 화면 좌표 → 월드 레이

### Added — P34 (선택): wgpu 백엔드

- `WgpuRenderer` — wgpu-py 기반 오프스크린 렌더러, WGSL PBR 셰이더
- wgpu 없는 환경에서 `DeferredRenderer` 자동 폴백

---

## [1.1.0] — 2026-06-03  🎮 Game-Ready Release

### Added

**Physics API 확장**

- `World.add_box(static=True)` — 정적 박스를 공개 API에서 직접 생성 (기존: 내부 `_physics.add_static_box()` 직접 호출 필요)
- `World.add_capsule(static=True)` — 정적 캡슐 지원
- `World.add_static_box(...)` — 공개 편의 메서드; `world.bodies`에 자동 등록
- `Body.friction` / `Body.restitution` setter — 런타임 마찰·반발 계수 변경
- `Body.linear_damping` / `Body.angular_damping` — 속도 감쇠 계수 (dt 보정 지수 감쇠, `world.step()` 내 자동 적용)
- `World.weld(body, anchor, local_rotation=...)` — 자식 body의 상대 회전 저장 지원
- `World.raycast(origin, direction, max_dist)` → `RayHit(body, point, normal, distance)` — 기본 레이캐스트 API

**렌더링 — Heightfield 지형 시각화**

- `TerrainSnapshot` 데이터클래스 추가 (`forge3d.TerrainSnapshot`)
- `World.add_terrain()` 시 `SceneSnapshot.terrains` 에 자동 포함 → 렌더러에 전달
- `RealtimeRenderer` — heightfield 삼각 메시 생성·렌더링 (shadow pass 포함)
- `WindowRenderer` (apps/game) — 동일 terrain 렌더링 지원
- `render.realtime.meshes.heightfield_mesh(heights, cell_size, origin)` 공개 함수

**카메라**

- `FollowCamera(frame="local")` — 차체 로컬 프레임 오프셋; 차가 회전해도 항상 뒤에서 추적
- `FollowCamera(smoothing_hz=6.0)` — FPS 독립 지수 감쇠 스무딩 (기존 `alpha` per-frame 대체)
- `FollowCamera.to_snapshot(dt=...)` — dt 파라미터로 FPS 독립 스무딩

**입력**

- `forge3d.InputBuilder` — 공개 클래스 (기존: `_InputBuilder` 비공개)
- `InputBuilder` — 공개 클래스로 승격, glfw 콜백과 자동 연결

**Viewer**

- `Viewer.draw_text(text, x, y, size, color, bg_alpha, anchor)` — HUD 텍스트 오버레이

**직렬화**

- `World.save()` — 조인트(Hinge/Spring/Distance/Ball/Fixed/Prismatic) 직렬화 포함
- `World.load()` — 저장된 조인트 자동 복원

### Performance

- `World.step()` 내 `detect_contacts` 이중 호출 제거: physics step의 캐시된 contact를 이벤트 디스패치에서 재활용 → ~2× 이벤트 처리 속도 향상

### Fixed

- `World.add_terrain()` 의 `material` 파라미터가 Heightfield 렌더에 전달되지 않던 문제

---

## [1.0.0] — 2026-06-03  ★ STABLE RELEASE

### Added (P15 — MkDocs 문서 사이트)
- MkDocs Material 테마 기반 문서 사이트 (`mkdocs.yml`, `docs_src/`)
- API 레퍼런스, 튜토리얼 4종, 아키텍처 개요 페이지
- ReadTheDocs 설정 (`.readthedocs.yaml`), GitHub Pages 워크플로우

### Added (P16 — 조인트 & 구속 시스템)
- `forge3d.constraints` 패키지: Sequential Impulse 구속 솔버
- `FixedJoint`, `BallJoint`, `HingeJoint` (모터·한계 포함), `PrismaticJoint`, `DistanceJoint`, `SpringJoint`
- `World.add_joint(type, body_a, body_b, ...)` 통합 API; `World.remove_joint(handle)`
- `forge3d.JointHandle` 핸들 클래스

### Added (P17 — 충돌 이벤트 콜백)
- `forge3d.CollisionEvent`, `forge3d.CollisionHandler`
- `World.on_collision_begin`, `on_collision_stay`, `on_collision_end` 데코레이터
- `World.add_collision_handler(body_a, body_b)` 쌍별 핸들러
- `World.add_trigger_zone(position, size)` 순수 데이터 존 (물리 충돌 없음)
- `World.ignore_collision(body_a, body_b)` 쌍별 충돌 무시

### Added (P18 — 씬 직렬화)
- `World.save(path)` → JSON 저장
- `World.load(path)` 클래스 메서드 → World 복원
- `forge3d.StateRecorder` — 프레임별 상태 기록 + npz 저장/재현

### Added (P19 — 충돌 레이어·마스크)
- `forge3d.CollisionLayer` 비트필드 상수 (`DEFAULT`, `PLAYER`, `ENEMY`, `BULLET` 등)
- `Body.collision_layer`, `Body.collision_mask` 프로퍼티
- `World.ignore_collision()` 쌍 기반 물리 충돌 무시 (physics-level)

### Added (P20 — API 강화)
- `forge3d.errors` 모듈: `Forge3dError`, `ValidationError`, `PhysicsError`, `RenderError`
- `World()`, `add_box()`, `add_sphere()` 인자 검증 (mass > 0, size > 0, restitution ∈ [0,1])
- 친절한 에러 메시지 (`ClassName.method() — param must be ... got param=...`)

### Added (P21 — Heightfield 지형)
- `World.add_terrain(heights, cell_size, origin)` → Heightfield
- 구 vs 높이맵, 박스 vs 높이맵 충돌 감지 (쌍선형 보간)

### Added (P23 — 아일랜드 슬리핑)
- 바디 슬리핑 카운터 (`_sleep_counters`)
- `Body.is_sleeping` 프로퍼티, `PhysicsWorld.wake_body()`

### Changed
- Version bump: `0.4.0` → `1.0.0` (첫 안정 릴리즈)
- pyproject.toml `Development Status :: 5 - Production/Stable`
- Baumgarte 바이어스 부호 수정 (구속 솔버 안정성 대폭 향상)

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
