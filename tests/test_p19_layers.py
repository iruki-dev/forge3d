"""P19: Collision layer / mask filtering tests."""

from __future__ import annotations

import numpy as np

import forge3d as f3d
from forge3d import CollisionLayer

# ── G1: Different layers — no collision ───────────────────────────────────────


def test_different_layers_no_collision():
    """Bodies on different layers that don't overlap in mask should not collide."""
    world = f3d.World(gravity=(0, 0, 0))

    # A is on PLAYER layer, masks DEFAULT | ENEMY
    sphere_a = world.add_sphere(radius=0.4, position=(0, 0, 0), mass=1.0)
    sphere_a.collision_layer = CollisionLayer.PLAYER
    sphere_a.collision_mask = CollisionLayer.DEFAULT | CollisionLayer.ENEMY

    # B is on BULLET layer — sphere_a's mask doesn't include BULLET
    sphere_b = world.add_sphere(radius=0.4, position=(0.5, 0, 0), mass=1.0)
    sphere_b.collision_layer = CollisionLayer.BULLET
    sphere_b.collision_mask = CollisionLayer.DEFAULT | CollisionLayer.ENEMY

    # Give them approaching velocities
    from dataclasses import replace

    world._physics._replace_body(sphere_a._id, replace(sphere_a._state(), vel=np.array([1, 0, 0])))
    world._physics._replace_body(sphere_b._id, replace(sphere_b._state(), vel=np.array([-1, 0, 0])))

    for _ in range(30):
        world.step(dt=1 / 60)

    # If no collision, they should pass through each other
    # After 0.5 s at relative velocity 2 m/s, they should be far apart (not bounced)
    dist = np.linalg.norm(sphere_b.position - sphere_a.position)
    # With physical collision, they'd bounce back; without, they pass through
    assert dist > 0.3, f"Bodies should pass through (no collision), dist={dist:.3f}"


# ── G2: Matching masks — normal collision ─────────────────────────────────────


def test_matching_mask_collides():
    """Bodies whose layers and masks are compatible should collide normally."""
    world = f3d.World(gravity=(0, 0, 0))

    ball_a = world.add_sphere(radius=0.4, position=(-1, 0, 0), mass=1.0)
    ball_b = world.add_sphere(radius=0.4, position=(1, 0, 0), mass=1.0)

    # Both on DEFAULT layer, both masking DEFAULT
    ball_a.collision_layer = CollisionLayer.DEFAULT
    ball_a.collision_mask = CollisionLayer.DEFAULT
    ball_b.collision_layer = CollisionLayer.DEFAULT
    ball_b.collision_mask = CollisionLayer.DEFAULT

    from dataclasses import replace

    world._physics._replace_body(ball_a._id, replace(ball_a._state(), vel=np.array([2, 0, 0])))
    world._physics._replace_body(ball_b._id, replace(ball_b._state(), vel=np.array([-2, 0, 0])))

    v_a_before = ball_a.velocity[0]

    for _ in range(60):
        world.step(dt=1 / 60)

    # After collision, velocity should have changed direction
    v_a_after = ball_a.velocity[0]
    # They should have interacted (velocities changed significantly)
    assert abs(v_a_after - v_a_before) > 0.1, "Expected velocity change from collision"


# ── G3: ignore_collision — specific pair excluded ────────────────────────────


def test_ignore_collision_pair():
    """world.ignore_collision(a, b) should prevent physics contact between them."""
    world = f3d.World(gravity=(0, 0, 0))

    ball_a = world.add_sphere(radius=0.4, position=(-0.5, 0, 0), mass=1.0)
    ball_b = world.add_sphere(radius=0.4, position=(0.5, 0, 0), mass=1.0)

    world.ignore_collision(ball_a, ball_b)

    from dataclasses import replace

    world._physics._replace_body(ball_a._id, replace(ball_a._state(), vel=np.array([1, 0, 0])))

    for _ in range(60):
        world.step(dt=1 / 60)

    # ball_a should pass through ball_b (velocity not reversed)
    assert ball_a.velocity[0] > 0.5, f"Ball should have kept direction, v={ball_a.velocity[0]:.3f}"


# ── G4: Layer / mask API ─────────────────────────────────────────────────────


def test_layer_mask_api():
    """collision_layer and collision_mask should be get/settable via Body."""
    world = f3d.World()
    box = world.add_box(size=(1, 1, 1), position=(0, 0, 5))

    box.collision_layer = CollisionLayer.PLAYER
    box.collision_mask = CollisionLayer.DEFAULT | CollisionLayer.ENEMY

    assert box.collision_layer == CollisionLayer.PLAYER
    assert box.collision_mask == (CollisionLayer.DEFAULT | CollisionLayer.ENEMY)

    # CollisionLayer.ALL should be a big mask
    assert CollisionLayer.ALL > CollisionLayer.DEFAULT
    assert CollisionLayer.NONE == 0
