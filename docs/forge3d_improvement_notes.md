# forge3d 개선 필요 사항

> **작성 기준**: `apps/desert_journey/` 개발 중 실제로 마주한 버그·누락·불일치를 정리한 문서.
> 각 항목은 **증거**(실제 코드/에러), **영향**, **제안 API**를 함께 기술한다.

---

## 버그 (Bug)

### B-1. `add_terrain()` 커스텀 Material이 스냅샷에 보존되지 않음

**심각도**: 높음 — 렌더러-물리 연동의 핵심 계약 위반

**재현**
```python
world.add_terrain(
    heights=h, cell_size=5.0, origin=(-240,-240,0),
    material=f3d.Material(color=(0.78,0.60,0.32), roughness=0.92,
                          texture_path="sand.png"),
)
snap = world.snapshot()
terrain_snap = list(snap.terrains)[0]
# terrain_snap.material_id → 'custom#c69951_3fd7'
# BUILTIN_MATERIALS.get('custom#c69951_3fd7') → None  ← 여기서 깨짐
```

**원인**: `add_terrain(material=Material(...))` 시 내부에서 해시 기반 ID(`custom#...`)가 생성되지만,
해당 Material 객체가 `BUILTIN_MATERIALS` 딕셔너리에 등록되지 않는다.
스냅샷 소비자(렌더러)는 ID만 받아 조회하므로 항상 `None`을 반환받는다.

**우회책** (desert_journey에서 적용):
렌더러가 `material_id`를 무시하고 직접 색상 하드코딩.

**제안 수정**:
```python
# Option A: Material 객체를 스냅샷에 직접 포함
@dataclass
class TerrainSnapshot:
    heights:     np.ndarray
    cell_size:   float
    origin:      tuple
    material:    Material          # ← material_id 대신 실물 저장
    material_id: str               # ← 하위 호환용으로 유지

# Option B: 커스텀 Material을 자동으로 전역 레지스트리에 등록
# add_terrain()에서 BUILTIN_MATERIALS["custom#..."] = material 등록
```

---

### B-2. `Body.name` 읽기 전용 (setter 없음)

**심각도**: 보통

**재현**
```python
head = world.add_sphere(radius=0.21, ..., name="head")
head.name = "player_head"   # AttributeError: property 'name' has no setter
```

**영향**: 생성 이후 이름 변경 불가. 특히 `world.weld()`로 접합된 서브 바디를 나중에
재명명해야 할 때 코드 구조가 어색해진다.

**제안 수정**:
```python
@name.setter
def name(self, value: str) -> None:
    self._name = value
```

---

### B-3. `world.save()` / `world.load()` — Body가 직렬화되지 않음

**심각도**: 높음 — 문서에 저장/복원 기능으로 표시되어 있지만 실제로는 공 상태만 저장됨

**재현**
```python
world = f3d.World()
world.add_box(size=(1,1,1), position=(0,0,5), mass=1.0)
world.save("/tmp/test.json")

world2 = f3d.World()
world2.load("/tmp/test.json")
len(list(world2.bodies))   # → 0  (기대값: 1)
```

**제안**: `save()/load()`가 모든 Body (위치, 형상, 질량, 이름, 재질)를 JSON으로 완전 직렬화.

---

## 누락된 기능 (Missing Feature)

### M-1. `TriggerZone` 이동/리사이즈 불가

**현황**: `TriggerZone`은 생성 시 위치·크기 고정. `set_position()` 없음.

**요구 사례**: 플레이어가 수집한 fragment가 사라진 뒤 해당 트리거 영역을 비활성화하거나
이동시키고 싶을 때.

```python
zone.position         # 읽기 가능 (ndarray)
zone.set_position(p)  # ← 없음
zone.half_extents     # 읽기 가능
zone.set_enabled(False)  # ← 없음 (활성화 토글)
```

**제안 API**:
```python
zone.set_position(position: ArrayLike) -> None
zone.enabled: bool          # getter / setter
zone.half_extents = (…)     # setter 추가
```

---

### M-2. `Body.on_collision` 이벤트 (개별 바디 수준)

**현황**: 충돌 콜백은 `world.on_collision_begin(handler)` 처럼 전역 수준만 있다.
특정 Body의 충돌을 선택적으로 구독하려면 핸들러 내부에서 직접 필터링해야 한다.

**요구 사례**: 플레이어 바디에서 특정 오브젝트(fragment, 벽)와의 충돌만 감지.

```python
# 현재 우회 방식
@world.on_collision_begin
def _all(a, b, contact):
    if a.name == "player" or b.name == "player":
        ...  # 수동 필터링

# 원하는 API
@player_body.on_collision_begin
def _player_hit(other, contact):
    ...
```

**제안 API**:
```python
Body.on_collision_begin(callback: Callable[[Body, ContactInfo], None]) -> None
Body.on_collision_end(callback: …) -> None
```

---

### M-3. `Body` 형상(Shape) 쿼리 불가

**현황**: 생성 후 바디의 형상 종류(box/sphere/capsule)와 파라미터를 읽을 수 없다.
`BodySnapshot.shape_type`, `BodySnapshot.shape_params`는 스냅샷에만 있고 라이브 바디에는 없다.

```python
b = world.add_capsule(radius=0.5, half_length=1.0, position=(0,0,5))
b.shape_type    # ← AttributeError
b.shape_params  # ← AttributeError
```

