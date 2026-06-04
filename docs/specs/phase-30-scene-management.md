# SPEC: Phase 30 — 씬 관리 (Transform 계층 + Prefab + 씬 스트리밍)

> 파생: `docs/ROADMAP_v2.md` P30. 규칙: 루트 `CLAUDE.md`.

---

## 1. 목표 (한 문장)

부모/자식 Transform 계층, Prefab(재사용 가능한 엔티티 템플릿), 씬 로드/언로드를 통해 복잡한 씬을 데이터 기반으로 구성하고 교체할 수 있게 한다.

---

## 2. 범위

### 포함

- **Transform 부모/자식 계층** (P27 ECS Transform 위에 확장)
  - `SceneNode`: 이름 있는 트리 노드, 자식 리스트
  - `world_position()`, `world_rotation()` 재귀 계산
  - 부모 변경 시 자식 월드 행렬 자동 갱신 (dirty flag)
- **Prefab 시스템**
  - `Prefab`: 엔티티+컴포넌트 묶음을 JSON 정의로 저장
  - `World.instantiate(prefab, position, rotation)` — 복제 생성
  - `Prefab.save()` / `Prefab.load()` JSON
- **씬 로드/언로드**
  - `SceneManager.load_scene(path)` — 기존 씬 언로드 + 새 씬 로드
  - `SceneManager.add_scene(path)` — 씬 중첩(additive) 로드
  - 씬 전환 콜백: `on_scene_loaded`, `on_scene_unloading`

### 제외 (Out of scope)

- 비동기/스트리밍 씬 로드 (대형 오픈 월드) — v2.2 이후
- 씬 전환 애니메이션/크로스페이드 — v2.2 이후

---

## 3. 영향 파일 / 인터페이스

### 새로 생성

| 경로 | 역할 |
|------|------|
| `src/forge3d/scene/__init__.py` | 공개 씬 관리 API |
| `src/forge3d/scene/node.py` | `SceneNode` 트리 |
| `src/forge3d/scene/prefab.py` | `Prefab` 직렬화/인스턴스화 |
| `src/forge3d/scene/manager.py` | `SceneManager` 로드/언로드 |
| `tests/test_p30_scene.py` | 씬 관리 테스트 |

### 핵심 인터페이스

```python
class SceneNode:
    name: str
    entity: Entity
    children: list["SceneNode"]
    parent: "SceneNode | None"

    def world_position(self) -> np.ndarray: ...
    def world_matrix(self) -> np.ndarray: ...
    def add_child(self, child: "SceneNode") -> None: ...
    def remove_child(self, child: "SceneNode") -> None: ...

class SceneManager:
    def load_scene(self, path: str) -> None: ...
    def add_scene(self, path: str) -> None: ...   # additive
    def unload_scene(self) -> None: ...
    def on_scene_loaded(self, callback: Callable) -> None: ...

# Prefab
class Prefab:
    @staticmethod
    def save(node: SceneNode, path: str) -> None: ...
    @staticmethod
    def load(path: str) -> "Prefab": ...
    def instantiate(
        self, ew: EntityWorld, position: np.ndarray, rotation: np.ndarray | None = None
    ) -> SceneNode: ...
```

---

## 4. 구현 작업 (체크리스트)

- [ ] **T1. SceneNode 트리** — 완료 조건: 부모 이동 → 자식 월드 위치 연동
- [ ] **T2. Dirty flag 최적화** — 완료 조건: 변경 없으면 행렬 재계산 안 함
- [ ] **T3. Prefab JSON 직렬화** — 완료 조건: save → load → instantiate 위치 일치
- [ ] **T4. SceneManager load/unload** — 완료 조건: 씬 전환 후 이전 엔티티 소멸 확인
- [ ] **T5. 씬 콜백** — 완료 조건: `on_scene_loaded` 콜백 호출 횟수 검증
- [ ] **T6. 테스트** — 완료 조건: 8개 테스트 PASS

---

## 5. 검증 (Phase 게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | 부모 이동 → 자식 월드 위치 갱신 | `test_p30_scene::test_transform_hierarchy` |
| G2 | Prefab save/load/instantiate 재현 | `test_p30_scene::test_prefab_roundtrip` |
| G3 | `load_scene` 후 이전 씬 엔티티 0개 | `test_p30_scene::test_scene_unload` |
| G4 | 전체 기존 테스트 회귀 없음 | `pytest tests/ -q` |
