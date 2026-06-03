"""Inertia tensor computations for primitive rigid-body shapes.

All tensors are diagonal in the body's principal frame.
Convention: body z-axis is the symmetry axis for capsule/cylinder.
"""

from __future__ import annotations

import numpy as np


def box_inertia(mass: float, half_extents: np.ndarray) -> np.ndarray:
    """Solid box: 3×3 diagonal inertia tensor about center of mass.

    half_extents = [a, b, c]  (x, y, z semi-lengths)
    Ix = m/12*(4b²+4c²),  Iy = m/12*(4a²+4c²),  Iz = m/12*(4a²+4b²)
    """
    a, b, c = float(half_extents[0]), float(half_extents[1]), float(half_extents[2])
    Ix = mass / 12.0 * (4 * b**2 + 4 * c**2)
    Iy = mass / 12.0 * (4 * a**2 + 4 * c**2)
    Iz = mass / 12.0 * (4 * a**2 + 4 * b**2)
    return np.diag([Ix, Iy, Iz])


def sphere_inertia(mass: float, radius: float) -> np.ndarray:
    """Solid sphere: 3×3 diagonal inertia tensor (isotropic)."""
    val = 2.0 / 5.0 * float(mass) * float(radius) ** 2
    return np.eye(3) * val


def capsule_inertia(mass: float, radius: float, half_length: float) -> np.ndarray:
    """Capsule (cylinder + two hemispheres), symmetry axis = z.

    Approximates each hemisphere as a half-sphere of mass m_cap/2.
    """
    r = float(radius)
    half_len = float(half_length)
    L = 2.0 * half_len  # full cylinder length

    # Split mass between cylinder and two hemispheres by volume
    vol_cyl = np.pi * r**2 * L
    vol_cap = (4.0 / 3.0) * np.pi * r**3
    vol_total = vol_cyl + vol_cap
    m_cyl = mass * vol_cyl / vol_total
    m_cap = mass * vol_cap / vol_total

    # Cylinder contribution (axis = z)
    Ix_cyl = m_cyl * (3 * r**2 + L**2) / 12.0
    Iz_cyl = m_cyl * r**2 / 2.0

    # Hemisphere contribution (each, then ×2).
    # Hemisphere CoM is at 3r/8 from flat face.
    # I about hemisphere CoM ≈ 2/5 * (m/2) * r²
    # Parallel axis to capsule CoM: d = half_len + 3r/8
    I_hemi_cm = 2.0 / 5.0 * (m_cap / 2.0) * r**2
    d = half_len + 3.0 * r / 8.0
    Ix_cap = 2.0 * (I_hemi_cm + (m_cap / 2.0) * d**2)
    Iz_cap = 2.0 * (2.0 / 5.0 * (m_cap / 2.0) * r**2)

    return np.diag([Ix_cyl + Ix_cap, Ix_cyl + Ix_cap, Iz_cyl + Iz_cap])
