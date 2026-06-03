"""Robot model configuration — simple Python dict/dataclass format.

Usage:
    from forge3d.model.robot_config import LinkConfig, JointConfig, build_model

This is the "URDF-like" loader for Phase 2.  Instead of parsing XML, the robot
is described as a Python list of (JointConfig, LinkConfig) pairs which is then
assembled into a RigidBodyModel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from forge3d.dynamics.model import RigidBodyModel
from forge3d.math.se3 import rot_x
from forge3d.math.spatial import Xpose, spatial_inertia


@dataclass
class LinkConfig:
    """Physical properties of one link."""

    mass: float
    com: Any = field(default_factory=lambda: np.zeros(3))  # in link (joint) frame
    inertia: Any = field(default_factory=lambda: np.zeros((3, 3)))  # Icm, 3x3

    def __post_init__(self) -> None:
        self.com = np.asarray(self.com, dtype=float)
        self.inertia = np.asarray(self.inertia, dtype=float)


@dataclass
class JointConfig:
    """Kinematic properties of one joint.

    parent   : index of parent link (-1 = world base).
    type     : 'revolute' | 'prismatic'.
    axis     : joint axis in the child link's joint frame (usually [0,0,1]).
    origin_xyz : position of the joint origin in the PARENT frame, at q=0.
    origin_R   : 3x3 rotation of the child joint frame relative to parent, at q=0.
                 (active rotation, columns = child axes in parent coords.)
    """

    parent: int
    type: str = "revolute"
    axis: Any = field(default_factory=lambda: np.array([0.0, 0.0, 1.0]))
    origin_xyz: Any = field(default_factory=lambda: np.zeros(3))
    origin_R: Any = field(default_factory=lambda: np.eye(3))

    def __post_init__(self) -> None:
        self.axis = np.asarray(self.axis, dtype=float)
        self.origin_xyz = np.asarray(self.origin_xyz, dtype=float)
        self.origin_R = np.asarray(self.origin_R, dtype=float)


def build_model(
    joints: list[JointConfig],
    links: list[LinkConfig],
    gravity: Any = None,
) -> RigidBodyModel:
    """Assemble a RigidBodyModel from joint and link configuration lists.

    len(joints) == len(links) == n_links.
    joints[i].parent is the parent link index (-1 = base).
    """
    if len(joints) != len(links):
        raise ValueError("joints and links must have the same length")

    n = len(joints)
    if gravity is None:
        gravity = np.array([0.0, 0.0, -9.81])

    X_tree = np.empty((n, 6, 6))
    S = np.zeros((n, 6))
    I_link = np.empty((n, 6, 6))

    for i, (jc, lc) in enumerate(zip(joints, links, strict=True)):
        # ── tree transform: Xpose(origin_R, origin_xyz) ───────────────────────
        X_tree[i] = Xpose(jc.origin_R, jc.origin_xyz)

        # ── joint subspace ─────────────────────────────────────────────────────
        axis = np.asarray(jc.axis, dtype=float)
        axis_n = axis / (np.linalg.norm(axis) + 1e-300)
        if jc.type == "revolute":
            S[i, :3] = axis_n  # angular part
        elif jc.type == "prismatic":
            S[i, 3:] = axis_n  # linear part
        else:
            raise ValueError(f"Unknown joint type: {jc.type!r}")

        # ── spatial inertia ────────────────────────────────────────────────────
        I_link[i] = spatial_inertia(lc.mass, lc.com, lc.inertia)

    parents = [jc.parent for jc in joints]

    return RigidBodyModel(
        n_links=n,
        parent=parents,
        X_tree=X_tree,
        S=S,
        I_link=I_link,
        gravity=np.asarray(gravity, dtype=float),
    )


# ── DH parameter helpers ──────────────────────────────────────────────────────


def dh_joint(parent: int, d: float, a: float, alpha: float) -> JointConfig:
    """Standard DH convention → JointConfig (joint rotates about z-axis).

    At q=0: transform from parent to child is:
        T = Trans(x, a) * Trans(z, d) * Rot(x, alpha)
      = make_se3(Rx(alpha), [a, 0, d])
    """
    return JointConfig(
        parent=parent,
        type="revolute",
        axis=np.array([0.0, 0.0, 1.0]),
        origin_xyz=np.array([a, 0.0, d]),
        origin_R=rot_x(alpha),
    )


def rod_link(mass: float, length: float) -> LinkConfig:
    """Uniform cylindrical rod of given mass and length (along x-axis from joint)."""
    Ixx = 0.0
    Iyy = mass * length**2 / 12.0
    Izz = mass * length**2 / 12.0
    return LinkConfig(
        mass=mass,
        com=np.array([length / 2.0, 0.0, 0.0]),
        inertia=np.diag([Ixx, Iyy, Izz]),
    )