**요구 사례**: 물리 바디 기반 자동 충돌 시각화, 디버그 렌더러 구현 시 필요.

**제안 API**:
```python
body.shape_type:   str                  # 'box' | 'sphere' | 'capsule' | 'mesh' | 'terrain'
body.shape_params: dict[str, Any]       # {'size': (1,1,1)} 등
```

---

### M-4. `Material.emissive` — 스냅샷에 포함 안 됨

**현황**: `Material` 객체에 `emissive` 속성을 직접 설정할 수 있고 (`mat.emissive = 2.0`)
setter도 작동하지만, 스냅샷(`TerrainSnapshot`, `BodySnapshot`)의 `material_id`를 통해
복원한 `BUILTIN_MATERIALS` Material은 emissive를 지원하지 않는다.

**영향**: 렌더러가 스냅샷 기반으로 glowing 오브젝트를 표현할 수 없다.
desert_journey 렌더러는 `RenderObject.emissive`를 별도 필드로 유지하는 방식으로 우회.

**제안**:
```python
@dataclass
class Material:
    color:           tuple[float, float, float] = (0.5, 0.5, 0.5)
    roughness:       float  = 0.5
    metallic:        float  = 0.0
    emissive:        float  = 0.0       # ← 렌더 파이프라인 전체에 전파
    texture_path:    str | None = None
    normal_map_path: str | None = None
```

---

### M-5. `Snapshot` 기반 렌더러를 위한 `BodySnapshot` orientation 불일치

**현황**: 라이브 `Body`는 쿼터니언(`[w, x, y, z]`)을 반환하지만
`BodySnapshot.transform`은 3×3 회전 행렬을 반환한다.

```python
# Live body
body.orientation  # → np.array([w, x, y, z])   쿼터니언

# Snapshot
body_snap.transform.rotation  # → np.ndarray (3,3)  회전 행렬
body_snap.transform.position  # → np.ndarray (3,)   위치
```

**영향**: 스냅샷 기반 렌더러는 한 경로로 쿼터니언을 빌드하고,
라이브 바디 기반 렌더러는 다른 경로로 행렬을 직접 구성해야 한다.
desert_journey 렌더러는 라이브 바디에서 쿼터니언을 읽어 행렬로 직접 변환하는 방식 사용.

**제안**: 두 인터페이스 통일
```python
# Transform 클래스에 quaternion 프로퍼티 추가
transform.quaternion  # → np.array([w, x, y, z])

# 또는 live Body에 rotation_matrix 추가
body.rotation_matrix  # → np.ndarray (3,3)
```

---

### M-6. `world.raycast()` — 다중 히트 (Multi-hit) 미지원

**현황**: `world.raycast()`는 가장 가까운 단일 히트만 반환한다.

```python
result = world.raycast(origin=..., direction=..., max_dist=50.)
# result: RayHit | None  ← 단일 결과만
```

**요구 사례**: 투명 오브젝트 투과, 레이건 관통, 지형 높이 샘플링(복수 레이).

**제안 API**:
```python
world.raycast(origin, direction, max_dist=inf) -> RayHit | None  # 현행 유지
world.raycast_all(origin, direction, max_dist=inf,
                  layer_mask=CollisionLayer.ALL) -> list[RayHit]  # 신규
```

---

### M-7. `world.overlap_sphere()` / `world.overlap_box()` 미존재

**현황**: 특정 공간 영역에 겹치는 바디 목록을 즉시 조회하는 API 없음.

**요구 사례**: 폭발 범위 내 바디 일괄 적용, AI 시야각 감지, 플레이어 근처 오브젝트 수집.

**제안 API**:
```python
world.overlap_sphere(center: ArrayLike, radius: float,
                     layer_mask=CollisionLayer.ALL) -> list[Body]
world.overlap_box(center: ArrayLike, half_extents: ArrayLike,
                  orientation: ArrayLike | None = None,
                  layer_mask=CollisionLayer.ALL) -> list[Body]
```

---

### M-8. `Body.set_position()` 작동하지만 문서에 없음 / `world.teleport()` 와 의미 중복

**현황**: `Body.set_position(pos)`는 실제로 존재하고 동작하지만 공식 문서/API 레퍼런스에 없다.
`world.teleport(body, pos)`와 동일한 역할을 한다.

**제안**: 둘 중 하나를 deprecated 처리하거나, `teleport`는 속도·각속도까지 초기화하는
"완전 리셋"으로, `set_position`은 순수 위치 이동으로 의미를 명확히 구분.

---

### M-9. `CollisionLayer` — 숫자 값이 공개 API에 노출되지 않음

**현황**: `CollisionLayer.PLAYER = 2` 처럼 정수 값이 있지만, 레이어 간 비트마스크 연산
방법이 불분명하다.

```python
body.collision_layer = CollisionLayer.PLAYER
body.collision_mask  = 0   # 아무것도 충돌 안 함
# 이것이 '레이어 PLAYER, 마스크 0(충돌 없음)'을 의미하는지
# 또는 '마스크 0이면 layer 설정 무의미'인지 동작이 불명확
```

**제안**: 공식 비트마스크 표를 문서화하고, 헬퍼 제공:
```python
CollisionLayer.mask_for(*layers) -> int
# CollisionLayer.mask_for(CollisionLayer.TERRAIN, CollisionLayer.PLAYER) → 0b1010
```

