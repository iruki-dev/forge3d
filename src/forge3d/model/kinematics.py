"""Forward kinematics and Jacobian for a RigidBodyModel.

All results are expressed in the world frame.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from forge3d.dynamics.model import RigidBodyModel
from forge3d.math.se3 import aa_to_rot, unskew


def _fk_frames(
    model: RigidBodyModel,
    q: Any,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Compute world-frame joint origin positions and link orientations.

    Returns
    -------
    p_world : list of (3,) arrays — world position of each link's joint origin.
    R_world : list of (3,3) arrays — world orientation of each link frame.
    """
    q = np.asarray(q, dtype=float)
    n = model.n_links

    p_world = [np.zeros(3)] * n
    R_world = [np.eye(3)] * n

    for i in range(n):
        X_t = model.X_tree[i]
        E = X_t[:3, :3]  # E = R_tree.T (Featherstone passive)
        R_tree = E.T  # active rotation
        p_tree = unskew(-(R_tree @ X_t[3:, :3]))

        axis = model.S[i][:3]
        n_ax = float(np.linalg.norm(axis))
        R_joint = aa_to_rot(axis / n_ax, q[i]) if n_ax > 1e-10 else np.eye(3)

        R_parent = np.eye(3) if model.parent[i] == -1 else R_world[model.parent[i]]
        p_parent = np.zeros(3) if model.parent[i] == -1 else p_world[model.parent[i]]

        p_world[i] = p_parent + R_parent @ p_tree
        R_world[i] = R_parent @ R_tree @ R_joint

    return p_world, R_world


def forward_kinematics(
    model: RigidBodyModel,
    q: Any,
    link_idx: int = -1,
    local_pos: Any = None,
) -> tuple[Any, Any]:
    """Compute world-frame pose (position, rotation) of a point on a link.

    Parameters
    ----------
    model     : RigidBodyModel
    q         : (n,) joint angles
    link_idx  : target link index (default: last link = end-effector)
    local_pos : (3,) offset from joint origin in link frame (default: zeros)

    Returns
    -------
    pos : (3,) world-frame position of the target point.
    R   : (3,3) world-frame orientation of the target link.
    """
    if link_idx == -1:
        link_idx = model.n_links - 1
    if local_pos is None:
        local_pos = np.zeros(3)
    local_pos = np.asarray(local_pos, dtype=float)

    p_world, R_world = _fk_frames(model, q)
    pos = p_world[link_idx] + R_world[link_idx] @ local_pos
    return pos, R_world[link_idx]


def jacobian(
    model: RigidBodyModel,
    q: Any,
    link_idx: int = -1,
    local_pos: Any = None,
) -> Any:
    """Geometric Jacobian J (6×n) mapping qd → [omega; v_ee].

    J = [[J_w], [J_v]] where J_w is the angular Jacobian and J_v is linear.

    Parameters
    ----------
    link_idx  : end-effector link index (default: last link).
    local_pos : (3,) offset from joint origin in link frame.

    Returns
    -------
    J : (6, n) Jacobian matrix.
    """
    if link_idx == -1:
        link_idx = model.n_links - 1
    if local_pos is None:
        local_pos = np.zeros(3)
    local_pos = np.asarray(local_pos, dtype=float)

    q = np.asarray(q, dtype=float)
    n = model.n_links
    p_world, R_world = _fk_frames(model, q)

    # End-effector world position
    p_ee = p_world[link_idx] + R_world[link_idx] @ local_pos

    J = np.zeros((6, n))

    # Walk up the kinematic chain from link_idx to root
    # Each joint i (with i <= link_idx and on the path) contributes a column.
    # For a serial chain, all joints 0..link_idx are on the path.
    for i in range(link_idx + 1):
        axis_i = model.S[i][:3]  # joint axis in LINK frame (usually [0,0,1])
        # Joint axis in WORLD frame
        z_i = R_world[i] @ axis_i

        if model.S[i, :3].any():
            # Revolute joint
            p_i = p_world[i]  # joint origin in world
            J[:3, i] = z_i  # angular part
            J[3:, i] = np.cross(z_i, p_ee - p_i)  # linear part
        else:
            # Prismatic joint
            J[3:, i] = R_world[i] @ model.S[i, 3:]  # only linear

    return J
