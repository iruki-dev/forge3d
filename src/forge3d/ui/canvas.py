"""Canvas — 2D 픽셀 좌표계 오버레이 (텍스트, 직사각형, 이미지).

ImGui DrawList 또는 NumPy 버퍼에 렌더링한다.
좌표 범위를 벗어나면 clip (예외 없음).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from forge3d.ui.backend import get_imgui

Color = tuple[float, float, float, float]  # RGBA [0,1]


@dataclass
class DrawCommand:
    """단일 드로우 커맨드 레코드 (테스트 검증용)."""

    kind: str  # "text" | "rect" | "image"
    pos: tuple[int, int]
    args: dict  # kind별 추가 인수


class Canvas:
    """2D 화면 좌표계 오버레이.

    ImGui DrawList 또는 내부 커맨드 버퍼에 기록한다.
    테스트에서는 커맨드 버퍼만 사용한다.
    """

    def __init__(self, width: int = 1280, height: int = 720) -> None:
        self.width = width
        self.height = height
        self._commands: list[DrawCommand] = []

    # ── 드로우 API ───────────────────────────────────────────────────────────

    def text(
        self,
        pos: tuple[int, int],
        content: str,
        color: Color = (1.0, 1.0, 1.0, 1.0),
    ) -> None:
        """지정 위치에 텍스트를 그린다. 화면 밖이면 clip (무시)."""
        if not self._in_bounds(pos):
            return
        self._commands.append(DrawCommand("text", pos, {"content": content, "color": color}))
        self._imgui_text(pos, content, color)

    def rect(
        self,
        pos: tuple[int, int],
        size: tuple[int, int],
        color: Color = (1.0, 1.0, 1.0, 1.0),
        filled: bool = True,
    ) -> None:
        """직사각형을 그린다. 완전히 화면 밖이면 clip."""
        x, y = pos
        w, h = size
        if x + w < 0 or y + h < 0 or x > self.width or y > self.height:
            return
        self._commands.append(
            DrawCommand("rect", pos, {"size": size, "color": color, "filled": filled})
        )
        self._imgui_rect(pos, size, color, filled)

    def clear(self) -> None:
        """커맨드 버퍼를 비운다."""
        self._commands.clear()

    # ── 상태 접근 ────────────────────────────────────────────────────────────

    @property
    def command_count(self) -> int:
        return len(self._commands)

    @property
    def commands(self) -> list[DrawCommand]:
        return list(self._commands)

    def to_numpy(self) -> np.ndarray:
        """커맨드 버퍼를 RGBA uint8 이미지로 래스터화 (간단한 소프트 렌더)."""
        buf = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        for cmd in self._commands:
            if cmd.kind == "rect":
                x, y = cmd.pos
                w, h = cmd.args["size"]
                r, g, b, a = cmd.args["color"]
                x0, x1 = max(0, x), min(self.width, x + w)
                y0, y1 = max(0, y), min(self.height, y + h)
                buf[y0:y1, x0:x1] = [int(r * 255), int(g * 255), int(b * 255), int(a * 255)]
        return buf

    # ── 내부 ─────────────────────────────────────────────────────────────────

    def _in_bounds(self, pos: tuple[int, int]) -> bool:
        x, y = pos
        return 0 <= x <= self.width and 0 <= y <= self.height

    def _imgui_text(self, pos: tuple[int, int], content: str, color: Color) -> None:
        ig = get_imgui()
        if ig is None:
            return
        try:
            draw_list = ig.get_foreground_draw_list()
            col = ig.get_color_u32_rgba(*color)
            draw_list.add_text((float(pos[0]), float(pos[1])), col, content)
        except Exception:
            pass

    def _imgui_rect(
        self, pos: tuple[int, int], size: tuple[int, int], color: Color, filled: bool
    ) -> None:
        ig = get_imgui()
        if ig is None:
            return
        try:
            draw_list = ig.get_foreground_draw_list()
            col = ig.get_color_u32_rgba(*color)
            x, y = float(pos[0]), float(pos[1])
            x2, y2 = x + size[0], y + size[1]
            if filled:
                draw_list.add_rect_filled((x, y), (x2, y2), col)
            else:
                draw_list.add_rect((x, y), (x2, y2), col)
        except Exception:
            pass
