# SPEC: Phase 33 — 씬 에디터 (ImGui 기반)

> 파생: `docs/ROADMAP_v2.md` P33. 규칙: 루트 `CLAUDE.md`.

---

## 1. 목표 (한 문장)

ImGui 기반 씬 에디터를 제공하여 뷰포트에서 오브젝트를 선택·이동하고 인스펙터에서 컴포넌트를 수정하며 Play/Pause/Step을 제어할 수 있게 한다.

---

## 2. 범위

### 포함

- **에디터 레이아웃**: 계층(Hierarchy) + 뷰포트 + 인스펙터 3패널 분할
- **오브젝트 선택**: 마우스 클릭 → 레이캐스트 → 엔티티 선택 + 아웃라인
- **이동 기즈모**: 선택 오브젝트 이동(축 드래그), 회전·스케일(기본)
- **Play/Pause/Step 버튼**: 에디터 모드(정지) ↔ 플레이 모드(물리 활성)
- **실시간 인스펙터**: P32 InspectorPanel 통합
- **씬 저장**: 에디터에서 JSON 씬 저장 (P30 SceneManager 통합)

### 제외 (Out of scope)

- 에셋 임포터(파일 시스템 브라우저) — v2.2 이후
- Undo/Redo 스택 — v2.2 이후
- 멀티뷰포트(4분할) — v2.2 이후

---

## 3. 영향 파일 / 인터페이스

### 새로 생성

| 경로 | 역할 |
|------|------|
| `src/forge3d/editor/__init__.py` | 공개 에디터 API |
| `src/forge3d/editor/layout.py` | 3패널 레이아웃 관리 |
| `src/forge3d/editor/gizmo.py` | 이동/회전/스케일 기즈모 |
| `src/forge3d/editor/editor_app.py` | `EditorApp` — 에디터 모드 App |
| `tests/test_p33_editor.py` | 에디터 로직 단위 테스트 |

### 핵심 인터페이스

```python
class EditorApp:
    def __init__(self, world: World, entity_world: EntityWorld) -> None: ...
    def run(self) -> None: ...
    # 내부적으로 Play/Pause/Step 상태를 관리
    # Play: World.step() 활성화
    # Pause: World.step() 중단
    # Step: 단일 스텝 실행

# 진입 예제
import forge3d as f3d
world = f3d.World()
ew = f3d.EntityWorld()
editor = f3d.EditorApp(world, ew)
editor.run()
```

---

## 4. 구현 작업 (체크리스트)

- [ ] **T1. 3패널 레이아웃** — 완료 조건: ImGui DockSpace 3영역 분할
- [ ] **T2. 레이캐스트 선택** — 완료 조건: 뷰포트 클릭 → 가장 가까운 엔티티 선택
- [ ] **T3. 이동 기즈모** — 완료 조건: 선택 오브젝트 XYZ 축 드래그 이동
- [ ] **T4. Play/Pause/Step 상태 머신** — 완료 조건: 버튼 상태에 따라 물리 스텝 ON/OFF
- [ ] **T5. 씬 저장 버튼** — 완료 조건: 버튼 클릭 → P30 SceneManager.save() 호출
- [ ] **T6. 테스트** — 완료 조건: 레이캐스트 로직, 상태 전환 8개 테스트 PASS

---

## 5. 검증 (Phase 게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | 레이캐스트 → 올바른 엔티티 선택 | `test_p33_editor::test_entity_pick` |
| G2 | Play→Pause→Step 상태 전환 | `test_p33_editor::test_play_pause_step` |
| G3 | 이동 기즈모 드래그 → Transform 위치 갱신 | `test_p33_editor::test_gizmo_drag` |
| G4 | 전체 기존 테스트 회귀 없음 | `pytest tests/ -q` |
