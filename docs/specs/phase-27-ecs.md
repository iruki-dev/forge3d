# SPEC: Phase 27 — Entity Component System (ECS)

> Claude가 이 작업을 진행하는 **단일 기준**이다. 자기완결적으로 작성한다.  
> 파생: `docs/ROADMAP_v2.md` P27. 규칙: 루트 `CLAUDE.md`. 절차: `docs/WORKFLOW.md`.

---

## 1. 목표 (한 문장)

Unity의 GameObject/Component 패턴을 Python으로 구현하여 **복잡한 씬을 컴포넌트 조합으로 설계**할 수 있게 하되, v1 `Body/World` API와 완전 호환되어 기존 코드가 수정 없이 동작해야 한다.

---

## 2. 범위

### 포함

- **EntityWorld**: 엔티티(정수 ID) 생성/소멸, 컴포넌트 등록/조회
- **기본 컴포넌트**: `Transform`, `MeshRenderer`, `Collider`, `Rigidbody`, `Camera`, `Light`, `Script`
- **System 추상**: `System.update(world, dt)` — 물리·렌더·입력 시스템 등록
- **Transform 계층**: 부모/자식 Transform, 월드 행렬 재귀 계산
- **`World.query()` API**: Unity `FindObjectsOfType<T>()` 대응
- **v1 Body 브릿지**: 기존 `Body` 객체를 ECS 엔티티로 래핑
- **JAX-가속 배치 Transform**: `vmap`으로 N개 엔티티 행렬 일괄 계산
- **씬 계층 직렬화**: ECS 씬을 JSON으로 save/load

### 제외 (Out of scope)

- DOTS 수준의 청크(Chunk) 메모리 레이아웃 — Python에서 비현실적
- 메모리 세이프 아키타입(Archetype) 시스템 — v2.2 이후
- ECS 전용 물리 백엔드 — P25 Rust 코어를 그대로 사용
- 시각적 씬 에디터 — P33
- 네트워킹/멀티플레이어 — 로드맵 외

---

## 3. 영향 파일 / 인터페이스

### 새로 생성

| 경로 | 역할 |
|------|------|
| `src/forge3d/ecs/__init__.py` | 공개 ECS API |
| `src/forge3d/ecs/entity.py` | `Entity(int)` 타입 별칭, `EntityWorld` |
| `src/forge3d/ecs/component.py` | `Component` 기반 클래스, 내장 컴포넌트 |
| `src/forge3d/ecs/system.py` | `System` ABC, `SystemRegistry` |
| `src/forge3d/ecs/transform.py` | `Transform` 컴포넌트, 계층 계산 |
| `src/forge3d/ecs/query.py` | `Query`, `QueryBuilder` |
| `src/forge3d/ecs/bridge.py` | v1 `Body` ↔ ECS 엔티티 래퍼 |
| `src/forge3d/ecs/serialization.py` | ECS 씬 JSON 직렬화 |
| `tests/test_p27_ecs.py` | ECS 단위 + 통합 테스트 |
| `examples/05_ecs_scene.py` | ECS 진입 예제 (15줄 이내) |

### 수정

| 경로 | 변경 |
|------|------|
| `src/forge3d/__init__.py` | `EntityWorld`, `Component`, `System`, `Transform` 공개 |
| `src/forge3d/facade.py` | `World.entity_world` 프로퍼티로 ECS 연결 |
| `src/forge3d/render/snapshot.py` | `SceneSnapshot` 생성 시 ECS Transform 계층 반영 |

### 핵심 인터페이스

