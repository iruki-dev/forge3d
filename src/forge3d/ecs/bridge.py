"""v1 Body ↔ ECS 엔티티 브릿지."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from forge3d.ecs.component import MeshRenderer, Rigidbody
from forge3d.ecs.transform import Transform

if TYPE_CHECKING:
    from forge3d.ecs.entity import Entity, EntityWorld


def body_to_entity(world: Any, body: Any, ew: "EntityWorld") -> "Entity":
    """기존 v1 Body를 ECS 엔티티로 래핑한다 (파괴적 변환 없음).

    Args:
        world: forge3d.World (v1 퍼사드)
        body:  forge3d.Body 인스턴스
        ew:    대상 EntityWorld

    Returns:
        생성된 Entity ID
    """
    pos = np.asarray(body.position, dtype=np.float64)
    quat = _body_quat(body)
    is_static = getattr(body, "is_static", getattr(body, "static", False))
    rb = Rigidbody(mass=body.mass, is_static=is_static, _body_ref=body)
    shape_type = getattr(body, "shape_type", "box")
    mesh_id = _shape_to_mesh_id(shape_type, body)

    transform = Transform(position=pos.copy(), rotation=quat.copy())
    mat_id = getattr(body, "material_id", None) or "default"
    mesh_renderer = MeshRenderer(mesh_id=mesh_id, material_id=mat_id)

    return ew.create_entity(transform, rb, mesh_renderer)


def sync_body_to_transform(body: Any, transform: Transform) -> None:
    """v1 Body 상태를 ECS Transform으로 복사한다."""
    transform.position = np.asarray(body.position, dtype=np.float64)
    transform.rotation = _body_quat(body)


def sync_transform_to_body(transform: Transform, body: Any) -> None:
    """ECS Transform을 v1 Body 위치로 복사한다 (teleport)."""
    if hasattr(body, "teleport"):
        body.teleport(transform.position)
    else:
        body._physics.update_body_pose(
            body._id, transform.position.copy(), transform.rotation.copy()
        )


def _body_quat(body: Any) -> np.ndarray:
    """Body에서 쿼터니언 [w,x,y,z]을 추출한다."""
    if hasattr(body, "orientation"):
        return np.asarray(body.orientation, dtype=np.float64)
    if hasattr(body, "quat"):
        return np.asarray(body.quat, dtype=np.float64)
    return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)


def _shape_to_mesh_id(shape_type: str, body: Any) -> str:
    if shape_type == "sphere":
        return "sphere_1"
    if shape_type == "capsule":
        return "capsule_1"
    sp = getattr(body, "shape_params", {})
    he = sp.get("half_extents", [0.5, 0.5, 0.5])
    return f"box_{he[0]*2:.1f}x{he[1]*2:.1f}x{he[2]*2:.1f}"
