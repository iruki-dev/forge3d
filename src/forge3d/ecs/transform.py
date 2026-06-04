"""Transform 컴포넌트 — 위치/회전/스케일 + 부모/자식 계층."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from forge3d.ecs.component import Component
from forge3d.errors import Forge3dError

if TYPE_CHECKING:
    from forge3d.ecs.entity import EntityWorld

Entity = int


@dataclass
class Transform(Component):
    """6-DOF 변환 + 계층 관계.

    rotation은 쿼터니언 [w, x, y, z] 형식.
    """

    position: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.float64))
    rotation: np.ndarray = field(
        default_factory=lambda: np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
    )
    scale: np.ndarray = field(default_factory=lambda: np.ones(3, dtype=np.float64))
    parent: Entity | None = None

    def local_matrix(self) -> np.ndarray:
        """(4,4) 로컬 변환 행렬."""
        M = np.eye(4, dtype=np.float64)
        M[:3, :3] = _quat_to_rot(self.rotation) * self.scale[None, :]
        M[:3, 3] = self.position
        return M

    def world_matrix(self, ew: "EntityWorld") -> np.ndarray:
        """(4,4) 월드 변환 행렬 (부모 계층 포함, 최대 깊이 64)."""
        chain: list[np.ndarray] = [self.local_matrix()]
        visited: set[Entity] = set()
        current = self.parent

        while current is not None:
            if current in visited:
                raise Forge3dError("순환 Transform 계층 감지됨")
            visited.add(current)
            try:
                parent_tf: Transform = ew.get_component(current, Transform)
            except KeyError:
                break
            chain.append(parent_tf.local_matrix())
            current = parent_tf.parent
            if len(chain) > 64:
                raise Forge3dError("Transform 계층이 64 깊이를 초과합니다")

        M = np.eye(4, dtype=np.float64)
        for mat in reversed(chain):
            M = M @ mat
        return M

    def world_position(self, ew: "EntityWorld") -> np.ndarray:
        return self.world_matrix(ew)[:3, 3]

    def world_rotation_matrix(self, ew: "EntityWorld") -> np.ndarray:
        return self.world_matrix(ew)[:3, :3]


def _quat_to_rot(q: np.ndarray) -> np.ndarray:
    """쿼터니언 [w,x,y,z] → 3×3 회전행렬."""
    w, x, y, z = q
    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - w*z),     2*(x*z + w*y)],
        [2*(x*y + w*z),     1 - 2*(x*x + z*z), 2*(y*z - w*x)],
        [2*(x*z - w*y),     2*(y*z + w*x),     1 - 2*(x*x + y*y)],
    ], dtype=np.float64)


def jax_batch_world_matrix(transforms: list[Transform]) -> np.ndarray:
    """루트 엔티티(parent=None)의 로컬 행렬을 JAX vmap으로 일괄 계산.

    부모 없는 엔티티만 처리하는 빠른 경로. 계층이 있으면 world_matrix()를 사용하라.
    Returns: (N, 4, 4) float64
    """
    if not transforms:
        return np.zeros((0, 4, 4))
    mats = np.stack([t.local_matrix() for t in transforms])
    return mats
