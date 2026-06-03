"""Forge Ball game scene builder.

Builds a physics arena and returns handles for the player and target objects.
This module uses only the public forge3d API (import forge3d as f3d).
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")

import forge3d as f3d


def build_scene() -> tuple[f3d.World, f3d.Body, list[f3d.Body]]:
    """Create the Forge Ball arena.

    Layout (top view, x-right y-forward z-up):
      - 35×35 ground
      - Low boundary walls on all four sides
      - Player sphere at origin
      - 5 box towers (3 boxes each) near corners + centre-back
      - 4 loose balls scattered for chaos
      - Static ramp wedge in the south

    Returns
    -------
    world   : forge3d.World
    player  : Body handle for the player sphere
    targets : list of Body handles for the 15 knockable boxes
    """
    world = f3d.World(gravity=(0.0, 0.0, -9.81))

    # ── Ground ────────────────────────────────────────────────────────────────
    world.add_ground(size=(36.0, 36.0, 0.4))

    # ── Boundary walls (keep player in arena) ─────────────────────────────────
    wall_h = 1.8
    half_arena = 17.5
    for px, py, sx, sy in [
        (0.0, +half_arena, 36.0, 0.5),  # north
        (0.0, -half_arena, 36.0, 0.5),  # south
        (+half_arena, 0.0, 0.5, 36.0),  # east
        (-half_arena, 0.0, 0.5, 36.0),  # west
    ]:
        world._physics.add_static_box(
            size=(sx, sy, wall_h),
            position=(px, py, wall_h / 2),
            material="default",
            name="wall",
            friction=0.3,
            restitution=0.5,
        )

    # ── Player sphere ─────────────────────────────────────────────────────────
    player = world.add_sphere(
        radius=0.35,
        position=(0.0, 0.0, 0.5),
        mass=3.0,
        restitution=0.25,
        friction=0.55,
        material="blue",
        name="player",
    )

    # ── Target towers  (5 positions × 3 levels = 15 boxes) ───────────────────
    tower_cfg = [
        ((-7.0, -7.0), "red", 0.55, 0.35, 0.5),
        ((7.0, -7.0), "orange", 0.55, 0.35, 0.5),
        ((-7.0, 7.0), "green", 0.55, 0.35, 0.5),
        ((7.0, 7.0), "gold", 0.80, 0.20, 0.4),
        ((0.0, 9.0), "white", 0.45, 0.40, 0.5),
    ]
    targets: list[f3d.Body] = []
    for (tx, ty), color, mass, restitution, friction in tower_cfg:
        for level in range(3):
            body = world.add_box(
                size=(0.8, 0.8, 0.8),
                position=(tx, ty, 0.4 + level * 0.85),
                mass=mass,
                restitution=restitution,
                friction=friction,
                material=color,
            )
            targets.append(body)

    # ── Loose chaos balls ─────────────────────────────────────────────────────
    for bx, by in [(4.0, 2.0), (-4.0, 2.0), (0.5, -4.5), (-2.0, 5.0)]:
        world.add_sphere(
            radius=0.22,
            position=(bx, by, 0.4),
            mass=0.25,
            restitution=0.6,
            friction=0.3,
            material="orange",
        )

    # ── Ramp (wedge built from two stacked static boxes with a gap) ───────────
    # A simple raised platform the player can roll up
    world._physics.add_static_box(
        size=(4.0, 1.5, 0.5),
        position=(0.0, -9.0, 0.25),
        material="ground",
        name="ramp_base",
        friction=0.5,
    )
    world._physics.add_static_box(
        size=(4.0, 1.5, 0.5),
        position=(0.0, -10.5, 0.50),
        material="ground",
        name="ramp_step",
        friction=0.5,
    )

    return world, player, targets
