# SPEC: Phase 32 — UI 시스템 (ImGui + 캔버스 오버레이)

> 파생: `docs/ROADMAP_v2.md` P32. 규칙: 루트 `CLAUDE.md`.

---

## 1. 목표 (한 문장)

ImGui-bundle 기반 디버그·인스펙터 패널과 간단한 2D 캔버스 HUD 오버레이를 제공하여 게임 루프 안에서 즉시 UI를 구성할 수 있게 한다.

---

## 2. 범위

### 포함

- **ImGui 통합**: `imgui-bundle` (`imgui.h` Python 바인딩)
- **DebugPanel**: FPS, 바디 수, 물리 스텝 시간 표시
- **InspectorPanel**: ECS 엔티티 선택 → 컴포넌트 필드 실시간 편집
- **HierarchyPanel**: 씬 트리 표시, 엔티티 선택
- **Canvas**: 2D 오버레이(텍스트, 직사각형, 이미지), 화면 좌표계
- **UISystem**: ECS 시스템, 매 프레임 ImGui 호출 관리

### 제외 (Out of scope)

- 월드 공간 3D 빌보드 UI — v2.2 이후
- 커스텀 스킨/테마 에디터 — v2.2 이후
- 씬 에디터(오브젝트 드래그 배치) — P33

---

## 3. 영향 파일 / 인터페이스

### 새로 생성

| 경로 | 역할 |
|------|------|
| `src/forge3d/ui/__init__.py` | 공개 UI API |
| `src/forge3d/ui/panels.py` | `DebugPanel`, `InspectorPanel`, `HierarchyPanel` |
| `src/forge3d/ui/canvas.py` | `Canvas` 2D 오버레이 |
| `src/forge3d/ui/system.py` | `UISystem` ECS 시스템 |
| `tests/test_p32_ui.py` | UI 로직 단위 테스트 |

### 핵심 인터페이스

```python
class DebugPanel:
    def render(self, fps: float, body_count: int, step_ms: float) -> None: ...

class InspectorPanel:
    def render(self, ew: EntityWorld, selected: Entity | None) -> None: ...

class Canvas:
    def text(self, pos: tuple[int, int], content: str, color=(1,1,1,1)) -> None: ...
    def rect(self, pos, size, color, filled=True) -> None: ...

class UISystem(System):
    def add_panel(self, panel: Any) -> None: ...
    def update(self, ew: EntityWorld, dt: float) -> None: ...
```

### 의존성

```toml
"imgui-bundle>=1.5"
```

---

## 4. 구현 작업 (체크리스트)

- [ ] **T1. ImGui 컨텍스트 초기화** — 완료 조건: moderngl + imgui-bundle 공존, 예외 없음
- [ ] **T2. DebugPanel** — 완료 조건: FPS/바디수/스텝ms 텍스트 패널 렌더
- [ ] **T3. InspectorPanel** — 완료 조건: 선택된 엔티티의 Transform 필드 실시간 편집
- [ ] **T4. HierarchyPanel** — 완료 조건: 씬 트리 목록, 클릭으로 엔티티 선택
- [ ] **T5. Canvas 오버레이** — 완료 조건: 2D 텍스트·직사각형을 화면에 픽셀 좌표로 그리기
- [ ] **T6. UISystem + 통합** — 완료 조건: `App.run()` 루프에서 자동 호출
- [ ] **T7. 테스트** — 완료 조건: null 렌더 기반 6개 논리 테스트 PASS

---

## 5. 검증 (Phase 게이트)

| # | 기준 | 방법 |
|---|------|------|
| G1 | `DebugPanel.render()` 예외 없음 (null 백엔드) | `test_p32_ui::test_debug_panel` |
| G2 | `InspectorPanel` 편집 → ECS 컴포넌트 값 반영 | `test_p32_ui::test_inspector_edit` |
| G3 | `Canvas.text()` 좌표 범위 벗어나면 clip (예외 없음) | `test_p32_ui::test_canvas_clip` |
| G4 | 전체 기존 테스트 회귀 없음 | `pytest tests/ -q` |
