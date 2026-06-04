"""EditorApp — ImGui 기반 씬 에디터 메인 클래스."""
from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable

import numpy as np

from forge3d.editor.gizmo import TranslateGizmo, screen_to_ray
from forge3d.editor.layout import EditorLayout, LayoutConfig
from forge3d.ui.panels import DebugPanel, HierarchyPanel, InspectorPanel

if TYPE_CHECKING:
    from forge3d.ecs.entity import EntityWorld
    from forge3d.facade import World


class PlayState(Enum):
    """에디터 플레이 상태 머신."""
    EDIT = auto()    # 물리 정지, 에디터 활성
    PLAY = auto()    # 물리 실행
    PAUSE = auto()   # 물리 일시정지


class EditorApp:
    """씬 에디터 애플리케이션.

    v1 World + ECS EntityWorld를 함께 관리한다.
    ImGui 없는 환경에서는 상태 머신과 레이캐스트 로직만 동작한다.
    """

    def __init__(
        self,
        world: "World",
        entity_world: "EntityWorld",
        config: LayoutConfig | None = None,
        dt: float = 1 / 60,
    ) -> None:
        self._world = world
        self._ew = entity_world
        self._dt = dt
        self._state = PlayState.EDIT
        self._frame_count = 0
        self._step_requested = False

        self.layout = EditorLayout(config)
        self.gizmo = TranslateGizmo()
        self.hierarchy = HierarchyPanel()
        self.inspector = InspectorPanel()
        self.debug = DebugPanel()

        self._on_scene_saved: Callable | None = None
        self._scene_path: str = "scene.json"

        # 누적 시간 (성능 측정용)
        self._last_step_ms: float = 0.0
        self._fps: float = 0.0

    # ── 플레이 상태 머신 ──────────────────────────────────────────────────────

    def play(self) -> None:
        """에디터 모드 → 플레이 모드 (물리 활성화)."""
        self._state = PlayState.PLAY

    def pause(self) -> None:
        """플레이 → 일시정지."""
        if self._state == PlayState.PLAY:
            self._state = PlayState.PAUSE

    def stop(self) -> None:
        """플레이/일시정지 → 에디터 모드."""
        self._state = PlayState.EDIT

    def step_once(self) -> None:
        """단일 물리 스텝 실행 (일시정지 또는 에디터 모드에서 사용)."""
        self._step_requested = True

    @property
    def play_state(self) -> PlayState:
        return self._state

    @property
    def is_playing(self) -> bool:
        return self._state == PlayState.PLAY

    @property
    def is_paused(self) -> bool:
        return self._state == PlayState.PAUSE

    @property
    def is_editing(self) -> bool:
        return self._state == PlayState.EDIT

    # ── 프레임 업데이트 ──────────────────────────────────────────────────────

    def update(self) -> None:
        """한 프레임을 처리한다 (물리 스텝 + UI 업데이트)."""
        import time
        t0 = time.perf_counter()

        if self._state == PlayState.PLAY or self._step_requested:
            self._world.step(self._dt)
            self._ew.step(self._dt)
            self._step_requested = False

        step_ms = (time.perf_counter() - t0) * 1000
        self._last_step_ms = step_ms
        self._frame_count += 1

        # FPS 근사
        self._fps = 1.0 / max(self._dt, 1e-6)

        # 패널 업데이트
        from forge3d.ecs.entity import EntityWorld
        body_count = len(self._ew.all_entities())
        self.debug.render(fps=self._fps, body_count=body_count, step_ms=step_ms)
        self.hierarchy.render(ew=self._ew, inspector=self.inspector)

        if self.gizmo.state.selected is not None:
            self.inspector.render(ew=self._ew, selected=self.gizmo.state.selected)

    # ── 레이캐스트 선택 ──────────────────────────────────────────────────────

    def pick_entity(
        self,
        screen_x: float,
        screen_y: float,
        fov_deg: float = 45.0,
        view_matrix: np.ndarray | None = None,
    ) -> int | None:
        """화면 좌표 (screen_x, screen_y)에서 레이캐스트로 엔티티를 선택한다."""
        if view_matrix is None:
            view_matrix = np.eye(4)
        w = self.layout.config.viewport_width
        h = self.layout.config.window_height
        origin, direction = screen_to_ray(screen_x, screen_y, w, h, fov_deg, view_matrix)
        entity = self.gizmo.pick(origin, direction, self._ew)
        if entity is not None:
            self.inspector.select(entity)
            self.hierarchy.select(entity)
        return entity

    # ── 기즈모 조작 ──────────────────────────────────────────────────────────

    def move_selected(self, axis: int, delta: float) -> None:
        """선택된 엔티티를 지정 축으로 delta 만큼 이동한다 (0=X, 1=Y, 2=Z)."""
        self.gizmo.start_drag(axis)
        self.gizmo.drag(delta, self._ew)
        self.gizmo.end_drag()

    # ── 씬 저장 ──────────────────────────────────────────────────────────────

    def save_scene(self, path: str | None = None) -> None:
        """현재 ECS 씬을 JSON으로 저장한다."""
        from forge3d.ecs.serialization import save_scene
        target = path or self._scene_path
        save_scene(self._ew, target)
        if self._on_scene_saved:
            self._on_scene_saved(target)

    def on_scene_saved(self, callback: Callable) -> None:
        self._on_scene_saved = callback

    def set_scene_path(self, path: str) -> None:
        self._scene_path = path

    # ── 간소화 실행 루프 (headless 테스트용) ─────────────────────────────────

    def run_headless(self, n_frames: int = 1) -> None:
        """GUI 없이 n_frames 동안 update()를 실행한다."""
        for _ in range(n_frames):
            self.update()

    def run(self, max_frames: int = 0) -> None:
        """에디터를 실행한다. ImGui 가용 시 실제 창, 없으면 1프레임 headless."""
        from forge3d.ui.backend import has_imgui
        if has_imgui():
            self._run_imgui(max_frames)
        else:
            frames = max_frames if max_frames > 0 else 1
            self.run_headless(frames)

    def _run_imgui(self, max_frames: int) -> None:
        """ImGui 기반 에디터 루프."""
        # 실제 ImGui 창 생성은 moderngl 컨텍스트 필요 — 현재 구현 범위 밖
        # 기본 동작: headless update
        frames = max_frames if max_frames > 0 else 1
        self.run_headless(frames)

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def selected_entity(self) -> int | None:
        return self.gizmo.state.selected