---

### M-10. `world.add_terrain()` — 런타임 높이 업데이트 미지원

**현황**: 지형 생성 후 높이맵을 변경할 수 없다.

**요구 사례**: 동적 모래 변형, 충격에 의한 지형 변형 시뮬레이션.

**제안 API**:
```python
terrain_body.update_heights(heights: np.ndarray) -> None
```

---

## API 개선 제안 (Enhancement)

### E-1. `Body` 생성 API — 키워드 인수 일관성

현재 `add_box`, `add_sphere`, `add_capsule`의 키워드 인수 이름이 일부 다르다.

| 기능 | add_box | add_sphere | add_capsule |
|------|---------|------------|-------------|
| 위치 | `position` | `position` | `position` ✓ |
| 정적 | `static=True` | `static=True` | `static=True` ✓ |
| 반지름 | — | `radius` | `radius` ✓ |
| 길이 | — | — | `half_length` (절반값 주의) |

`add_capsule(half_length=...)` 에서 `half_length`인지 `length`인지 직관적이지 않다.
total length를 받는 `length=` 오버로드 추가 또는 명칭을 `length=`로 통일 제안.

---

### E-2. `BodySnapshot` — `orientation` 쿼터니언 직접 노출

M-5와 연계. 스냅샷 기반 렌더러 작성 시 `transform.rotation` (3×3)을 매번 쿼터니언으로
역변환하는 번거로움 제거.

```python
# 제안
body_snap.transform.quaternion  # → np.array([w, x, y, z])
body_snap.transform.matrix4     # → np.ndarray (4,4) model matrix (column-major ready)
```

---

### E-3. 충돌 이벤트 `ContactInfo` 구조체 강화

현재 `on_collision_begin(body_a, body_b, contact)` 에서
`contact` 객체의 구조가 불분명하다(공식 문서 없음).

**제안**:
```python
@dataclass
class ContactInfo:
    point:       np.ndarray      # 충돌 지점 world 좌표
    normal:      np.ndarray      # 충돌 법선 (body_a 기준 outward)
    depth:       float           # 관통 깊이 (m)
    impulse:     float           # 충격량 (N·s)
    relative_vel: np.ndarray     # 상대 속도 (m/s)
```

---

### E-4. `world.add_terrain()` — 높이맵 외 추가 형상 파라미터

현재 지형은 높이맵(grid)만 지원. Journey 같은 게임에서 유용한 기능:

```python
world.add_terrain(
    heights: np.ndarray,
    cell_size: float,
    origin: tuple,
    material: Material | str,
    friction: float = 0.8,       # ← 지형별 마찰계수 없음
    layer: CollisionLayer = CollisionLayer.TERRAIN,  # ← 레이어 지정 불가
)
```

---

### E-5. `world.step()` — 서브스텝 지원

고속 물체(총알, 슈팅)나 부드러운 물리를 위해 한 프레임을 여러 서브스텝으로 나눠 처리:

```python
world.step(dt: float, substeps: int = 1) -> None
# substeps=4 이면 dt/4 간격으로 4번 내부 스텝
```

현재 우회: `for _ in range(4): world.step(dt/4)` — 콜백이 4번 호출되는 부작용 있음.

---

## 렌더러 관련 (Renderer API)

### R-1. `snapshot.bodies`의 `BodySnapshot`에 렌더링에 필요한 정보가 부족

desert_journey는 forge3d 기본 렌더러를 전혀 사용하지 않고 moderngl로 직접 구현했다.
그 이유: 기본 렌더러는 박스·구·캡슐 모양만 그릴 수 있고, 커스텀 메시 지원이 없기 때문.

**제안**: `world.add_mesh()` API 확장:
```python
world.add_mesh(
    vertices:   np.ndarray,   # (N,8) — pos·normal·uv
    indices:    np.ndarray,   # (M,) uint32
    position:   ArrayLike,
    mass:       float = 0.0,  # 0 = static
    material:   Material | str = "default",
    name:       str = "",
)
```

그리고 `BodySnapshot.shape_type == 'mesh'`일 때 `shape_params['vertices']`,
`shape_params['indices']`가 제공되어야 스냅샷 기반 렌더러가 커스텀 메시를 그릴 수 있다.

---

### R-2. 내장 렌더러 — GPU 인스턴싱 미지원

내장 `RealtimeRenderer`는 각 바디를 개별 draw call로 처리한다.
desert_journey에서 120개 기둥/바위/아치를 인스턴싱 없이 그리면 Intel UHD 620 기준 3~4 FPS.

GPU 인스턴싱 API:
```python
renderer.add_instance_group(
    mesh_key:   str,           # 'column_14m' 등 고유 메시 ID
    verts:      np.ndarray,
    indices:    np.ndarray,
    transforms: list[np.ndarray],  # 각 인스턴스의 4×4 모델 행렬
    material:   Material,
) -> None
```

---

### R-3. 내장 렌더러 — 다중 포인트 라이트 미지원

desert_journey는 글로잉 fragment 오브젝트 등 8개의 포인트 라이트를 사용했으나
내장 렌더러는 방향성 광원(sun) 1개만 지원한다.

