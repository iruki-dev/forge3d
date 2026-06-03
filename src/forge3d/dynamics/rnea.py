"""Recursive Newton-Euler Algorithm (RNEA) — inverse dynamics.

Given a RigidBodyModel and joint state (q, qd, qdd), computes joint torques tau
such that the equations of motion M(q)*qdd + h(q,qd) = tau are satisfied.

Also provides:
  - compute_mass_matrix   : O(n^2) CRBA via repeated RNEA calls
  - forward_dynamics      : compute qdd from tau (uses CRBA + RNEA for bias)
  - semi_implicit_euler   : one integration step

Reference: Featherstone, Rigid Body Dynamics Algorithms (2008), Algorithm 5.1.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from forge3d.dynamics.model import RigidBodyModel
from forge3d.math.spatial import Xrot, crf, crm

# ── helpers ───────────────────────────────────────────────────────────────────


def _joint_transform(S_i: Any, q_i: float) -> Any:
    """Spatial transform due to joint motion.

    For revolute joint (S = [axis; 0]) rotating by q_i about joint axis.
    For zero motion returns identity.
    """
    axis = S_i[:3]
    n = np.linalg.norm(axis)
    if n < 1e-10:
        # Prismatic joint (not used in Phase 1 but handled gracefully)
        return np.eye(6)
    return Xrot(axis / n, q_i)


def _gravity_spatial(gravity: Any) -> Any:
    """Convert gravity 3-vector to spatial base acceleration (Featherstone trick).

    Setting a_base = [0; -gravity] accounts for gravitational forces without
    adding explicit external forces.  The sign flip makes gravity appear as an
    inertial upward acceleration propagating through the tree.
    """
    g = np.asarray(gravity, dtype=float)
    return np.array([0.0, 0.0, 0.0, -g[0], -g[1], -g[2]])


# ── RNEA ─────────────────────────────────────────────────────────────────────


def inverse_dynamics(
    model: RigidBodyModel,
    q: Any,
    qd: Any,
    qdd: Any,
    gravity: Any | None = None,
) -> Any:
    """Recursive Newton-Euler: tau = ID(model, q, qd, qdd).

    Parameters
    ----------
    model   : RigidBodyModel
    q, qd, qdd : (n,) joint angles, velocities, accelerations
    gravity : (3,) gravity vector (overrides model.gravity if given)

    Returns
    -------
    tau : (n,) joint torques
    """
    q = np.asarray(q, dtype=float)
    qd = np.asarray(qd, dtype=float)
    qdd = np.asarray(qdd, dtype=float)
    n = model.n_links
    grav = np.asarray(gravity if gravity is not None else model.gravity, dtype=float)

    # Storage
    v = np.zeros((n, 6))  # spatial velocities
    a = np.zeros((n, 6))  # spatial accelerations
    f = np.zeros((n, 6))  # spatial forces
    Xup = np.zeros((n, 6, 6))  # cumulative joint+tree transforms

    # Base spatial acceleration (gravity trick)
    a_base = _gravity_spatial(grav)

    # ── Forward pass ──────────────────────────────────────────────────────────
    for i in range(n):
        X_J = _joint_transform(model.S[i], q[i])
        Xup[i] = X_J @ model.X_tree[i]

        if model.parent[i] == -1:
            v[i] = model.S[i] * qd[i]
            a[i] = Xup[i] @ a_base + model.S[i] * qdd[i] + crm(v[i]) @ model.S[i] * qd[i]
        else:
            p = model.parent[i]
            v[i] = Xup[i] @ v[p] + model.S[i] * qd[i]
            a[i] = Xup[i] @ a[p] + model.S[i] * qdd[i] + crm(v[i]) @ model.S[i] * qd[i]

        f[i] = model.I_link[i] @ a[i] + crf(v[i]) @ model.I_link[i] @ v[i]

    # ── Backward pass ─────────────────────────────────────────────────────────
    tau = np.zeros(n)
    for i in range(n - 1, -1, -1):
        tau[i] = float(model.S[i] @ f[i])
        p = model.parent[i]
        if p != -1:
            f[p] = f[p] + Xup[i].T @ f[i]

    return tau


# ── Mass matrix (CRBA via column-by-column RNEA) ──────────────────────────────


def compute_mass_matrix(model: RigidBodyModel, q: Any) -> Any:
    """n×n joint-space mass matrix M(q) via O(n^2) RNEA calls."""
    q = np.asarray(q, dtype=float)
    n = model.n_links
    M = np.zeros((n, n))
    zero_qd = np.zeros(n)
    zero_grav = np.zeros(3)
    for j in range(n):
        qdd_j = np.zeros(n)
        qdd_j[j] = 1.0
        col = inverse_dynamics(model, q, zero_qd, qdd_j, gravity=zero_grav)
        M[:, j] = col
    return M


# ── Forward dynamics ──────────────────────────────────────────────────────────


def forward_dynamics(
    model: RigidBodyModel,
    q: Any,
    qd: Any,
    tau: Any,
    gravity: Any | None = None,
) -> Any:
    """Compute joint accelerations qdd given torques tau.

    qdd = M(q)^{-1} * (tau - h(q, qd))
    where h = RNEA(q, qd, 0, gravity)  (bias: Coriolis + gravity)
    """
    q = np.asarray(q, dtype=float)
    qd = np.asarray(qd, dtype=float)
    tau = np.asarray(tau, dtype=float)
    grav = gravity if gravity is not None else model.gravity

    M = compute_mass_matrix(model, q)
    h = inverse_dynamics(model, q, qd, np.zeros_like(q), gravity=grav)
    return np.linalg.solve(M, tau - h)


# ── Integrator ────────────────────────────────────────────────────────────────


def semi_implicit_euler(
    model: RigidBodyModel,
    q: Any,
    qd: Any,
    tau: Any,
    dt: float,
    gravity: Any | None = None,
) -> tuple[Any, Any]:
    """Semi-implicit (symplectic) Euler integration step.

    1. qdd = forward_dynamics(q, qd, tau)
    2. qd_new = qd + dt * qdd   (velocity updated first)
    3. q_new  = q  + dt * qd_new

    Returns (q_new, qd_new) — no in-place mutation.
    """
    q = np.asarray(q, dtype=float)
    qd = np.asarray(qd, dtype=float)
    qdd = forward_dynamics(model, q, qd, tau, gravity=gravity)
    qd_new = qd + dt * qdd
    q_new = q + dt * qd_new
    return q_new, qd_new


# ── Energy utilities ──────────────────────────────────────────────────────────


def kinetic_energy(model: RigidBodyModel, q: Any, qd: Any) -> float:
    """T = 0.5 * qd^T * M(q) * qd."""
    q = np.asarray(q, dtype=float)
    qd = np.asarray(qd, dtype=float)
    M = compute_mass_matrix(model, q)
    return float(0.5 * qd @ M @ qd)


def potential_energy(model: RigidBodyModel, q: Any) -> float:
    """V = -sum_i m_i * g · r_i  (height above reference).

    Uses gravity direction from model.gravity.
    """
    from forge3d.math.se3 import aa_to_rot, unskew

    q = np.asarray(q, dtype=float)
    n = model.n_links
    grav = model.gravity

    # Forward kinematics via SE(3).
    # Convention: T_world[i] maps points FROM link i's joint frame TO world frame.
    #   T_world[i] = T_world[parent] @ T_parent_to_link[i]
    #   T_parent_to_link[i] = make_se3(R_tree @ R_joint, p_tree)
    # where (Featherstone passive convention):
    #   E = X_tree[:3,:3]   (E = R_tree.T)
    #   R_tree = E.T         (active rotation of tree frame in parent)
    #   p_tree = unskew(-(R_tree @ X_tree[3:,:3]))
    #   R_joint = aa_to_rot(S[:3]/|S[:3]|, q_i)

    R_world = [np.eye(3)] * n  # accumulated world-frame rotation of link i
    p_world = [np.zeros(3)] * n  # world-frame position of link i joint origin

    for i in range(n):
        X_t = model.X_tree[i]
        E = X_t[:3, :3]  # E = R_tree.T  (Featherstone passive)
        R_tree = E.T  # active rotation
        p_tree = unskew(-(R_tree @ X_t[3:, :3]))  # joint position in parent frame

        axis = model.S[i][:3]
        n_ax = float(np.linalg.norm(axis))
        R_joint = aa_to_rot(axis / n_ax, q[i]) if n_ax > 1e-10 else np.eye(3)

        if model.parent[i] == -1:
            R_parent = np.eye(3)
            p_parent = np.zeros(3)
        else:
            R_parent = R_world[model.parent[i]]
            p_parent = p_world[model.parent[i]]

        # World position of this link's joint origin
        p_world[i] = p_parent + R_parent @ p_tree
        # World orientation: parent @ tree-rotation @ joint-rotation
        R_world[i] = R_parent @ R_tree @ R_joint

    # Accumulate PE contribution from each link's CoM
    V = 0.0
    for i in range(n):
        I_i = model.I_link[i]
        mass = float(I_i[3, 3])
        if mass < 1e-12:
            continue
        # CoM in link frame from spatial inertia: I[:3, 3:] = mass * skew(com)
        skew_com = I_i[:3, 3:] / mass
        com_local = np.array([-skew_com[1, 2], skew_com[0, 2], -skew_com[0, 1]])

        com_world = p_world[i] + R_world[i] @ com_local
        V += -mass * float(np.dot(grav, com_world))

    return V


def total_energy(model: RigidBodyModel, q: Any, qd: Any) -> float:
    """Total mechanical energy E = T + V."""
    return kinetic_energy(model, q, qd) + potential_energy(model, q)
