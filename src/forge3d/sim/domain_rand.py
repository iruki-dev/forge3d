"""Domain randomization utilities for forge3d.

Randomizes physical properties of bodies (mass, friction, restitution) and
environment parameters (gravity, target positions) to improve RL robustness.

Example::

    config = DomainRandConfig(mass_range=(0.3, 1.5), friction_range=(0.3, 0.9))
    rng = np.random.default_rng(42)
    randomize_body(world, body_id=obj_id, config=config, rng=rng)
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace as _replace
from typing import Any

import numpy as np

# ── Configuration ─────────────────────────────────────────────────────────────


@dataclass
class DomainRandConfig:
    """Ranges for domain randomization.

    All ``*_range`` fields are (low, high) uniform intervals.
    Set both bounds equal to disable randomization of that property.
    """

    mass_range: tuple[float, float] = (0.5, 2.0)
    friction_range: tuple[float, float] = (0.3, 0.9)
    restitution_range: tuple[float, float] = (0.0, 0.5)
    gravity_z_range: tuple[float, float] = (-10.0, -9.0)
    # Target position noise (added to a base position): (low, high) per axis
    target_noise_range: tuple[float, float] = (-0.1, 0.1)
    # Shape scale factor (applied uniformly to half-extents / radius)
    scale_range: tuple[float, float] = (0.9, 1.1)


# ── Body randomization ────────────────────────────────────────────────────────


def randomize_body(
    physics_world: Any,
    body_id: int,
    config: DomainRandConfig,
    rng: np.random.Generator | None = None,
) -> None:
    """Randomize physical properties of one body in-place.

    Parameters
    ----------
    physics_world : ``PhysicsWorld`` instance.
    body_id       : integer body id (returned by ``add_box`` / ``add_sphere``).
    config        : randomization ranges.
    rng           : NumPy random Generator.  Created from system entropy if
                    None.
    """
    if rng is None:
        rng = np.random.default_rng()

    pw = physics_world  # type: ignore[assignment]
    for i, b in enumerate(pw._bodies):
        if b.body_id != body_id or b.static:
            continue
        new_mass = float(rng.uniform(*config.mass_range))
        new_friction = float(rng.uniform(*config.friction_range))
        new_restitution = float(rng.uniform(*config.restitution_range))
        pw._bodies[i] = _replace(
            b,
            mass=new_mass,
            friction=new_friction,
            restitution=new_restitution,
        )
        return


def randomize_gravity(
    physics_world: Any,
    config: DomainRandConfig,
    rng: np.random.Generator | None = None,
) -> None:
    """Randomize the world gravity z-component."""
    if rng is None:
        rng = np.random.default_rng()
    pw = physics_world  # type: ignore[assignment]
    gz = float(rng.uniform(*config.gravity_z_range))
    pw._gravity = np.array([pw._gravity[0], pw._gravity[1], gz])


def randomize_target(
    base_position: np.ndarray,
    config: DomainRandConfig,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Return a randomized target position near ``base_position``.

    Parameters
    ----------
    base_position : (3,) nominal target position.
    config        : randomization config (``target_noise_range`` used).
    rng           : NumPy random Generator.

    Returns
    -------
    perturbed (3,) target position.
    """
    if rng is None:
        rng = np.random.default_rng()
    noise = rng.uniform(*config.target_noise_range, size=3)
    return np.asarray(base_position, dtype=float) + noise
