"""Quaternion operations — functional, no in-place mutation.

Convention: q = [w, x, y, z]  (scalar first)
"""

from __future__ import annotations

from typing import Any

import numpy as np


def quat_normalize(q: Any) -> Any:
    """Normalize quaternion to unit length."""
    q = np.asarray(q, dtype=float)
    n = np.linalg.norm(q)
    return q / (n + 1e-300)


def quat_conjugate(q: Any) -> Any:
    """Quaternion conjugate: [w, x, y, z] → [w, -x, -y, -z]."""
    q = np.asarray(q, dtype=float)
    return np.array([q[0], -q[1], -q[2], -q[3]])


def quat_inv(q: Any) -> Any:
    """Quaternion inverse (assumes unit quaternion = conjugate)."""
    return quat_conjugate(quat_normalize(q))


def quat_multiply(q1: Any, q2: Any) -> Any:
    """Hamilton product q1 * q2."""
    q1 = np.asarray(q1, dtype=float)
    q2 = np.asarray(q2, dtype=float)
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ]
    )


def quat_rotate(q: Any, v: Any) -> Any:
    """Rotate 3-vector v by unit quaternion q.  v' = q * [0,v] * q^{-1}."""
    q = quat_normalize(np.asarray(q, dtype=float))
    v = np.asarray(v, dtype=float)
    qv = np.array([0.0, v[0], v[1], v[2]])
    return quat_multiply(quat_multiply(q, qv), quat_conjugate(q))[1:]


def quat_from_aa(axis: Any, angle: float) -> Any:
    """Axis-angle → unit quaternion."""
    axis = np.asarray(axis, dtype=float)
    axis = axis / (np.linalg.norm(axis) + 1e-300)
    s = np.sin(angle / 2.0)
    return np.array([np.cos(angle / 2.0), axis[0] * s, axis[1] * s, axis[2] * s])


def quat_to_rot(q: Any) -> Any:
    """Unit quaternion → 3x3 rotation matrix."""
    q = quat_normalize(np.asarray(q, dtype=float))
    w, x, y, z = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ]
    )


def quat_from_rot(R: Any) -> Any:
    """3x3 rotation matrix → unit quaternion (Shepperd method)."""
    R = np.asarray(R, dtype=float)
    trace = R[0, 0] + R[1, 1] + R[2, 2]
    if trace > 0:
        s = 0.5 / np.sqrt(trace + 1.0)
        return np.array(
            [
                0.25 / s,
                (R[2, 1] - R[1, 2]) * s,
                (R[0, 2] - R[2, 0]) * s,
                (R[1, 0] - R[0, 1]) * s,
            ]
        )
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        return np.array(
            [
                (R[2, 1] - R[1, 2]) / s,
                0.25 * s,
                (R[0, 1] + R[1, 0]) / s,
                (R[0, 2] + R[2, 0]) / s,
            ]
        )
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        return np.array(
            [
                (R[0, 2] - R[2, 0]) / s,
                (R[0, 1] + R[1, 0]) / s,
                0.25 * s,
                (R[1, 2] + R[2, 1]) / s,
            ]
        )
    else:
        s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
        return np.array(
            [
                (R[1, 0] - R[0, 1]) / s,
                (R[0, 2] + R[2, 0]) / s,
                (R[1, 2] + R[2, 1]) / s,
                0.25 * s,
            ]
        )


def quat_slerp(q1: Any, q2: Any, t: float) -> Any:
    """Spherical linear interpolation between unit quaternions."""
    q1 = quat_normalize(np.asarray(q1, dtype=float))
    q2 = quat_normalize(np.asarray(q2, dtype=float))
    dot = np.dot(q1, q2)
    # Ensure shortest path
    if dot < 0.0:
        q2 = -q2
        dot = -dot
    dot = np.clip(dot, -1.0, 1.0)
    if dot > 0.9995:
        # Linear interpolation for very close quaternions
        return quat_normalize(q1 + t * (q2 - q1))
    theta_0 = np.arccos(dot)
    theta = theta_0 * t
    sin_theta = np.sin(theta)
    sin_theta_0 = np.sin(theta_0)
    s1 = np.cos(theta) - dot * sin_theta / sin_theta_0
    s2 = sin_theta / sin_theta_0
    return quat_normalize(s1 * q1 + s2 * q2)
