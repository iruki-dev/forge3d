"""ECS 씬 JSON 직렬화/역직렬화."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from forge3d.ecs.component import Collider, LightComponent, MeshRenderer, Rigidbody, Script
from forge3d.ecs.transform import Transform

if TYPE_CHECKING:
    from forge3d.ecs.entity import Entity, EntityWorld

_COMPONENT_REGISTRY: dict[str, type] = {
    "Transform": Transform,
    "MeshRenderer": MeshRenderer,
    "Rigidbody": Rigidbody,
    "Collider": Collider,
    "LightComponent": LightComponent,
}


def save_scene(ew: "EntityWorld", path: str | Path) -> None:
    """EntityWorld를 JSON 파일로 저장한다."""
    data: dict[str, Any] = {"entities": []}
    for e in ew.all_entities():
        comps = ew.components_of(e)
        comp_list = []
        for typ, comp in comps.items():
            if typ.__name__ not in _COMPONENT_REGISTRY:
                continue
            comp_list.append({"type": typ.__name__, "data": _serialize_comp(comp)})
        data["entities"].append({"id": e, "components": comp_list})
    Path(path).write_text(json.dumps(data, indent=2))


def load_scene(path: str | Path) -> "EntityWorld":
    """JSON 파일에서 EntityWorld를 재구성한다."""
    from forge3d.ecs.entity import EntityWorld

    raw = json.loads(Path(path).read_text())
    ew = EntityWorld()
    for ent_data in raw["entities"]:
        comps = [
            _deserialize_comp(cd["type"], cd["data"])
            for cd in ent_data["components"]
            if cd["type"] in _COMPONENT_REGISTRY
        ]
        ew.create_entity(*comps)
    return ew


# ── 직렬화 헬퍼 ──────────────────────────────────────────────────────────────

def _serialize_comp(comp: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(comp, Transform):
        out["position"] = comp.position.tolist()
        out["rotation"] = comp.rotation.tolist()
        out["scale"] = comp.scale.tolist()
        out["parent"] = comp.parent
    elif isinstance(comp, MeshRenderer):
        out["mesh_id"] = comp.mesh_id
        out["material_id"] = comp.material_id
    elif isinstance(comp, Rigidbody):
        out["mass"] = comp.mass
        out["is_static"] = comp.is_static
    elif isinstance(comp, Collider):
        out["shape"] = comp.shape
        out["size"] = comp.size.tolist()
    elif isinstance(comp, LightComponent):
        out["direction"] = comp.direction.tolist()
        out["color"] = comp.color.tolist()
        out["intensity"] = comp.intensity
    return out


def _deserialize_comp(type_name: str, data: dict[str, Any]) -> Any:
    typ = _COMPONENT_REGISTRY[type_name]
    if typ is Transform:
        return Transform(
            position=np.array(data["position"], dtype=np.float64),
            rotation=np.array(data["rotation"], dtype=np.float64),
            scale=np.array(data["scale"], dtype=np.float64),
            parent=data.get("parent"),
        )
    if typ is MeshRenderer:
        return MeshRenderer(mesh_id=data["mesh_id"], material_id=data.get("material_id", "default"))
    if typ is Rigidbody:
        return Rigidbody(mass=data["mass"], is_static=data["is_static"])
    if typ is Collider:
        return Collider(shape=data["shape"], size=np.array(data["size"], dtype=np.float64))
    if typ is LightComponent:
        return LightComponent(
            direction=np.array(data["direction"]),
            color=np.array(data["color"]),
            intensity=data["intensity"],
        )
    raise ValueError(f"알 수 없는 컴포넌트: {type_name}")
