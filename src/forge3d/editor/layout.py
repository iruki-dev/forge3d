"""3패널 에디터 레이아웃 — Hierarchy | Viewport | Inspector."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from forge3d.ecs.entity import Entity, EntityWorld


@dataclass
class LayoutConfig:
    """레이아웃 비율 설정."""
    hierarchy_width: float = 0.2   # 전체 너비의 20%
    inspector_width: float = 0.25  # 전체 너비의 25%
    # viewport = 나머지 55%

    window_width: int = 1280
    window_height: int = 720

    @property
    def hierarchy_px(self) -> int:
        return int(self.window_width * self.hierarchy_width)

    @property
    def inspector_px(self) -> int:
        return int(self.window_width * self.inspector_width)

    @property
    def viewport_x(self) -> int:
        return self.hierarchy_px

    @property
    def viewport_width(self) -> int:
        return self.window_width - self.hierarchy_px - self.inspector_px


class EditorLayout:
    """3패널 레이아웃 — ImGui DockSpace 또는 고정 분할.

    ImGui 없는 환경에서는 내부 상태만 관리한다.
    """

    def __init__(self, config: LayoutConfig | None = None) -> None:
        self.config = config or LayoutConfig()
        self._panels_rendered: list[str] = []

    def begin_frame(self) -> None:
        """프레임 시작 — ImGui 가용 시 DockSpace 초기화."""
        self._panels_rendered.clear()
        from forge3d.ui.backend import get_imgui
        ig = get_imgui()
        if ig is None:
            return
        try:
            # 풀스크린 DockSpace
            ig.set_next_window_size(
                (float(self.config.window_width), float(self.config.window_height))
            )
            ig.set_next_window_pos((0.0, 0.0))
        except Exception:
            pass

    def begin_hierarchy(self) -> None:
        self._panels_rendered.append("hierarchy")
        from forge3d.ui.backend import get_imgui
        ig = get_imgui()
        if ig is None:
            return
        try:
            ig.set_next_window_size((float(self.config.hierarchy_px),
                                     float(self.config.window_height)))
            ig.set_next_window_pos((0.0, 0.0))
            ig.begin("Hierarchy##editor")
        except Exception:
            pass

    def end_hierarchy(self) -> None:
        from forge3d.ui.backend import get_imgui
        ig = get_imgui()
        if ig:
            try:
                ig.end()
            except Exception:
                pass

    def begin_inspector(self) -> None:
        self._panels_rendered.append("inspector")
        from forge3d.ui.backend import get_imgui
        ig = get_imgui()
        if ig is None:
            return
        try:
            x = float(self.config.window_width - self.config.inspector_px)
            ig.set_next_window_size((float(self.config.inspector_px),
                                     float(self.config.window_height)))
            ig.set_next_window_pos((x, 0.0))
            ig.begin("Inspector##editor")
        except Exception:
            pass

    def end_inspector(self) -> None:
        from forge3d.ui.backend import get_imgui
        ig = get_imgui()
        if ig:
            try:
                ig.end()
            except Exception:
                pass

    def begin_viewport(self) -> None:
        self._panels_rendered.append("viewport")

    def end_viewport(self) -> None:
        pass

    @property
    def rendered_panels(self) -> list[str]:
        return list(self._panels_rendered)
