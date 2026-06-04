"""ImGui 백엔드 — imgui-bundle 자동 감지, 없으면 null 드라이버."""
from __future__ import annotations

import os
from typing import Any

_USE_IMGUI = os.environ.get("USE_IMGUI", "auto").lower()
_imgui: Any = None

if _USE_IMGUI != "0":
    try:
        from imgui_bundle import imgui as _imgui_mod  # type: ignore[import]
        _imgui = _imgui_mod
    except ImportError:
        try:
            import imgui as _imgui_mod2  # type: ignore[import]
            _imgui = _imgui_mod2
        except ImportError:
            _imgui = None


def has_imgui() -> bool:
    return _imgui is not None


def get_imgui() -> Any:
    """ImGui 모듈 반환. 없으면 None."""
    return _imgui


class NullImGui:
    """ImGui 없는 환경용 no-op 스텁 — 테스트에서 사용."""

    def __init__(self) -> None:
        self._calls: list[tuple[str, tuple]] = []

    def begin(self, title: str, *args: Any) -> tuple[bool, bool]:
        self._calls.append(("begin", (title,)))
        return True, True

    def end(self) -> None:
        self._calls.append(("end", ()))

    def text(self, msg: str) -> None:
        self._calls.append(("text", (msg,)))

    def separator(self) -> None:
        self._calls.append(("separator", ()))

    def tree_node(self, label: str) -> bool:
        self._calls.append(("tree_node", (label,)))
        return True

    def tree_pop(self) -> None:
        self._calls.append(("tree_pop", ()))

    def selectable(self, label: str, selected: bool = False) -> tuple[bool, bool]:
        return False, selected

    def input_float3(self, label: str, values: list[float]) -> tuple[bool, list[float]]:
        return False, values

    def input_float(self, label: str, value: float) -> tuple[bool, float]:
        return False, value

    @property
    def call_count(self) -> int:
        return len(self._calls)

    def clear(self) -> None:
        self._calls.clear()
