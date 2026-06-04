"""Prefab — 엔티티+컴포넌트 템플릿 JSON 직렬화/인스턴스화."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from forge3d.ecs.component import Collider, MeshRenderer, Rigidbody
from forge3d.ecs.serialization import _deserialize_comp, _serialize_comp
from forge3d.ecs.transform import Transform

if TYPE_CHECKING:
    from forge3d.ecs.entity import Entity, EntityWorld
    from forge3d.scene.node import SceneNode


@dataclass
class PrefabNode:
    """Prefab 내 단일 노드 정의."""

    name: str
    components: list[dict[str, Any]] = field(default_factory=list)
    children: list["PrefabNode"] = field(default_factory=list)


class Prefab:
    """재사용 가능한 엔티티+컴포넌트 묶음 템플릿.

    JSON 파일에서 로드하거나 SceneNode 트리에서 생성할 수 있다.
    """

    def __init__(self, root_node: PrefabNode) -> None:
        self._root = root_node

    # ── 저장 / 로드 ──────────────────────────────────────────────────────────

    @staticmethod
    def save(node: "SceneNode", path: str | Path) -> None:
        """SceneNode 트리를 JSON Prefab 파일로 저장한다."""
        data = _scene_node_to_dict(node)
        Path(path).write_text(json.dumps(data, indent=2))

    @staticmethod
    def load(path: str | Path) -> "Prefab":
        """JSON 파일에서 Prefab을 로드한다."""
        data = json.loads(Path(path).read_text())
        root = _dict_to_prefab_node(data)
        return Prefab(root)

    # ── 인스턴스화 ───────────────────────────────────────────────────────────

    def instantiate(
        self,
        ew: "EntityWorld",
        position: np.ndarray | None = None,
        rotation: np.ndarray | None = None,
    ) -> "SceneNode":
        """Prefab을 EntityWorld에 인스턴스화하고 SceneNode 트리를 반환한다."""
        from forge3d.scene.node import SceneNode

        root_node = _instantiate_node(self._root, ew, parent_entity=None)

        # 루트 위치/회전 오버라이드
        if position is not None or rotation is not None:
            try:
                tf: Transform = ew.get_component(root_node.entity, Transform)
                if position is not None:
                    tf.position = np.asarray(position, dtype=np.float64)
                if rotation is not None:
                    tf.rotation = np.asarray(rotation, dtype=np.float64)
                root_node._mark_dirty()
            except KeyError:
                pass

        return root_node


# ── 내부 헬퍼 ────────────────────────────────────────────────────────────────

_SAVEABLE_COMPONENTS = {
    "Transform": Transform,
    "MeshRenderer": MeshRenderer,
    "Rigidbody": Rigidbody,
    "Collider": Collider,
}


def _scene_node_to_dict(node: "SceneNode") -> dict[str, Any]:
    comps = node._ew.components_of(node.entity)
    comp_list = []
    for typ, comp in comps.items():
        if typ.__name__ in _SAVEABLE_COMPONENTS:
            comp_list.append({"type": typ.__name__, "data": _serialize_comp(comp)})
    return {
        "name": node.name,
        "components": comp_list,
        "children": [_scene_node_to_dict(c) for c in node.children],
    }


def _dict_to_prefab_node(data: dict[str, Any]) -> PrefabNode:
    children = [_dict_to_prefab_node(c) for c in data.get("children", [])]
    return PrefabNode(
        name=data.get("name", "node"),
        components=data.get("components", []),
        children=children,
    )


def _instantiate_node(
    pnode: PrefabNode,
    ew: "EntityWorld",
    parent_entity: "Entity | None",
) -> "SceneNode":
    from forge3d.scene.node import SceneNode

    # 컴포넌트 역직렬화
    comps = []
    for cd in pnode.components:
        try:
            comps.append(_deserialize_comp(cd["type"], cd["data"]))
        except (KeyError, ValueError):
            pass

    # ECS 엔티티 생성 (Transform이 없으면 추가)
    has_tf = any(c["type"] == "Transform" for c in pnode.components)
    if not has_tf:
        comps.insert(0, Transform())

    entity = ew.create_entity(*comps)

    # ECS Transform.parent 연결
    if parent_entity is not None:
        try:
            tf: Transform = ew.get_component(entity, Transform)
            tf.parent = parent_entity
        except KeyError:
            pass

    scene_node = SceneNode(name=pnode.name, entity=entity, ew=ew)

    for child_pnode in pnode.children:
        child_scene_node = _instantiate_node(child_pnode, ew, parent_entity=entity)
        scene_node.children.append(child_scene_node)
        child_scene_node.parent = scene_node

    return scene_node
