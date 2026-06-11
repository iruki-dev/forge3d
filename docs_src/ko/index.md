# forge3d

**순수 Python 3D 물리 게임 엔진 — 독자적 동역학, 독자적 규칙, 타협 없음.**

[![PyPI version](https://img.shields.io/pypi/v/pyforge3d.svg)](https://pypi.org/project/pyforge3d/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/iruki-dev/forge3d/blob/main/LICENSE)
[![CI](https://github.com/iruki-dev/forge3d/actions/workflows/ci.yml/badge.svg)](https://github.com/iruki-dev/forge3d/actions/workflows/ci.yml)

---

## forge3d란?

forge3d는 **완전히 Python으로 작성된** 배터리 내장형 3D 물리 게임 엔진입니다 — MuJoCo, PyBullet 등 외부 물리 엔진 없음. 동역학, 충돌 감지, 접촉 해결은 모두 forge3d 자체 코드가 처리하며, NumPy와 선택적 JAX 가속을 지원합니다.

```python
import forge3d as f3d

world = f3d.World(gravity=(0, 0, -9.81))
world.add_ground()
box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)

viewer = f3d.Viewer(world, max_frames=90)
while viewer.is_open:
    world.step(dt=1/60)
    viewer.draw()

print(f"박스 최종 z = {box.position[2]:.2f} m")
```

---

## 핵심 철학

forge3d는 세 가지 원칙을 기반으로 구축됩니다:

1. **물리와 렌더러는 서로를 알지 못합니다.** 유일한 연결고리는 `SceneSnapshot` — 순수 데이터 객체입니다. 물리 코드를 건드리지 않고 렌더러를 교체할 수 있습니다.
2. **외부 물리 엔진을 사용하지 않습니다.** 모든 동역학 알고리즘(RNEA, CRBA, ABA, GJK+EPA, PGS)이 forge3d 자체 코드로 구현되어 있습니다.
3. **Python이 일급 언어입니다.** 모든 사용자 대면 API는 Python입니다. 성능 임계 내부 루프는 선택적으로 JAX JIT 또는 Rust(PyO3)로 네이티브 컴파일됩니다.

---

## 주요 기능

### 물리 코어

| 기능 | 구현 |
|------|------|
| 강체 동역학 | Semi-implicit Euler, 함수형 불변성 |
| 로봇 동역학 | RNEA (Newton-Euler), CRBA (복합강체법), ABA (관절체법) |
| 광역 단계 | AABB 오버랩 컬링 |
| 협역 단계 | SAT (OBB-OBB), GJK+EPA (볼록 형상), 구/캡슐 해석적 처리 |
| 접촉 솔버 | 임펄스 기반 PGS (6회 반복), 쿨롱 마찰, 바움가르테 안정화 |
| 높이맵 지형 | 충돌 + 렌더링 (32×32 ~ 512×512) |
| 조인트 | 힌지, 프리즈마틱, 볼, 고정, 거리, 스프링 |
| 레이캐스트 | `world.raycast()` / `world.raycast_all()` |
| 오버랩 쿼리 | `world.overlap_sphere()` / `world.overlap_box()` |
| 충돌 레이어 | 비트필드 필터링 (PLAYER, ENEMY, TERRAIN, TRIGGER, BULLET, …) |
| 캐릭터 컨트롤러 | 캡슐 바디 + `move()` / `jump()` / `is_grounded` |
| 슬리핑 | 비활성 바디 자동 감지로 건너뜀 |
| 직렬화 | `world.save()` / `world.load()` (JSON, 조인트 포함) |

### 게임 프레임워크

| 기능 | API |
|------|-----|
| 앱 게임 루프 | `App("My World")` + `@app.on_start`, `@app.on_update`, `@app.on_render` |
| 실시간 뷰어 | `Viewer(world)` — 헤드리스(오프스크린) 또는 윈도우 모드 |
| 비디오 레코더 | `Recorder(world, mode="hq")` → MP4/GIF/PNG 시퀀스 |
| 키보드 + 마우스 | `Input.key_held()`, `key_pressed()`, `mouse_delta()`, `scroll_delta()` |
| 카메라 컨트롤러 | `OrbitCamera`, `FollowCamera` (월드 또는 바디 로컬 프레임) |
| HUD 텍스트 오버레이 | `viewer.draw_text(text, x, y, size, color, anchor)` |
| 물리 프로파일러 | `world.profiler` 컨텍스트 매니저 → `PhysicsProfile` 타이밍 데이터 |

### 고급 시스템 (v2.0+)

| 시스템 | 주요 클래스 |
|--------|-------------|
| 엔티티-컴포넌트 (ECS) | `EntityWorld`, `Transform`, `Rigidbody`, `MeshRenderer`, `Script`, `PhysicsSystem` |
| 골격 애니메이션 | `Skeleton`, `AnimationClip`, `AnimationPlayer`, `BlendTree`, `FABRIKSolver` |
| 3D 오디오 | `AudioSystem`, `AudioSource`, `AudioListener`, `AudioClip` (WAV/OGG) |
| 파티클 시스템 | `ParticleEmitter`, `ParticleSystem` + 프리셋(`sparks`, `smoke`, `rain`) |
| 씬 관리 | `SceneManager`, `SceneNode`, `Prefab` |
| 인엔진 에디터 | `EditorApp` — 플레이/일시정지/스텝, 트랜스폼 기즈모 |
| UI 오버레이 | `Canvas`, `DebugPanel`, `InspectorPanel`, `HierarchyPanel` |

### 렌더링

| 렌더러 | 모드 | 설명 |
|--------|------|------|
| `RealtimeRenderer` | 헤드리스 | OpenGL 3.3 (moderngl), PBR, PCF 그림자 — 오프스크린 FBO |
| `WindowedRealtimeRenderer` | 윈도우 | glfw OS 창, 실시간 입력, HUD 텍스트 캐싱 |
| `DeferredRenderer` | 헤드리스 | OpenGL 4.3, G-버퍼, SSAO, CSM 그림자, 블룸 + ACES 톤매핑 |
| `HQRenderer` | 오프라인 | NumPy 소프트웨어 레이트레이서, Blinn-Phong + 앰비언트 오클루전 |

### 성능

| 기법 | 효과 |
|------|------|
| JAX JIT + `vmap` | 배치 RL 롤아웃 2,000× 처리량 향상 |
| AABB 광역 단계 | 충돌 쌍 검사 ~80% 건너뜀 |
| 접촉 캐시 | 중복 쌍 감지 억제 |
| 바디 슬리핑 | 정지 객체 물리 연산 건너뜀 |
| Rust PyO3 코어 (선택) | 네이티브 속도 PGS 솔버, GJK/EPA, BVH |

---

## 설치

```bash
pip install pyforge3d                # 코어 (물리만)
pip install "pyforge3d[render]"      # + 실시간 & HQ 렌더링
pip install "pyforge3d[rl]"          # + Gymnasium / SB3 RL 환경
pip install "pyforge3d[all]"         # 전체
```

!!! note "패키지명 vs 임포트명"
    PyPI 배포명은 `pyforge3d`이지만, 코드에서는 항상 `import forge3d`를 사용합니다.

→ [전체 설치 가이드](install.md)

---

## 빠른 예제

=== "낙하하는 박스"

    ```python
    import forge3d as f3d

    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground()
    box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)

    viewer = f3d.Viewer(world, max_frames=180)
    while viewer.is_open:
        world.step(dt=1/60)
        viewer.draw()

    print(f"박스 착지 위치 z = {box.position[2]:.3f} m")
    ```

=== "앱 게임 루프"

    ```python
    import forge3d as f3d

    app = f3d.App("물리 샌드박스", width=1280, height=720)
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

=== "HQ 비디오"

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

=== "ECS 씬"

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
    print(f"엔티티 z = {tf.position[2]:.3f}")
    ```

---

## 빠른 링크

- [**설치 가이드**](install.md) — pip, 선택적 extras, 헤드리스 환경
- [**빠른 시작**](quickstart.md) — 15줄로 작동하는 예제 4개
- [**물리 튜토리얼**](tutorials/01_physics.md) — 중력, 충돌, 조인트, 레이캐스트
- [**렌더링 튜토리얼**](tutorials/02_rendering.md) — 카메라, 재질, 지형, HUD
- [**API 레퍼런스**](../api/world.md) — 전체 클래스·메서드 문서 (영문)
- [**아키텍처**](architecture.md) — SceneSnapshot 계약, 모듈 맵, 설계 원칙
- [**변경 내역**](changelog.md)
