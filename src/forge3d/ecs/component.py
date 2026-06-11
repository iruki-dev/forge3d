"""내장 ECS 컴포넌트 정의."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    pass


class Component:
    """모든 ECS 컴포넌트의 기반 클래스."""


class MeshRenderer(Component):
    """Visual mesh + material component for an ECS entity.

    Two equivalent ways to construct:

    .. code-block:: python

        # Convenience: shape + size derive mesh_id automatically
        f3d.MeshRenderer(shape="box", size=(1, 1, 1))
        f3d.MeshRenderer(shape="sphere", size=(0.5,))

        # Explicit mesh_id (advanced)
        f3d.MeshRenderer(mesh_id="box_2x1x0.5", material_id="metal")
    """

    def __init__(
        self,
        mesh_id: str = "",
        material_id: str = "default",
        *,
        shape: str = "",
        size: Any = None,
    ) -> None:
        if shape:
            self.mesh_id = _shape_to_mesh_id(shape, size)
        else:
            self.mesh_id = mesh_id or "box_1x1x1"
        self.material_id = material_id

    def __repr__(self) -> str:
        return f"MeshRenderer(mesh_id={self.mesh_id!r}, material_id={self.material_id!r})"


def _shape_to_mesh_id(shape: str, size: Any) -> str:
    """Derive a mesh_id string from a shape name and optional size."""
    s = shape.lower()
    if s == "sphere":
        r = (
            float(size[0])
            if size is not None and hasattr(size, "__getitem__")
            else (float(size) if size is not None else 0.5)
        )
        return f"sphere_{r}"
    if s == "capsule":
        return "capsule"
    # box (default)
    if size is not None and hasattr(size, "__len__") and len(size) >= 3:
        w, h, d = float(size[0]), float(size[1]), float(size[2])
        return f"box_{w}x{h}x{d}"
    return "box_1x1x1"


@dataclass
class Rigidbody(Component):
    mass: float = 1.0
    is_static: bool = False
    _body_ref: Any = field(default=None, repr=False)


@dataclass
class Collider(Component):
    shape: str = "box"  # "box" | "sphere" | "capsule"
    size: np.ndarray = field(default_factory=lambda: np.ones(3))


@dataclass
class CameraComponent(Component):
    fov_deg: float = 45.0
    near: float = 0.1
    far: float = 200.0


@dataclass
class LightComponent(Component):
    direction: np.ndarray = field(default_factory=lambda: np.array([1.0, 1.0, -1.0]))
    color: np.ndarray = field(default_factory=lambda: np.ones(3))
    intensity: float = 1.0


@dataclass
class Script(Component):
    on_start: Callable | None = field(default=None, repr=False)
    on_update: Callable[[float], None] | None = field(default=None, repr=False)
    _started: bool = field(default=False, repr=False)
