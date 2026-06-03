"""Rigid body tree model for dynamics computations.

A model is a kinematic tree of links connected by 1-DOF joints (revolute or
prismatic).  All quantities are expressed in link-local coordinates.

Conventions:
  - Link indices are 0-based.  The base (world) is implicitly index -1.
  - parent[i]: index of parent link (-1 = base/world).
  - X_tree[i]: 6x6 spatial transform from parent link's frame to link i's
    joint frame (at zero configuration).  Shape: (n, 6, 6).
  - S[i]: 6-vector joint subspace (motion subspace).  Shape: (n, 6).
    Revolute about axis a: S = [a; 0].
    Prismatic along axis a: S = [0; a].
  - I[i]: 6x6 spatial inertia of link i in link i's frame.  Shape: (n, 6, 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from forge3d.math.spatial import Xpose, spatial_inertia


@dataclass
class RigidBodyModel:
    """Minimal tree model for RNEA / CRBA / ABA."""

    n_links: int
    parent: list[int]  # length n_links; -1 = base
    X_tree: Any  # (n_links, 6, 6) float64
    S: Any  # (n_links, 6)    float64  joint subspace
    I_link: Any  # (n_links, 6, 6) float64  spatial inertia
    gravity: Any  # (3,) gravity vector in world frame  e.g. [0,0,-9.81]


def make_2dof_arm(
    *,
    L1: float = 1.0,
    L2: float = 0.8,
    m1: float = 1.0,
    m2: float = 0.8,
    Izz1: float = 1.0 / 12.0,  # m*L^2/12 for uniform rod (normalised by m*L^2)
    Izz2: float = 1.0 / 12.0,
    gravity: Any = None,
) -> RigidBodyModel:
    """2-DOF revolute arm in the x-y plane, joints revolve about z-axis.

    Link 1: joint at world origin, CoM at L1/2 along x-axis of link frame.
    Link 2: joint at end of link 1 (L1 along x-axis), CoM at L2/2 along x.

    Izz1 / Izz2 are rotational inertia about z through CoM
    as a fraction of m*L^2.  Default: uniform rod = 1/12.
    """
    if gravity is None:
        gravity = np.array([0.0, -9.81, 0.0])  # gravity in -y (vertical plane)

    # ── Joint subspaces (revolute about z) ────────────────────────────────────
    S = np.zeros((2, 6))
    S[0, 2] = 1.0  # link 1: rotate about z  → omega_z component
    S[1, 2] = 1.0  # link 2: rotate about z

    # ── X_tree: from parent frame to joint frame (at q=0) ─────────────────────
    # Link 0: joint at world origin → identity
    X_tree_0 = np.eye(6)
    # Link 1: joint at end of link 1.  In link 1's frame (at q1=0) the
    #         joint-2 origin is at p = [L1, 0, 0] from link-1's origin.
    #         No relative rotation at q=0.
    X_tree_1 = Xpose(np.eye(3), np.array([L1, 0.0, 0.0]))

    X_tree = np.stack([X_tree_0, X_tree_1])  # (2,6,6)

    # ── Spatial inertias (in link frame, origin = joint) ──────────────────────
    # CoM of each link is at L/2 along x in the link's own frame.
    com1 = np.array([L1 / 2.0, 0.0, 0.0])
    com2 = np.array([L2 / 2.0, 0.0, 0.0])

    I1_cm = np.diag([0.0, 0.0, Izz1 * m1 * L1**2])
    I2_cm = np.diag([0.0, 0.0, Izz2 * m2 * L2**2])

    I_link = np.stack(
        [
            spatial_inertia(m1, com1, I1_cm),
            spatial_inertia(m2, com2, I2_cm),
        ]
    )  # (2,6,6)

    return RigidBodyModel(
        n_links=2,
        parent=[-1, 0],
        X_tree=X_tree,
        S=S,
        I_link=I_link,
        gravity=np.asarray(gravity, dtype=float),
    )