```python
# --- 엔티티 생성 ---
Entity = int  # 타입 별칭

class EntityWorld:
    def create_entity(self, *components: Component) -> Entity: ...
    def destroy_entity(self, e: Entity) -> None: ...
    def add_component(self, e: Entity, c: Component) -> None: ...
    def remove_component(self, e: Entity, typ: type[C]) -> None: ...
    def get_component(self, e: Entity, typ: type[C]) -> C: ...
    def query(self, *types: type[Component]) -> Iterator[tuple[Entity, ...]]: ...
    def add_system(self, system: System) -> None: ...
    def step(self, dt: float) -> None: ...  # 등록된 모든 System 실행

# --- 기본 컴포넌트 ---
@dataclass
class Transform(Component):
    position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    rotation: np.ndarray = field(default_factory=lambda: np.array([1,0,0,0]))  # 쿼터니언 w,x,y,z
    scale: np.ndarray = field(default_factory=lambda: np.ones(3))
    parent: Entity | None = None

    def world_matrix(self, ew: "EntityWorld") -> np.ndarray:
        """(4,4) 월드 변환 행렬 (부모 계층 포함)"""

@dataclass
class MeshRenderer(Component):
    mesh_id: str
    material: Material

@dataclass
class Rigidbody(Component):
    mass: float = 1.0
    is_static: bool = False
    _body_ref: Any = field(default=None, repr=False)  # v1 Body 브릿지

@dataclass
class Collider(Component):
    shape: str  # "box" | "sphere" | "capsule"
    size: np.ndarray = field(default_factory=lambda: np.ones(3))

@dataclass
class Script(Component):
    on_start: Callable | None = None
    on_update: Callable[[float], None] | None = None

# --- 시스템 ---
class System(ABC):
    @abstractmethod
    def update(self, ew: EntityWorld, dt: float) -> None: ...

class PhysicsSystem(System):
    """v1 World와 ECS를 동기화"""

class RenderSystem(System):
    """ECS Transform → SceneSnapshot 생성"""

# --- 쿼리 예시 ---
for entity, transform, rb in ew.query(Transform, Rigidbody):
    transform.position += np.array([0, 0, 0.1]) * dt

# --- v1 브릿지 ---
def body_to_entity(world: "forge3d.World", body: "forge3d.Body") -> Entity:
    """기존 Body를 ECS 엔티티로 래핑 (파괴적 변환 없음)"""

# --- 진입 예제 (15줄 이내) ---
import forge3d as f3d
ew = f3d.EntityWorld()
ground = ew.create_entity(
    f3d.Transform(position=[0, 0, 0]),
    f3d.Collider(shape="box", size=[20, 20, 0.1]),
    f3d.Rigidbody(is_static=True),
)
box = ew.create_entity(
    f3d.Transform(position=[0, 0, 5]),
    f3d.MeshRenderer(mesh_id="box_1x1", material=f3d.Material(color="red")),
    f3d.Rigidbody(mass=1.0),
)
ew.add_system(f3d.PhysicsSystem())
ew.add_system(f3d.RenderSystem())
app = f3d.App(entity_world=ew)
app.run()
```

---

## 4. 구현 작업 (체크리스트)

- [ ] **T1. `EntityWorld` 코어** — 완료 조건: 엔티티 생성/소멸, 컴포넌트 CRUD, `query()` 동작
  - `entity.py`: `EntityWorld` 클래스 (`_components: dict[type, dict[Entity, Component]]`)
  - `query.py`: 타입 교집합 반복자
  - 단위 테스트: 생성/소멸, 컴포넌트 없는 엔티티 query 결과 empty

- [ ] **T2. `Transform` 계층** — 완료 조건: 부모 이동 시 자식 월드 행렬 갱신
  - `transform.py`: `world_matrix()` 재귀 계산
  - JAX vmap 경로: N개 엔티티 행렬 일괄 계산 (`jax_batch_world_matrix()`)
  - 테스트: 자식이 부모 좌표계에서 올바른 월드 위치 반환

- [ ] **T3. 내장 컴포넌트** — 완료 조건: `Rigidbody`, `Collider`, `MeshRenderer`, `Script` 데이터 클래스
  - `component.py`: 6개 내장 컴포넌트 dataclass
  - 타입 검사: `mypy src/forge3d/ecs/` 0 errors

