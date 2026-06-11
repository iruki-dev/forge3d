"""System ABC + 내장 시스템."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import numpy as np

from forge3d.ecs.component import LightComponent, MeshRenderer, Rigidbody, Script
from forge3d.ecs.transform import Transform

if TYPE_CHECKING:
    from forge3d.ecs.entity import EntityWorld

logger = logging.getLogger(__name__)


class System(ABC):
    """ECS 시스템 기반 클래스."""

    @abstractmethod
    def update(self, ew: EntityWorld, dt: float) -> None: ...


class ScriptSystem(System):
    """Script 컴포넌트의 on_start/on_update 콜백을 실행한다."""

    def update(self, ew: EntityWorld, dt: float) -> None:
        for _e, script in ew.query(Script):
            s: Script = script  # type: ignore[assignment]
            if not s._started and s.on_start is not None:
                try:
                    s.on_start()
                except Exception as exc:
                    logger.warning("Script.on_start 오류: %s", exc)
                s._started = True
            if s.on_update is not None:
                try:
                    s.on_update(dt)
                except Exception as exc:
                    logger.warning("Script.on_update 오류: %s", exc)


class PhysicsSystem(System):
    """Rigidbody 엔티티를 v1 World에 동기화하고 물리 스텝을 실행한다.

    동작:
      1. ECS Transform → v1 Body 위치 동기화
      2. v1 World.step()
      3. v1 Body 위치 → ECS Transform 역동기화
    """

    def __init__(self, world: Any | None = None) -> None:
        self._world = world  # forge3d.facade.World

    def attach_world(self, world: Any) -> None:
        self._world = world

    def update(self, ew: EntityWorld, dt: float) -> None:
        if self._world is None:
            return

        # ECS → v1 동기화 (정적 바디는 건너뜀)
        for _e, tf, rb in ew.query(Transform, Rigidbody):
            transform: Transform = tf  # type: ignore[assignment]
            rigidbody: Rigidbody = rb  # type: ignore[assignment]
            body = rigidbody._body_ref
            if body is not None and not getattr(body, "is_static", rigidbody.is_static):
                if hasattr(body, "set_position"):
                    body.set_position(tuple(transform.position))
                if hasattr(body, "set_orientation"):
                    body.set_orientation(tuple(transform.rotation))

        # 물리 스텝
        self._world.step(dt)

        # v1 → ECS 역동기화
        for _e, tf, rb in ew.query(Transform, Rigidbody):
            transform = tf  # type: ignore[assignment]
            rigidbody = rb  # type: ignore[assignment]
            body = rigidbody._body_ref
            if body is not None:
                transform.position = np.asarray(body.position, dtype=np.float64).copy()
                if hasattr(body, "orientation"):
                    transform.rotation = np.asarray(body.orientation, dtype=np.float64).copy()


class RenderSystem(System):
    """ECS Transform + MeshRenderer → SceneSnapshot 생성.

    last_snapshot 속성에 가장 최근 스냅샷을 저장한다.
    """

    def __init__(self) -> None:
        self.last_snapshot: Any = None

    def update(self, ew: EntityWorld, dt: float) -> None:
        from forge3d.render.snapshot import (
            BodySnapshot,
            LightSnapshot,
            SceneSnapshot,
        )
        from forge3d.render.snapshot import (
            Transform as RenderTransform,
        )

        bodies = []
        cam_snap = None
        lights = []

        for e, tf, mr in ew.query(Transform, MeshRenderer):
            transform: Transform = tf  # type: ignore[assignment]
            mesh_renderer: MeshRenderer = mr  # type: ignore[assignment]
            wm = transform.world_matrix(ew)
            pos = wm[:3, 3]
            rot = wm[:3, :3]
            shape_type, shape_params = _mesh_id_to_shape(mesh_renderer.mesh_id)
            bodies.append(
                BodySnapshot(
                    name=f"e{e}",
                    transform=RenderTransform(position=pos, rotation=rot),
                    shape_type=shape_type,
                    shape_params=shape_params,
                    material_id=mesh_renderer.material_id,
                )
            )

        for _e, tf, lc in ew.query(Transform, LightComponent):
            transform = tf  # type: ignore[assignment]
            light: LightComponent = lc  # type: ignore[assignment]
            lights.append(
                LightSnapshot(
                    direction=np.asarray(light.direction),
                    color=np.asarray(light.color),
                    intensity=light.intensity,
                )
            )

        self.last_snapshot = SceneSnapshot(
            bodies=bodies,
            lights=lights,
            camera=cam_snap,
        )


def _mesh_id_to_shape(mesh_id: str) -> tuple[str, dict]:
    """Parse a mesh_id string into (shape_type, shape_params).

    Supported formats:
    - ``"sphere"`` or ``"sphere_<r>"``   → sphere with given radius (default 0.5)
    - ``"capsule"`` or ``"capsule_*"``   → capsule (radius 0.3, half_length 0.5)
    - ``"box_WxHxD"`` or ``"box_S"``    → box with half-extents W/2 × H/2 × D/2
    """
    if mesh_id.startswith("sphere"):
        parts = mesh_id.split("_", 1)
        try:
            radius = float(parts[1]) if len(parts) > 1 else 0.5
        except ValueError:
            radius = 0.5
        return "sphere", {"radius": radius}
    if mesh_id.startswith("capsule"):
        return "capsule", {"radius": 0.3, "half_length": 0.5}
    # box (default)
    size_part = mesh_id.replace("box_", "").split("x")
    try:
        he = [float(s) / 2.0 for s in size_part]
        if len(he) == 1:
            he = he * 3
    except ValueError:
        he = [0.5, 0.5, 0.5]
    return "box", {"half_extents": he[:3] if len(he) >= 3 else [0.5, 0.5, 0.5]}