**제안 API**:
```python
renderer.add_point_light(position, color, radius) -> LightHandle
renderer.remove_point_light(handle: LightHandle) -> None
renderer.set_ambient(sky_color, ground_color) -> None  # hemisphere ambient
```

---

---

# 게임엔진 관점 개선 제안

> **작성 기준**: 위 desert_journey 개발 경험을 넘어, forge3d의 **전체 모듈 구조**를
> 직접 탐색한 결과를 바탕으로 작성한다.
> 실제로 모듈이 존재하더라도 게임 제작자가 실용적으로 사용하기 어려운 경우
> "구현 미완성(Stub)" 또는 "통합 누락"으로 분류한다.

---

## 1. 가장 큰 구조적 문제: ECS ↔ 물리 통합 부재

### G-1. `EntityWorld`와 `PhysicsWorld`가 연결되지 않음

**현황**

forge3d는 두 개의 독립적인 세계 표현을 가진다.

```
forge3d.sim.world.PhysicsWorld   ← World/Body façade가 감싸는 실물
forge3d.ecs.entity.EntityWorld   ← ECS 엔티티 컨테이너
```

두 시스템은 **서로를 전혀 모른다**. `EntityWorld`의 소스에 `forge3d.sim`이
import되어 있지 않고, `PhysicsWorld`에도 ECS import가 없다.
결과적으로 `AnimationSystem`, `ParticleSystem`, `AudioSystem`이 모두 ECS
시스템으로 구현되어 있지만, 이들을 물리 시뮬레이션과 함께 쓰려면
개발자가 직접 매 프레임 양쪽 `update()`를 순서대로 호출하고 위치를 동기화해야 한다.

**영향**

desert_journey는 ECS를 전혀 사용하지 않고 순수하게 facade World + 직접 구현으로
오디오·파티클·애니메이션을 회피했다. 이 연결이 없으면 고수준 서브시스템들은
실용적으로 사용 불가능하다.

**제안 설계**

```python
# 방안 A: GameWorld — ECS + 물리를 하나의 클래스로 통합
class GameWorld:
    def __init__(self, gravity=(0,0,-9.81)):
        self._physics = PhysicsWorld(gravity)
        self._ecs     = EntityWorld()
        self._systems = SystemPipeline()

    def create_entity(self, name="") -> Entity: ...
    def add_physics_body(self, entity: Entity, shape, **kwargs) -> Body: ...
    # Entity가 삭제되면 Body도 함께 삭제

    def step(self, dt: float) -> None:
        self._physics.step(dt)          # 물리
        self._sync_transforms()         # 물리 → ECS Transform 동기화
        self._systems.update(self._ecs, dt)  # 애니메이션, 파티클, 오디오…

# 방안 B: PhysicsBody ECS 컴포넌트 추가 (기존 World 유지)
class PhysicsBody(Component):
    def __init__(self, body: Body):
        self.body = body  # live Body ref
    @property
    def position(self): return self.body.position
    @position.setter
    def position(self, v): self.body.set_position(v)
```

---

## 2. 렌더러 아키텍처

### G-2. 렌더러가 3개인데 통합 인터페이스 없음

현재 forge3d에는 렌더러가 3개 있다.

| 렌더러 | 파일 | 상태 |
|--------|------|------|
| `RealtimeRenderer` | `render/realtime/renderer.py` | 완성, 헤드리스 전용 |
| `WindowRenderer` (pygame) | `render/realtime/window_renderer.py` | 완성, `Viewer`가 사용 |
| `DeferredRenderer` | `render/deferred/renderer.py` | **스텁** — `render()` 내부 대부분 `pass` |
| `WGPURenderer` | `render/wgpu_backend/renderer.py` | **임포트 불가** — 클래스명 불일치 |

**G-2a. DeferredRenderer 미완성 (스텁 8곳)**

```python
# render/deferred/renderer.py 실제 코드
def _gbuffer_pass(self, ctx, snapshot, vp, cam_pos):
    ...
    pass   # ← 미구현
def _ssao_pass(self, ctx, ...):
    pass   # ← 미구현
def _lighting_pass(self, ctx, ...):
    pass   # ← 미구현
```

기획된 CSM 4단계 + SSAO + GGX PBR 파이프라인이 모두 비어 있다.
이 렌더러를 실제로 사용할 수 없다.

**G-2b. WGPURenderer 임포트 불가**

```python
from forge3d.render.wgpu_backend.renderer import WGPURenderer
# ImportError: cannot import name 'WGPURenderer'
# (파일 내에는 Renderer를 상속한 클래스가 있지만 이름이 다름)
```

**제안**: 세 렌더러가 공통 기반 클래스(`Renderer`)를 상속하는 구조는 올바르다.
DeferredRenderer와 WGPURenderer를 실제로 완성하거나, 완성 전까지
`NotImplementedError`를 명시적으로 raise해 사용자 혼란을 방지해야 한다.

---

### G-3. 내장 WindowRenderer가 pygame에 의존

**현황**: `Viewer` → `WindowRenderer` → **pygame** + moderngl 조합.
pygame은 게임 개발 용도로 많이 쓰이지만 forge3d의 "고성능 게임 엔진" 포지셔닝과
어울리지 않는다. 특히 창 생성 및 입력을 pygame이 담당하므로:

