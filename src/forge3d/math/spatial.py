"""Featherstone spatial vector algebra — 6D motion/force vectors.

Convention (Featherstone RBDA):
  Spatial velocity  V = [omega; v_O]   (angular, then linear velocity of origin)
  Spatial force     F = [tau;   f  ]   (moment, then linear force)
  Spatial inertia   I  6x6 symmetric matrix

Spatial transform  X_{A→B}:  V_B = X * V_A
  X = [R          0]
      [-R*skew(p)  R]
  where R = rotation from A to B, p = position of B's origin in A frame.

Force transform from B to A (dual): F_A += X^T * F_B
"""

from __future__ import annotations

from typing import Any

import numpy as np

from forge3d.math.se3 import aa_to_rot, skew

# ── spatial transforms (6x6) ─────────────────────────────────────────────────


def Xrot(axis: Any, angle: float) -> Any:
    """Spatial transform for a pure rotation by `angle` about `axis`.

    Featherstone passive-rotation convention: E = R^T.
    X maps motion vectors FROM the un-rotated frame TO the rotated frame.
    """
    R = aa_to_rot(axis, angle)
    E = R.T  # passive: express un-rotated vectors in the rotated frame
    X = np.zeros((6, 6))
    X[:3, :3] = E
    X[3:, 3:] = E
    return X


def Xtrans(p: Any) -> Any:
    """Spatial transform for a pure translation by vector p.

    X_{A→B}: B's origin is at p in A's frame, no rotation.
    """
    p = np.asarray(p, dtype=float)
    X = np.eye(6)
    X[3:, :3] = -skew(p)
    return X


def Xpose(R: Any, p: Any) -> Any:
    """Spatial transform from frame A to frame B.

    R: 3x3 active rotation (R maps A-basis vectors to B-basis vectors,
       i.e. R is the matrix whose columns are B's axes in A).
    p: position of B's origin expressed in frame A.

    Featherstone convention: E = R^T (passive transformation).
    """
    R = np.asarray(R, dtype=float)
    p = np.asarray(p, dtype=float)
    E = R.T
    X = np.zeros((6, 6))
    X[:3, :3] = E
    X[3:, :3] = -E @ skew(p)
    X[3:, 3:] = E
    return X


# ── spatial cross products ────────────────────────────────────────────────────


def crm(V: Any) -> Any:
    """6x6 cross-product matrix for motion vectors.

    crm(V) * W = V ×m W  (spatial cross product of motion vectors)
    V = [omega; v_O]
    """
    V = np.asarray(V, dtype=float)
    om = V[:3]
    v = V[3:]
    Om = skew(om)
    Ve = skew(v)
    M = np.zeros((6, 6))
    M[:3, :3] = Om
    M[3:, :3] = Ve
    M[3:, 3:] = Om
    return M


def crf(V: Any) -> Any:
    """6x6 cross-product matrix for force vectors.

    crf(V) = -crm(V)^T
    crf(V) * F = V ×f F  (spatial cross product of force vectors)
    """
    return -crm(V).T


# ── spatial inertia ───────────────────────────────────────────────────────────


def spatial_inertia(mass: float, com: Any, Icm: Any) -> Any:
    """6x6 spatial inertia matrix of a rigid body (in body frame).

    mass : scalar mass
    com  : 3-vector, center of mass position from body frame origin
    Icm  : 3x3 rotational inertia about CoM expressed in body frame

    Formula (Featherstone RBDA eq 2.62):
      I = [Icm - m*C^2   m*C ]
          [m*C^T         m*E3]
    where C = skew(com),  C^2 = C @ C  (note: -C^2 = |c|^2*I3 - c*c^T)
    """
    mass = float(mass)
    com = np.asarray(com, dtype=float)
    Icm = np.asarray(Icm, dtype=float)
    C = skew(com)
    Imat = np.zeros((6, 6))
    # upper-left: Icm - m * C @ C  (= Icm + m*(|c|^2*I - c*c^T) by parallel axis)
    Imat[:3, :3] = Icm - mass * (C @ C)
    # upper-right: m * C
    Imat[:3, 3:] = mass * C
    # lower-left: m * C^T = -m * C
    Imat[3:, :3] = mass * C.T
    # lower-right: m * I3
    Imat[3:, 3:] = mass * np.eye(3)
    return Imat


# ── kinetic energy ────────────────────────────────────────────────────────────


def kinetic_energy_spatial(Imat: Any, V: Any) -> float:
    """Kinetic energy from spatial inertia and velocity: T = 0.5 * V^T * I * V."""
    V = np.asarray(V, dtype=float)
    Imat = np.asarray(Imat, dtype=float)
    return float(0.5 * V @ Imat @ V)
