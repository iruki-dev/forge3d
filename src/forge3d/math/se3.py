"""SE(3) Lie group operations — functional, no in-place mutation.

Convention:
  T = [R  p]  (4x4 homogeneous)
      [0  1]

Spatial twist xi = [omega; v]  (6-vector, angular first then linear)
"""

from __future__ import annotations

from typing import Any

import numpy as np

# ── helpers ──────────────────────────────────────────────────────────────────


def skew(v: Any) -> Any:
    """3-vector → 3x3 skew-symmetric cross-product matrix."""
    v = np.asarray(v, dtype=float)
    return np.array(
        [
            [0.0, -v[2], v[1]],
            [v[2], 0.0, -v[0]],
            [-v[1], v[0], 0.0],
        ]
    )


def unskew(M: Any) -> Any:
    """3x3 skew-symmetric matrix → 3-vector."""
    M = np.asarray(M, dtype=float)
    return np.array([M[2, 1], M[0, 2], M[1, 0]])


# ── rotation matrices ─────────────────────────────────────────────────────────


def rot_x(angle: float) -> Any:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def rot_y(angle: float) -> Any:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def rot_z(angle: float) -> Any:
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def aa_to_rot(axis: Any, angle: float) -> Any:
    """Axis-angle → 3x3 rotation matrix (Rodrigues formula)."""
    axis = np.asarray(axis, dtype=float)
    axis = axis / (np.linalg.norm(axis) + 1e-300)
    K = skew(axis)
    return np.eye(3) + np.sin(angle) * K + (1.0 - np.cos(angle)) * (K @ K)


# ── SE(3) operations ──────────────────────────────────────────────────────────


def make_se3(R: Any, p: Any) -> Any:
    """Build 4x4 SE(3) matrix from 3x3 rotation and 3-vector translation."""
    T = np.eye(4)
    T[:3, :3] = np.asarray(R, dtype=float)
    T[:3, 3] = np.asarray(p, dtype=float)
    return T


def rot_of(T: Any) -> Any:
    """Extract 3x3 rotation from 4x4 SE(3) matrix."""
    return np.asarray(T)[:3, :3]


def trans_of(T: Any) -> Any:
    """Extract 3-vector translation from 4x4 SE(3) matrix."""
    return np.asarray(T)[:3, 3]


def inv_se3(T: Any) -> Any:
    """Inverse of SE(3) transform without full 4x4 matrix inversion."""
    T = np.asarray(T, dtype=float)
    R = T[:3, :3]
    p = T[:3, 3]
    T_inv = np.eye(4)
    T_inv[:3, :3] = R.T
    T_inv[:3, 3] = -(R.T @ p)
    return T_inv


def exp_se3(xi: Any) -> Any:
    """se(3) → SE(3): exponential map.

    xi = [omega; v]  (6-vector, Lie algebra element)
    Returns 4x4 homogeneous transform.
    """
    xi = np.asarray(xi, dtype=float)
    omega = xi[:3]
    v = xi[3:]
    theta = np.linalg.norm(omega)
    if theta < 1e-10:
        # Small-angle approximation
        R = np.eye(3) + skew(omega)
        p = v
    else:
        K = skew(omega / theta)
        R = np.eye(3) + np.sin(theta) * K + (1.0 - np.cos(theta)) * (K @ K)
        V = (
            np.eye(3)
            + ((1.0 - np.cos(theta)) / theta) * K
            + ((theta - np.sin(theta)) / theta) * (K @ K)
        )
        p = V @ v
    return make_se3(R, p)


def log_se3(T: Any) -> Any:
    """SE(3) → se(3): logarithmic map.

    Returns 6-vector xi = [omega; v].
    """
    T = np.asarray(T, dtype=float)
    R = T[:3, :3]
    p = T[:3, 3]
    # Rotation part
    cos_theta = np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0)
    theta = np.arccos(cos_theta)
    if theta < 1e-10:
        omega = unskew(R - R.T) / 2.0
        v = p
    else:
        log_R = (theta / (2.0 * np.sin(theta))) * (R - R.T)
        omega = unskew(log_R)
        V_inv = (
            np.eye(3)
            - 0.5 * log_R
            + ((1.0 / theta**2) - (1.0 + np.cos(theta)) / (2.0 * theta * np.sin(theta)))
            * (log_R @ log_R)
        )
        v = V_inv @ p
    return np.concatenate([omega, v])


def adjoint_se3(T: Any) -> Any:
    """6x6 adjoint matrix of SE(3) element T.

    Maps se(3) vectors: Ad_T * xi maps xi from one frame to another.
    Ad_T = [R    0 ]
           [p×R  R ]
    """
    T = np.asarray(T, dtype=float)
    R = T[:3, :3]
    p = T[:3, 3]
    Ad = np.zeros((6, 6))
    Ad[:3, :3] = R
    Ad[3:, 3:] = R
    Ad[3:, :3] = skew(p) @ R
    return Ad