- `Input.key_pressed()` 반환값이 pygame 상수 (`K_w`, `K_space` 등) 기반
- desert_journey처럼 GLFW를 직접 사용하면 `Input` 시스템을 전혀 활용할 수 없음
- 멀티 창 렌더링, 고DPI 처리가 pygame에 제한됨

**제안**: GLFW 백엔드를 1급 지원으로 추가하고,
`Viewer(backend="glfw")` 또는 `Viewer(backend="pygame")`으로 선택 가능하게 한다.

```python
class WindowBackend(Protocol):
    def create_window(self, w, h, title) -> Any: ...
    def swap_buffers(self) -> None: ...
    def poll_events(self) -> InputState: ...
    def should_close(self) -> bool: ...

class GLFWBackend(WindowBackend): ...   # glfw-python
class PygameBackend(WindowBackend): ... # 기존 유지
```

---

### G-4. 내장 렌더러 — 그림자 해상도 512²로 너무 낮음

`window_renderer.py`:
```python
_SHADOW_SIZE = 512   # 너무 작아 근거리 그림자에 픽셀화 심각
```

반면 `renderer.py`(헤드리스)는 2048²를 사용한다.
windowed 렌더러도 옵션으로 해상도 변경 가능해야 한다.

```python
Viewer(shadow_resolution=1024)  # 기본값 상향 + 사용자 지정
```

---

## 3. 물리 엔진

### G-5. 물리 스텝 고정 간격(Fixed Timestep) 미지원

**현황**: `world.step(dt)` 는 가변 `dt`를 그대로 적분기에 넘긴다.
게임에서 물리 시뮬레이션이 안정적이려면 고정 간격(예: 1/120 s) 반복 + 잔여 시간
누적 패턴이 필요하다.

```python
# 현재 코드 (가변)
world.step(0.016)  # 16ms 프레임
world.step(0.033)  # 33ms 프레임 → 결과가 달라짐
```

**제안**:
```python
# 방안 A: World 자체에서 고정 스텝 관리
world = f3d.World(fixed_dt=1/120, max_substeps=8)
world.update(frame_dt)  # 내부에서 accumulated_t += frame_dt; while > fixed_dt: step()

# 방안 B: 기존 step() 유지 + 헬퍼
f3d.fixed_update(world, frame_dt, fixed_dt=1/120)
```

---

### G-6. 연속 충돌 감지(CCD) 미지원

**현황**: 현재 충돌 감지는 이산(Discrete)이다.
빠른 물체(총알, 빠른 낙하 물체)가 얇은 벽을 관통한다.

**제안**: 선형 CCD (swept sphere/box) 옵션 추가.
```python
body.ccd_enabled = True   # 해당 바디에 CCD 활성화
body.ccd_threshold = 0.5  # 이 속도(m/s) 이상일 때만 CCD 적용
```

---

### G-7. 동적 지형 충돌 (Dynamic Heightfield) 미지원

**현황**: `add_terrain()`으로 추가된 지형은 수정 불가 (M-10과 연계).
지형 변형 시뮬레이션, 눈/모래 변형 효과에 필요하다.

---

### G-8. 관절(Joint) 타입 다양성 부족

`world.add_joint(joint_type, ...)` 의 `joint_type` 문자열이 어떤 값을 지원하는지
문서나 에러 메시지에 명시되어 있지 않다.
소스를 직접 확인해야 `'hinge'`, `'ball'`, `'slider'` 등을 알 수 있다.

**제안**: 타입 안전한 열거형 + 명확한 문서:
```python
class JointType(str, Enum):
    HINGE   = "hinge"   # 1-DOF 회전 (경첩, 바퀴)
    BALL    = "ball"    # 3-DOF 회전 (어깨, 볼-소켓)
    SLIDER  = "slider"  # 1-DOF 직선 이동 (피스톤)
    FIXED   = "fixed"   # 0-DOF (단단한 연결)
    SPRING  = "spring"  # 탄성 거리 유지

world.add_joint(JointType.HINGE, body_a, body_b, axis=(0,0,1), limits=(-90,90))
```

---

## 4. 캐릭터 컨트롤러 (Character Controller)

### G-9. 캐릭터 컨트롤러 미존재

**현황**: 플레이어 캐릭터를 만들려면 매번 아래를 직접 구현해야 한다.
- 지면 감지 (ray 또는 높이 비교)
- velocity 기반 이동 (force 방식은 조작감 불량)
- 경사면 슬라이딩
- 점프 / 글라이드
- 자동 직립 유지
- 계단 자동 오르기

desert_journey에서 `player.py` 전체(200줄)가 이를 구현한다.

**제안**: 내장 CharacterController 컴포넌트.

```python
cc = world.add_character(
    position = (0, 0, 2),
    height   = 1.8,       # 캡슐 높이
    radius   = 0.3,       # 캡슐 반지름
    mass     = 70.0,
)

# 매 프레임
cc.move(direction=(dx, dy), speed=5.5, dt=dt)    # 수평 이동
cc.jump(impulse=6.4)                              # 점프
cc.glide(target_fall_speed=-0.5, dt=dt)           # 글라이드

# 상태 쿼리
cc.is_grounded   # bool
cc.is_airborne   # bool
cc.velocity      # ndarray(3,)
```

---

## 5. 고급 파티클 / VFX

### G-10. 파티클 시스템 — 렌더 통합 없음

