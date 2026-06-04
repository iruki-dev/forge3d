"""Gizmo — 이동/회전/스케일 기즈모 + 레이캐스트 엔티티 선택.

ImGui 없이도 순수 Python 로직으로 동작한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from forge3d.ecs.entity import Entity, EntityWorld
    from forge3d.ecs.transform import Transform


class GizmoMode(Enum):
    TRANSLATE = auto()
    ROTATE = auto()
    SCALE = auto()


@dataclass
class GizmoState:
    """기즈모 현재 상태."""
    selected: "Entity | None" = None
    mode: GizmoMode = GizmoMode.TRANSLATE
    dragging: bool = False
    drag_axis: int = -1       # 0=X, 1=Y, 2=Z, -1=없음
    drag_delta: np.ndarray = field(default_factory=lambda: np.zeros(3))


class TranslateGizmo:
    """선택 엔티티의 위치를 축별로 이동시키는 기즈모."""

    def __init__(self) -> None:
        self.state = GizmoState()

    # ── 엔티티 선택 (레이캐스트) ─────────────────────────────────────────────

    def pick(
        self,
        ray_origin: np.ndarray,
        ray_dir: np.ndarray,
        ew: "EntityWorld",
        max_dist: float = 100.0,
    ) -> "Entity | None":
        """화면 레이로 가장 가까운 엔티티를 선택한다.

        각 엔티티의 AABB 구(半경 1m 기본)에 레이-구 교차 테스트.
        """
        from forge3d.ecs.transform import Transform

        best_t = max_dist
        best_entity: "Entity | None" = None

        for e, tf in ew.query(Transform):
            transform: Transform = tf  # type: ignore[assignment]
            pos = transform.position
            t = _ray_sphere_intersect(ray_origin, ray_dir, pos, radius=1.0)
            if t is not None and 0 < t < best_t:
                best_t = t
                best_entity = int(e)

        self.state.selected = best_entity
        return best_entity

    # ── 기즈모 드래그 ─────────────────────────────────────────────────────────

    def start_drag(self, axis: int) -> None:
        """축 드래그 시작 (0=X, 1=Y, 2=Z)."""
        self.state.dragging = True
        self.state.drag_axis = axis

    def drag(self, delta: float, ew: "EntityWorld") -> None:
        """delta 거리만큼 선택 축을 따라 엔티티를 이동한다."""
        if not self.state.dragging or self.state.selected is None:
            return
        from forge3d.ecs.transform import Transform
        try:
            tf: Transform = ew.get_component(self.state.selected, Transform)
        except (KeyError, Exception):
            return

        axis = self.state.drag_axis
        if 0 <= axis <= 2:
            tf.position = tf.position.copy()
            tf.position[axis] += delta

    def end_drag(self) -> None:
        self.state.dragging = False
        self.state.drag_axis = -1

    def select(self, entity: "Entity | None") -> None:
        self.state.selected = entity


# ── 레이-구 교차 ─────────────────────────────────────────────────────────────

def _ray_sphere_intersect(
    origin: np.ndarray,
    direction: np.ndarray,
    center: np.ndarray,
    radius: float,
) -> float | None:
    """레이와 구의 교차 거리 t를 반환한다. 교차 없으면 None."""
    oc = np.asarray(origin) - np.asarray(center)
    d = np.asarray(direction)
    d_norm = np.linalg.norm(d)
    if d_norm < 1e-12:
        return None
    d = d / d_norm

    b = 2.0 * float(oc.dot(d))
    c = float(oc.dot(oc)) - radius * radius
    disc = b * b - 4.0 * c
    if disc < 0:
        return None
    t = (-b - np.sqrt(disc)) * 0.5
    if t < 0:
        t = (-b + np.sqrt(disc)) * 0.5
    return float(t) if t >= 0 else None


def screen_to_ray(
    screen_x: float,
    screen_y: float,
    width: int,
    height: int,
    fov_deg: float,
    view_matrix: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """화면 좌표 → 월드 공간 레이 (origin, direction).

    view_matrix: (4,4) 카메라 뷰 행렬.
    """
    aspect = width / height
    tan_half_fov = np.tan(np.radians(fov_deg) * 0.5)

    ndc_x = (2.0 * screen_x / width - 1.0) * aspect * tan_half_fov
    ndc_y = (1.0 - 2.0 * screen_y / height) * tan_half_fov

    # 카메라 공간에서 레이 방향 (z=-1이 앞)
    ray_cam = np.array([ndc_x, ndc_y, -1.0])

    # 월드 공간으로 변환
    inv_view = np.linalg.inv(view_matrix)
    ray_world = inv_view[:3, :3] @ ray_cam
    ray_world /= np.linalg.norm(ray_world) + 1e-12

    cam_pos = inv_view[:3, 3]
    return cam_pos, ray_world