- [ ] **T4. `System` + `PhysicsSystem`** — 완료 조건: `PhysicsSystem.update()` 가 v1 `World.step()` 호출 + 결과를 ECS Transform에 역동기화
  - `system.py`: `System` ABC, `SystemRegistry`
  - `PhysicsSystem`: `Rigidbody` 엔티티 목록 → v1 Body 동기화 → 스텝 → Transform 갱신
  - 테스트: 중력 아래 `Rigidbody` 엔티티가 낙하

- [ ] **T5. `RenderSystem` + SceneSnapshot 연동** — 완료 조건: ECS 씬이 `Viewer`에 렌더됨
  - `RenderSystem`: `Transform` + `MeshRenderer` 엔티티 → `SceneSnapshot` 생성
  - `viewer.py`에서 `EntityWorld` 받는 오버로드 추가

- [ ] **T6. v1 Body 브릿지** — 완료 조건: 기존 `World.add_box()` 반환 Body를 `body_to_entity()`로 ECS 편입
  - `bridge.py`: `body_to_entity()`, `sync_body_to_transform()`, `sync_transform_to_body()`
  - 테스트: v1 Body와 ECS 엔티티가 같은 물리 상태 공유

- [ ] **T7. ECS 씬 직렬화** — 완료 조건: `ew.save("scene.json")` → `ew.load("scene.json")` 재현 일치
  - `serialization.py`: 컴포넌트 → JSON 변환 (numpy 배열 list 직렬화)
  - 테스트: 저장 전·후 엔티티 수, Transform 위치 일치

- [ ] **T8. 예제 + 문서** — 완료 조건: `examples/05_ecs_scene.py` 15줄 이내 동작
  - 예제: 중력 씬, ECS 쿼리로 낙하 오브젝트 색상 변경
  - `docs_src/tutorials/ecs_quickstart.md` 작성

---

## 5. 엣지 케이스 / 제약

- **순환 부모 금지**: `Transform.parent` 설정 시 순환 감지, `Forge3dError` 발생.
- **엔티티 소멸 후 접근**: `get_component(destroyed_entity, T)` → `KeyError` 대신 명확한 `EntityNotFoundError`.
- **`Query` 비용**: Python 기반이므로 매 프레임 조회는 O(N) 컴포넌트 딕셔너리 교집합. 핫루프에서는 결과를 캐시하도록 문서 안내.
- **v1 API 불변**: `World`, `Body`, `Viewer`, `Recorder`의 시그니처는 건드리지 않는다. ECS는 추가 레이어.
- **`Script` 컴포넌트**: `on_update(dt)` 콜백에서 예외 발생 시 시스템 전체 중단 방지 — try/except + 로그.

---

## 6. 검증 (Phase 게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | `EntityWorld` 생성/쿼리/소멸 | `tests/test_p27_ecs.py::test_entity_lifecycle` |
| G2 | Transform 계층: 부모 이동 → 자식 월드 행렬 갱신 | `tests/test_p27_ecs.py::test_transform_hierarchy` |
| G3 | `PhysicsSystem` 하에서 중력 낙하 (위치 감소 확인) | `tests/test_p27_ecs.py::test_physics_system` |
| G4 | v1 Body → ECS 브릿지: 같은 물리 상태 공유 | `tests/test_p27_ecs.py::test_v1_bridge` |
| G5 | ECS 씬 save → load 재현 일치 | `tests/test_p27_ecs.py::test_serialization` |
| G6 | `examples/05_ecs_scene.py` 15줄 이내 수정 없이 동작 | 직접 실행 |
| G7 | v1 예제(`examples/01_falling_box_realtime.py`) 수정 없이 동작 | 회귀 확인 |
| G8 | `pytest tests/ -q` 전체 PASS (기존 테스트 회귀 없음) | 전체 스위트 |

---

## 7. 완료 후 리뷰

- `EntityWorld`가 `src/forge3d/sim/world.py`를 import하는 방향으로만 의존 (역방향 금지).
- `PhysicsSystem`이 렌더러를 import하지 않음 확인.
- P28(오디오) 착수 전 G1~G8 전부 통과 필수.
