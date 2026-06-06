"""UI 패널 — DebugPanel, InspectorPanel, HierarchyPanel.

ImGui가 없으면 내부 상태만 업데이트하고 렌더는 skip.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from forge3d.ui.backend import NullImGui, get_imgui

if TYPE_CHECKING:
    from forge3d.ecs.entity import Entity, EntityWorld


# ── DebugPanel ────────────────────────────────────────────────────────────────


@dataclass
class DebugPanelState:
    fps: float = 0.0
    body_count: int = 0
    step_ms: float = 0.0
    frame_count: int = 0


class DebugPanel:
    """FPS, 바디 수, 물리 스텝 시간을 표시하는 패널."""

    def __init__(self, title: str = "Debug") -> None:
        self.title = title
        self.state = DebugPanelState()
        self._null = NullImGui()

    def render(self, fps: float, body_count: int = 0, step_ms: float = 0.0) -> None:
        """상태를 업데이트하고 ImGui 가용 시 렌더한다."""
        self.state.fps = fps
        self.state.body_count = body_count
        self.state.step_ms = step_ms
        self.state.frame_count += 1

        ig = get_imgui()
        if ig is None:
            self._null.text(f"FPS: {fps:.1f}")
            self._null.text(f"Bodies: {body_count}")
            self._null.text(f"Step: {step_ms:.2f}ms")
            return

        try:
            ig.begin(self.title)
            ig.text(f"FPS:    {fps:.1f}")
            ig.text(f"Bodies: {body_count}")
            ig.text(f"Step:   {step_ms:.2f} ms")
            ig.separator()
            ig.text(f"Frame:  {self.state.frame_count}")
            ig.end()
        except Exception:
            pass


# ── InspectorPanel ────────────────────────────────────────────────────────────


@dataclass
class InspectorState:
    selected: Entity | None = None
    last_edited_field: str = ""
    last_edited_value: object = None


class InspectorPanel:
    """선택된 ECS 엔티티의 컴포넌트를 표시·편집하는 패널."""

    def __init__(self, title: str = "Inspector") -> None:
        self.title = title
        self.state = InspectorState()

    def select(self, entity: Entity | None) -> None:
        """선택 엔티티를 변경한다."""
        self.state.selected = entity

    def render(self, ew: EntityWorld, selected: Entity | None = None) -> None:
        """컴포넌트 필드를 표시하고 ImGui 가용 시 편집 가능하게 한다."""
        if selected is not None:
            self.state.selected = selected

        e = self.state.selected
        if e is None or not ew.is_alive(e):
            return

        comps = ew.components_of(e)

        ig = get_imgui()
        if ig is None:
            self._render_null(e, comps, ew)
            return

        try:
            ig.begin(self.title)
            ig.text(f"Entity: {e}")
            ig.separator()
            for typ, comp in comps.items():
                self._render_component_imgui(ig, typ, comp, ew, e)
            ig.end()
        except Exception:
            pass

    def _render_null(self, e: Entity, comps: dict, ew: EntityWorld) -> None:
        """ImGui 없는 환경에서 컴포넌트 편집 (직접 값 설정)."""
        from forge3d.ecs.transform import Transform

        for _typ, comp in comps.items():
            if isinstance(comp, Transform):
                # last_edited_field로 테스트 가능한 편집 경로
                if self.state.last_edited_field == "position":
                    comp.position = np.asarray(self.state.last_edited_value, dtype=np.float64)

    def _render_component_imgui(
        self, ig: Any, typ: type, comp: Any, ew: EntityWorld, e: Entity
    ) -> None:
        from forge3d.ecs.component import Rigidbody
        from forge3d.ecs.transform import Transform

        name = typ.__name__
        try:
            if ig.tree_node(name):
                if isinstance(comp, Transform):
                    pos = comp.position.tolist()
                    changed, new_pos = ig.input_float3("position", pos)
                    if changed:
                        comp.position = np.array(new_pos)
                        self.state.last_edited_field = "position"
                        self.state.last_edited_value = new_pos
                elif isinstance(comp, Rigidbody):
                    changed, new_mass = ig.input_float("mass", float(comp.mass))
                    if changed:
                        comp.mass = new_mass
                ig.tree_pop()
        except Exception:
            pass

    def set_field(self, field: str, value: object) -> None:
        """테스트용: 직접 필드 편집 트리거."""
        self.state.last_edited_field = field
        self.state.last_edited_value = value


# ── HierarchyPanel ────────────────────────────────────────────────────────────


class HierarchyPanel:
    """ECS 엔티티 목록을 표시하고 선택할 수 있는 패널."""

    def __init__(self, title: str = "Hierarchy") -> None:
        self.title = title
        self._selected: Entity | None = None
        self._entity_list: list[int] = []

    @property
    def selected(self) -> Entity | None:
        return self._selected

    def render(self, ew: EntityWorld, inspector: InspectorPanel | None = None) -> None:
        self._entity_list = list(ew.all_entities())

        ig = get_imgui()
        if ig is None:
            return  # 테스트에서는 entity_list만 갱신

        try:
            ig.begin(self.title)
            for e in self._entity_list:
                if not ew.is_alive(e):
                    continue
                is_selected = e == self._selected
                clicked, _ = ig.selectable(f"Entity {e}", is_selected)
                if clicked:
                    self._selected = e
                    if inspector:
                        inspector.select(e)
            ig.end()
        except Exception:
            pass

    def select(self, entity: Entity) -> None:
        self._selected = entity

    @property
    def entity_count(self) -> int:
        return len(self._entity_list)