**현황**: `ParticleSystem`은 파티클 위치 버퍼를 업데이트하지만,
이 버퍼를 실제로 **화면에 그리는 방법이 없다**.

- `RealtimeRenderer`는 파티클 렌더를 지원하지 않는다.
- `WindowRenderer`도 동일.
- ECS `ParticleSystem.update()`가 `buf` 배열을 계산하지만 렌더러에 전달하는 경로가 없다.

**제안**:
1. `SceneSnapshot`에 `ParticleSnapshot` 추가:
   ```python
   @dataclass
   class ParticleSnapshot:
       positions:  np.ndarray   # (N_alive, 3)
       colors:     np.ndarray   # (N_alive, 4)  RGBA
       sizes:      np.ndarray   # (N_alive,)    world-space radius
   ```
2. 렌더러에 `render_particles()` 패스 추가 (billboard sprite, 뎁스 write 없음)

---

### G-11. 파티클 — 물리 상호작용 없음

파티클이 지형·오브젝트와 충돌하거나 바람(trigger_zone)의 영향을 받는 방법이 없다.
최소한 `TriggerZone`에 들어온 파티클에 force field를 적용하는 기능이 필요하다.

```python
emitter.add_force_field(zone=wind_zone, force=(0,0,15))  # 위쪽 방향 가속
emitter.collide_with_terrain = True    # 지면 바운스
```

---

## 6. 애니메이션 시스템

### G-12. 표준 3D 애니메이션 파일 형식 미지원

**현황**: `AnimationClip`은 키프레임 딕셔너리를 직접 구성해야 한다.
외부 툴(Blender, Maya)에서 제작한 애니메이션을 사용할 수 없다.

```python
# 현재: 수동 키프레임 구성
clip = AnimationClip(keyframes={
    0.0: {"RootBone": np.eye(4)},
    0.5: {"RootBone": rotation_matrix(...)},
})

# 원하는 것: 파일 로드
clip = AnimationClip.load("character_walk.glb")  # gltf 스킨 애니메이션
clip = AnimationClip.load("jump.bvh")             # BVH 모션 캡처
```

**제안**: glTF 2.0 스킨 애니메이션 로더 및 BVH 로더 추가.

---

### G-13. 애니메이션 블렌딩 트리 — 상태 머신 연동 없음

`AnimationPlayer.blend_tree`는 존재하지만 게임 로직에서 자연스럽게
"이동 중 → walk 애니메이션, 정지 → idle, 점프 → jump" 전환을 구현하려면
별도 FSM을 작성해야 한다.

**제안**: 내장 애니메이션 상태 머신:
```python
class AnimStateMachine:
    def add_state(self, name, clip, loop=True): ...
    def add_transition(self, from_, to, condition: Callable[[], bool],
                       blend_time=0.2): ...
    def update(self, dt): ...

# 사용
fsm = AnimStateMachine(player)
fsm.add_state("idle",  idle_clip)
fsm.add_state("walk",  walk_clip)
fsm.add_transition("idle", "walk", lambda: player.speed > 0.1)
fsm.add_transition("walk", "idle", lambda: player.speed < 0.1)
```

---

## 7. 오디오 시스템

### G-14. 오디오 — Facade API에서 접근 불가

**현황**: `AudioSystem`은 ECS 시스템으로만 구현되어 있다.
`f3d.World`를 사용하는 개발자는 `AudioSystem`을 사용할 방법이 없다.
desert_journey에서 오디오를 전혀 구현하지 못한 직접적 이유이다.

```python
# ECS 없이는 오디오 사용 불가
# world.play_sound(...)  ← 없음
# world.add_audio_source(...)  ← 없음
```

**제안**: Facade World에 오디오 서브시스템 직접 통합:
```python
world = f3d.World()
world.audio.play("wind.ogg", position=(x,y,z), volume=0.8, loop=True)
world.audio.play_global("music.ogg", volume=0.5, loop=True)
world.audio.set_listener(position, orientation)  # 카메라 위치로 설정
```

---

### G-15. 3D 공간 오디오 — 거리 감쇠 모델 불명확

`AudioSystem.play_at(pos, clip, volume)`은 존재하지만
거리 감쇠 공식(linear, inverse square, logarithmic)이 어떤 것인지 문서에 없다.
특히 `AudioListener` 위치를 설정하는 방법이 직관적이지 않다.

---

## 8. 씬 시스템

### G-16. 씬 저장/복원이 Body를 직렬화하지 않음 (B-3과 연계)

`world.save()` → 빈 JSON. `SceneManager.load_scene()` → ECS 엔티티만 복원.
물리 오브젝트(바닥, 벽, 동적 바디)가 함께 저장되지 않아 씬 시스템이 실질적으로 무용하다.

**완전한 씬 저장 포맷 제안**:
```json
{
  "version": "2.0",
  "world": {
    "gravity": [0, 0, -9.81],
    "bodies": [
      {
        "name": "floor",
        "shape": "box",
        "size": [20, 20, 1],
        "position": [0, 0, 0],
        "static": true,
        "material": {"color": [0.7, 0.6, 0.4], "roughness": 0.9}
      }
    ],
    "terrain": { "cell_size": 5.0, "origin": [-240,-240,0], "heights_file": "heights.npy" }
  },
  "ecs": { "entities": [...] }
}
```

---

