"""UISystem — ECS 시스템, 등록된 패널의 render()를 매 프레임 호출."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from forge3d.ecs.system import System

if TYPE_CHECKING:
    from forge3d.ecs.entity import EntityWorld


class UISystem(System):
    """UI 패널 + 캔버스를 ECS 루프에서 관리하는 시스템.

    패널은 `add_panel()`로 등록하면 `update()` 시 자동 호출된다.
    ImGui 프레임 경계(begin/end frame)는 외부 렌더 루프에서 담당한다.
    """

    def __init__(self) -> None:
        self._panels: list[Any] = []
        self._canvas: Any | None = None
        self._debug_state: dict[str, object] = {"fps": 0.0, "body_count": 0, "step_ms": 0.0}

    def add_panel(self, panel: Any) -> None:
        self._panels.append(panel)

    def set_canvas(self, canvas: Any) -> None:
        self._canvas = canvas

    def set_debug_info(self, fps: float, body_count: int = 0, step_ms: float = 0.0) -> None:
        """외부에서 디버그 지표를 설정한다."""
        self._debug_state = {"fps": fps, "body_count": body_count, "step_ms": step_ms}

    def update(self, ew: "EntityWorld", dt: float) -> None:
        """등록된 패널의 render()를 호출한다."""
        fps = float(self._debug_state.get("fps", 0.0))
        body_count = int(self._debug_state.get("body_count", 0))
        step_ms = float(self._debug_state.get("step_ms", 0.0))

        for panel in self._panels:
            try:
                cls_name = type(panel).__name__
                if cls_name == "DebugPanel":
                    panel.render(fps=fps, body_count=body_count, step_ms=step_ms)
                elif cls_name == "InspectorPanel":
                    panel.render(ew=ew)
                elif cls_name == "HierarchyPanel":
                    panel.render(ew=ew)
                elif hasattr(panel, "render"):
                    panel.render(ew=ew, dt=dt)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("UISystem 패널 오류: %s", exc)

    @property
    def panel_count(self) -> int:
        return len(self._panels)
