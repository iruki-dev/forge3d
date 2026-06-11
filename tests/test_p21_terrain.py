"""P21: Heightfield terrain collision tests."""

from __future__ import annotations

from typing import Any

import numpy as np

import forge3d as f3d


def _flat_terrain(world: f3d.World, height: float = 0.0) -> Any:
    """Add a 10×10 flat terrain at the given height."""
    heights = np.full((10, 10), height, dtype=np.float32)
    return world.add_terrain(heights, cell_size=1.0, origin=(-5.0, -5.0, 0.0))


# ── G1: Sphere rests on flat terrain ─────────────────────────────────────────


def test_sphere_rests_on_flat_terrain():
    """A sphere dropped on flat terrain should come to rest near the surface."""
    world = f3d.World(gravity=(0, 0, -9.81))
    terrain_z = 0.0
    _flat_terrain(world, height=terrain_z)

    radius = 0.5
    ball = world.add_sphere(
        radius=radius, position=(0, 0, 3), mass=1.0, friction=0.5, restitution=0.0
    )

    for _ in range(300):
        world.step(dt=1 / 60)

    # Ball center should be at z ≈ terrain_z + radius
    expected_z = terrain_z + radius
    assert abs(ball.position[2] - expected_z) < 0.2, (
        f"Ball didn't rest on terrain: z={ball.position[2]:.3f}, expected≈{expected_z:.3f}"
    )


# ── G2: Sphere slides on slope ────────────────────────────────────────────────


def test_sphere_slides_on_slope():
    """A sphere on a sloped terrain should slide horizontally."""
    world = f3d.World(gravity=(0, 0, -9.81))

    # Create a slope: heights increase along x
    rows, cols = 10, 20
    slope_heights = np.zeros((rows, cols), dtype=np.float32)
    for c in range(cols):
        slope_heights[:, c] = c * 0.2  # 0 to 3.8 m rise over 19 cells

    world.add_terrain(slope_heights, cell_size=1.0, origin=(-5.0, -5.0, 0.0))

    # Place sphere near the top of the slope
    ball = world.add_sphere(
        radius=0.4, position=(9.0, 0.0, 5.0), mass=1.0, friction=0.1, restitution=0.0
    )

    x0 = ball.position[0]
    for _ in range(120):
        world.step(dt=1 / 60)

    # Ball should have slid in the -x direction (downhill)
    assert ball.position[0] < x0 - 0.5, (
        f"Ball didn't slide: x went from {x0:.2f} to {ball.position[0]:.2f}"
    )


# ── G3: Box rests on terrain ──────────────────────────────────────────────────


def test_box_rests_on_terrain():
    """A box dropped on flat terrain should settle near the surface."""
    world = f3d.World(gravity=(0, 0, -9.81))
    _flat_terrain(world, height=0.0)

    box = world.add_box(size=(1, 1, 1), position=(0, 0, 4), mass=2.0, friction=0.5, restitution=0.0)

    for _ in range(300):
        world.step(dt=1 / 60)

    # Box bottom should be near terrain surface (z=0)
    # Box center = z ≈ 0.5 (half height above terrain)
    assert abs(box.position[2] - 0.5) < 0.5, f"Box didn't settle: z={box.position[2]:.3f}"


# ── Terrain API ───────────────────────────────────────────────────────────────


def test_add_terrain_returns_heightfield():
    """add_terrain should return a Heightfield object."""
    from forge3d.collision.heightfield import Heightfield

    world = f3d.World()
    h = np.zeros((5, 5), dtype=np.float32)
    terrain = world.add_terrain(h, cell_size=1.0)
    assert isinstance(terrain, Heightfield)
    assert terrain.rows == 5
    assert terrain.cols == 5


def test_heightfield_height_at():
    """Heightfield.height_at() should return correct interpolated height."""
    from forge3d.collision.heightfield import Heightfield

    h = np.array([[0, 1], [2, 3]], dtype=np.float32)
    hf = Heightfield(heights=h, cell_size=1.0, origin=np.array([0.0, 0.0, 0.0]))

    # Corner values
    assert abs(hf.height_at(0.0, 0.0) - 0.0) < 1e-5
    assert abs(hf.height_at(1.0, 0.0) - 1.0) < 1e-5
    assert abs(hf.height_at(0.0, 1.0) - 2.0) < 1e-5
    assert abs(hf.height_at(1.0, 1.0) - 3.0) < 1e-5

    # Midpoint: bilinear average
    mid = hf.height_at(0.5, 0.5)
    assert abs(mid - 1.5) < 1e-4
