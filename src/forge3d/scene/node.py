"""SceneNode — 이름 있는 씬 트리 노드 (dirty flag 캐시 포함)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from forge3d.ecs.transform import Transform
from forge3d.errors import Forge3dError

if TYPE_CHECKING:
    from forge3d.ecs.entity import Entity, EntityWorld
else:
    Entity = int


class SceneNode:
    """씬 계층 트리의 단일 노드.

    ECS Transform을 감싸 부모/자식 계층을 관리하고
    월드 행렬을 dirty flag로 캐시한다.
    """

    def __init__(
        self,
        name: str,
        entity: Entity,
        ew: EntityWorld,
    ) -> None:
        self.name = name
        self.entity = entity
        self._ew = ew
        self.children: list[SceneNode] = []
        self.parent: SceneNode | None = None
        self._dirty: bool = True
        self._cached_world: np.ndarray = np.eye(4, dtype=np.float64)

    # ── 자식 관리 ─────────────────────────────────────────────────────────────

    def add_child(self, child: SceneNode) -> None:
        if child is self:
            raise Forge3dError("SceneNode는 자기 자신을 자식으로 가질 수 없습니다")
        if child.parent is not None:
            child.parent.remove_child(child)
        child.parent = self
        self.children.append(child)
        # ECS Transform parent 동기화
        try:
            child_tf: Transform = self._ew.get_component(child.entity, Transform)
            child_tf.parent = self.entity
        except KeyError:
            pass
        child._mark_dirty()

    def remove_child(self, child: SceneNode) -> None:
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            try:
                child_tf: Transform = self._ew.get_component(child.entity, Transform)
                child_tf.parent = None
            except KeyError:
                pass
            child._mark_dirty()

    # ── 변환 접근 ─────────────────────────────────────────────────────────────

    @property
    def transform(self) -> Transform:
        return self._ew.get_component(self.entity, Transform)

    @property
    def local_position(self) -> np.ndarray:
        return self.transform.position

    @local_position.setter
    def local_position(self, pos: np.ndarray) -> None:
        self.transform.position = np.asarray(pos, dtype=np.float64)
        self._mark_dirty()

    @property
    def local_rotation(self) -> np.ndarray:
        return self.transform.rotation

    @local_rotation.setter
    def local_rotation(self, q: np.ndarray) -> None:
        self.transform.rotation = np.asarray(q, dtype=np.float64)
        self._mark_dirty()

    def world_matrix(self) -> np.ndarray:
        """(4,4) 월드 변환 행렬 (dirty flag 캐시)."""
        if self._dirty:
            self._cached_world = self.transform.world_matrix(self._ew)
            self._dirty = False
        return self._cached_world

    def world_position(self) -> np.ndarray:
        return self.world_matrix()[:3, 3]

    def world_rotation(self) -> np.ndarray:
        return self.world_matrix()[:3, :3]

    # ── dirty propagation ────────────────────────────────────────────────────

    def _mark_dirty(self) -> None:
        """자신과 모든 자식을 dirty로 표시한다."""
        self._dirty = True
        for child in self.children:
            child._mark_dirty()

    # ── 유틸 ─────────────────────────────────────────────────────────────────

    def find(self, name: str) -> SceneNode | None:
        """이름으로 자신 또는 하위 노드를 검색한다."""
        if self.name == name:
            return self
        for child in self.children:
            found = child.find(name)
            if found:
                return found
        return None

    def descendants(self) -> list[SceneNode]:
        """자신을 포함한 모든 하위 노드 리스트."""
        result = [self]
        for child in self.children:
            result.extend(child.descendants())
        return result

    def __repr__(self) -> str:
        return f"SceneNode(name={self.name!r}, entity={self.entity}, children={len(self.children)})"
