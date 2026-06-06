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


@dataclass
class MeshRenderer(Component):
    mesh_id: str = "box_1x1"
    material_id: str = "default"


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
