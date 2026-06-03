"""Articulated Body Algorithm (ABA) — O(n) forward dynamics.

Reference: Featherstone, Rigid Body Dynamics Algorithms (2008), Algorithm 7.2.

Three passes:
  Pass 1 (forward) : compute spatial velocities and bias forces.
  Pass 2 (backward): compute articulated-body inertia (IA) and bias (pA).
  Pass 3 (forward) : compute joint accelerations and link accelerations.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from forge3d.dynamics.model import RigidBodyModel
from forge3d.math.spatial import Xrot, crf, crm


def _joint_xform(S_i: Any, q_i: float) -> Any:
    axis = S_i[:3]
    n = float(np.linalg.norm(axis))
    if n < 1e-10:
        return np.eye(6)
    return Xrot(axis / n, q_i)


def _gravity_spatial(gravity: Any) -> Any:
    g = np.asarray(gravity, dtype=float)
    return np.array([0.0, 0.0, 0.0, -g[0], -g[1], -g[2]])


def forward_dynamics_aba(
    model: RigidBodyModel,
    q: Any,
    qd: Any,
    tau: Any,
    gravity: Any | None = None,
) -> Any:
    """Articulated Body Algorithm: compute qdd in O(n).

    Returns
    -------
    qdd : (n,) joint accelerations.
    """
    q = np.asarray(q, dtype=float)
    qd = np.asarray(qd, dtype=float)
    tau = np.asarray(tau, dtype=float)
    n = model.n_links
    grav = np.asarray(gravity if gravity is not None else model.gravity, dtype=float)
    a_base = _gravity_spatial(grav)

    # Per-link arrays
    Xup = np.empty((n, 6, 6))
    v = np.empty((n, 6))
    c = np.empty((n, 6))  # velocity-product acceleration (Coriolis bias)
    IA = [None] * n  # articulated-body inertia (6x6)
    pA = np.empty((n, 6))  # articulated-body bias force

    # ── Pass 1: forward — velocities & bias ─────────────────────────────────
    for i in range(n):
        X_J = _joint_xform(model.S[i], q[i])
        Xup[i] = X_J @ model.X_tree[i]

        if model.parent[i] == -1:
            v[i] = model.S[i] * qd[i]
        else:
            v[i] = Xup[i] @ v[model.parent[i]] + model.S[i] * qd[i]

        c[i] = crm(v[i]) @ model.S[i] * qd[i]  # = v ×m (S*qd)
        IA[i] = model.I_link[i].copy()
        pA[i] = crf(v[i]) @ model.I_link[i] @ v[i]

    # ── Pass 2: backward — articulated-body inertia & bias ──────────────────
    # U[i] = IA[i] @ S[i],  d[i] = S[i]^T @ U[i]  (scalar for 1-DOF joints)
    U = np.empty((n, 6))
    d = np.empty(n)
    u = np.empty(n)

    for i in range(n - 1, -1, -1):
        U[i] = IA[i] @ model.S[i]
        d[i] = float(model.S[i] @ U[i])
        u[i] = float(tau[i]) - float(model.S[i] @ pA[i])

        p = model.parent[i]
        if p != -1:
            # Articulated inertia felt at parent: IA - U*U^T/d
            Ia = IA[i] - np.outer(U[i], U[i]) / d[i]
            # Articulated bias felt at parent: pA + Ia*c + U*(u/d)
            pa = pA[i] + Ia @ c[i] + U[i] * (u[i] / d[i])
            IA[p] = IA[p] + Xup[i].T @ Ia @ Xup[i]
            pA[p] = pA[p] + Xup[i].T @ pa

    # ── Pass 3: forward — accelerations ──────────────────────────────────────
    qdd = np.empty(n)
    a = np.empty((n, 6))

    for i in range(n):
        if model.parent[i] == -1:
            a[i] = Xup[i] @ a_base + c[i]
        else:
            a[i] = Xup[i] @ a[model.parent[i]] + c[i]

        qdd[i] = (u[i] - float(U[i] @ a[i])) / d[i]
        a[i] = a[i] + model.S[i] * qdd[i]

    return qdd
