"""Composite Rigid Body Algorithm (CRBA) — O(n²) mass matrix.

Reference: Featherstone, Rigid Body Dynamics Algorithms (2008), Algorithm 6.2.

Compared to the column-by-column RNEA approach (n RNEA calls),
CRBA makes a single backward sweep and is ~6x faster per joint.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from forge3d.dynamics.model import RigidBodyModel
from forge3d.math.spatial import Xrot


def _joint_xform(S_i: Any, q_i: float) -> Any:
    """Spatial transform for joint i at angle q_i (same helper as in rnea.py)."""
    axis = S_i[:3]
    n = float(np.linalg.norm(axis))
    if n < 1e-10:
        return np.eye(6)
    return Xrot(axis / n, q_i)


def mass_matrix(model: RigidBodyModel, q: Any) -> Any:
    """Composite Rigid Body Algorithm: n×n joint-space mass matrix M(q).

    Algorithm 6.2 from Featherstone (RBDA):
      1. Compute Xup[i] for all links.
      2. Init composite inertia Ic[i] = I_link[i].
      3. Backward sweep: Ic[parent] += Xup[i]^T @ Ic[i] @ Xup[i].
      4. For each (i,j) pair on the kinematic path, fill M[i,j].

    Returns
    -------
    M : (n, n) symmetric positive-definite mass matrix.
    """
    q = np.asarray(q, dtype=float)
    n = model.n_links

    # ── Step 1: forward kinematics — compute Xup ─────────────────────────────
    Xup = np.empty((n, 6, 6))
    for i in range(n):
        X_J = _joint_xform(model.S[i], q[i])
        Xup[i] = X_J @ model.X_tree[i]

    # ── Step 2: init composite inertias ───────────────────────────────────────
    Ic = [model.I_link[i].copy() for i in range(n)]

    # ── Step 3: backward accumulation ─────────────────────────────────────────
    for i in range(n - 1, -1, -1):
        p = model.parent[i]
        if p != -1:
            # Ic expressed in parent frame: Xup^T * Ic * Xup
            Ic[p] = Ic[p] + Xup[i].T @ Ic[i] @ Xup[i]

    # ── Step 4: fill mass matrix ───────────────────────────────────────────────
    M = np.zeros((n, n))
    for i in range(n):
        fh = Ic[i] @ model.S[i]  # 6-vector "generalised force"
        M[i, i] = float(model.S[i] @ fh)  # diagonal

        j = i
        while model.parent[j] != -1:
            fh = Xup[j].T @ fh  # propagate up the tree
            j = model.parent[j]
            M[i, j] = float(model.S[j] @ fh)
            M[j, i] = M[i, j]  # symmetry

    return M