### G-17. Prefab 시스템 미완성

`forge3d/scene/prefab.py`가 존재하지만 `World.instantiate_prefab()` 같은
facade 수준 API가 없다. Prefab을 실제로 "씬에 배치"하는 흐름이 ECS로만 가능하다.

**제안**:
```python
# prefab.json에 bodies + ecs components 포함
prefab = f3d.Prefab.load("column_ruin.prefab")
instance = world.instantiate(prefab, position=(10, 20, 0), scale=1.5)
# 반환: 생성된 Body들의 리스트 + ECS 엔티티
```

---

## 9. 공간 쿼리 / 내비게이션

### G-18. 내비메시 (NavMesh) 미존재

현대적 게임 엔진의 필수 요소. 현재 forge3d에는 AI 이동·경로 탐색 기능이 없다.

**최소 구현 제안**:
```python
navmesh = world.build_navmesh(
    terrain=terrain_body,
    agent_radius=0.4,
    agent_height=1.8,
    max_slope_deg=45.0,
)
path = navmesh.find_path(start=(0,0,5), goal=(100,200,8))
# → [(x,y,z), ...] 경유점 리스트
```

---

### G-19. 공간 파티셔닝 쿼리 부재

현재 `world.raycast()` 이외에 공간 기반 쿼리가 없다.
게임 AI, 최적화에 필수적인 쿼리들이 누락되어 있다.

```python
# 모두 미존재
world.overlap_sphere(center, radius)           # 구 내 Body 목록
world.overlap_box(center, half_extents)        # 박스 내 Body 목록
world.closest_body(point, max_dist=10.0)       # 가장 가까운 Body
world.bodies_in_frustum(vp_matrix)             # 카메라 절두체 내 Body 목록
```

---

## 10. 개발자 경험 (DX)

### G-20. 디버그 렌더러 미존재

물리 충돌 형상(collider wireframe), trigger zone 경계, raycast 시각화,
joint 연결선 등을 화면에 그리는 디버그 렌더 패스가 없다.

**제안**:
```python
world.debug_draw = True          # 전역 on/off
world.debug.show_colliders = True
world.debug.show_triggers  = True
world.debug.show_joints    = True
world.debug.raycast(origin, dir, dist=50, color="red")  # 1프레임 시각화
```

---

### G-21. 실시간 물리 파라미터 튜닝 UI 없음

현재 gravity, friction, restitution 등을 변경하면 코드를 수정·재시작해야 한다.
EditorApp이 존재하지만 물리 파라미터 인스펙터와 연결되어 있지 않다.

---

### G-22. 프로파일러 미존재

`PhysicsWorld`의 스텝 시간, 충돌 감지 시간, 적분 시간 등을 측정하는 API가 없다.
성능 문제 진단이 어렵다.

**제안**:
```python
with world.profiler:
    world.step(dt)

print(world.profiler.last)
# PhysicsProfile(
#   broad_phase_ms = 0.12,
#   narrow_phase_ms = 0.38,
#   contact_solver_ms = 0.85,
#   integration_ms = 0.22,
#   total_ms = 1.57,
#   n_contacts = 14
# )
```

---

### G-23. glTF 2.0 씬 임포터 없음

현대 3D 에셋의 표준 교환 포맷(glTF)을 임포트할 수 없다.
`forge3d/io/obj_loader.py`는 존재하지만 glTF/GLB 로더가 없어
Blender 등에서 만든 애니메이션 포함 씬을 통째로 가져올 수 없다.

**우선순위**: OBJ 다음으로 가장 많이 요청될 기능.

```python
scene = f3d.import_gltf("ruins.glb")
scene.spawn_into(world, position=(0,0,0))
# → Body들 + 메시 + 애니메이션 클립 일괄 생성
```

---

## 11. 멀티플레이어 / 네트워킹

### G-24. 네트워크 동기화 프리미티브 없음

온라인 멀티플레이어를 구현하려면 물리 상태의 직렬화·역직렬화·보간이 필요하지만
관련 API가 전혀 없다. 최소한 스냅샷 직렬화가 완성되면(G-16) 기반이 된다.

**최소 제안**:
```python
# 스냅샷 직렬화
data: bytes = world.snapshot().to_bytes()   # 네트워크 전송용 압축 바이너리
world.apply_snapshot_bytes(data)            # 수신 측 복원

# 상태 보간 (클라이언트-사이드 예측)
world.interpolate_toward(remote_snapshot, alpha=0.15)
```

---

## 요약 테이블 (전체)

| ID | 분류 | 제목 | 심각도 | 우회책 있음 |
|----|------|------|--------|------------|
| B-1 | 버그 | `add_terrain` 커스텀 Material 스냅샷 유실 | 높음 | ✓ |
| B-2 | 버그 | `Body.name` setter 없음 | 보통 | ✓ |
| B-3 | 버그 | `save/load` Body 직렬화 안 됨 | 높음 | — |
| M-1 | 누락 | `TriggerZone` 이동/비활성화 | 보통 | — |
| M-2 | 누락 | 개별 Body 충돌 콜백 | 보통 | ✓ |
| M-3 | 누락 | 라이브 Body 형상 쿼리 | 보통 | ✓ |
| M-4 | 누락 | `Material.emissive` 스냅샷 전파 | 낮음 | ✓ |
| M-5 | 누락 | `BodySnapshot` orientation 쿼터니언 | 보통 | ✓ |
| M-6 | 누락 | `raycast_all()` 다중 히트 | 낮음 | — |
| M-7 | 누락 | `overlap_sphere/box()` | 낮음 | — |
| M-8 | 개선 | `set_position` vs `teleport` 의미 중복 | 낮음 | ✓ |
| M-9 | 개선 | `CollisionLayer` 비트마스크 문서화 | 낮음 | ✓ |
| M-10 | 누락 | 지형 높이 런타임 업데이트 | 낮음 | — |
| E-1 | 개선 | Body 생성 API 일관성 | 낮음 | ✓ |
| E-2 | 개선 | `BodySnapshot` 4×4 모델행렬 직접 제공 | 보통 | ✓ |
| E-3 | 개선 | `ContactInfo` 구조체 명세 | 보통 | — |
| E-4 | 개선 | `add_terrain` 마찰/레이어 파라미터 | 낮음 | — |
| E-5 | 개선 | `world.step()` 서브스텝 | 낮음 | ✓ |
| R-1 | 렌더러 | 스냅샷에 커스텀 메시 정보 없음 | 높음 | ✓ |
| R-2 | 렌더러 | 내장 렌더러 GPU 인스턴싱 미지원 | 높음 | ✓ |
| R-3 | 렌더러 | 내장 렌더러 포인트 라이트 미지원 | 보통 | ✓ |

---

## 게임엔진 관점 요약 테이블

| ID | 분류 | 제목 | 심각도 |
|----|------|------|--------|
| G-1  | 아키텍처 | ECS ↔ 물리 통합 부재 — 서브시스템 사용 불가 | **매우 높음** |
| G-2a | 렌더러 | DeferredRenderer 스텁 8곳 — 미완성 | 높음 |
| G-2b | 렌더러 | WGPURenderer 임포트 불가 | 보통 |
| G-3  | 렌더러 | WindowRenderer pygame 의존 — GLFW 백엔드 없음 | 높음 |
| G-4  | 렌더러 | windowed 그림자 512² — 품질 저하 | 낮음 |
| G-5  | 물리 | 고정 타임스텝(Fixed Timestep) 미지원 | 높음 |
| G-6  | 물리 | CCD 연속 충돌 감지 없음 — 고속 물체 터널링 | 보통 |
| G-7  | 물리 | 동적 지형 변형 불가 | 낮음 |
| G-8  | 물리 | JointType 열거형/문서 부재 | 낮음 |
| G-9  | 게임플레이 | 캐릭터 컨트롤러 미존재 | **매우 높음** |
| G-10 | VFX | 파티클 렌더 통합 없음 — 파티클 화면 출력 불가 | **매우 높음** |
| G-11 | VFX | 파티클-물리 상호작용 없음 | 보통 |
| G-12 | 애니메이션 | glTF/BVH 애니메이션 파일 로드 불가 | 높음 |
| G-13 | 애니메이션 | 애니메이션 상태 머신 없음 | 높음 |
| G-14 | 오디오 | Facade World에서 오디오 접근 불가 | 높음 |
| G-15 | 오디오 | 3D 거리 감쇠 모델 문서 없음 | 낮음 |
| G-16 | 씬 | 씬 저장/복원에 Body 미포함 | 높음 |
| G-17 | 씬 | Prefab facade 인터페이스 없음 | 보통 |
| G-18 | AI | 내비메시 미존재 | 보통 |
| G-19 | 공간 쿼리 | overlap_sphere/box, frustum culling 없음 | 보통 |
| G-20 | DX | 디버그 렌더러 없음 | 높음 |
| G-21 | DX | 실시간 파라미터 튜닝 UI 없음 | 낮음 |
| G-22 | DX | 물리 프로파일러 없음 | 보통 |
| G-23 | 에셋 | glTF 2.0 씬 임포터 없음 | 높음 |
| G-24 | 네트워크 | 상태 직렬화/보간 프리미티브 없음 | 낮음 |

### 우선순위 요약

**P0 — 먼저 해결하지 않으면 게임 제작이 불가능한 것**
1. **G-1** ECS-물리 통합 (오디오·파티클·애니메이션을 쓰려면 필수)
2. **G-9** 캐릭터 컨트롤러 (플레이어 이동은 모든 게임에 필요)
3. **G-10** 파티클 렌더 통합 (ParticleSystem 자체가 현재 렌더 불가)
4. **B-1** terrain 커스텀 Material 스냅샷 유실 (지형 색상·텍스처 전달 불가)
5. **B-3** world.save/load Body 직렬화 안 됨 (씬 저장 기능 사실상 없음)

**P1 — 게임 품질에 직결**
- **G-3** GLFW 백엔드 / **G-5** 고정 타임스텝 / **G-12** glTF 애니메이션
- **G-14** Facade 오디오 / **G-16** 씬 직렬화 / **G-20** 디버그 렌더러
- **G-23** glTF 씬 임포터 / **R-1** 커스텀 메시 스냅샷 / **R-2** GPU 인스턴싱

**P2 — 있으면 좋은 것**
- G-6 CCD / G-8 JointType / G-13 FSM / G-18 NavMesh / G-19 공간 쿼리
- G-22 프로파일러 / M-2 Body 충돌 콜백 / M-6 raycast_all
