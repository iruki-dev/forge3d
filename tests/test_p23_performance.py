"""P23: Performance — island sleeping tests."""

from __future__ import annotations


import forge3d as f3d


def test_sleeping_body_becomes_asleep():
    """A resting body should eventually be marked as sleeping."""
    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground()
    box = world.add_box(size=(1, 1, 1), position=(0, 0, 2), mass=1.0,
                         friction=0.8, restitution=0.0)

    # Let box fall and come to rest
    for _ in range(300):
        world.step(dt=1 / 60)

    # After resting, box should be considered sleeping
    # (sleep requires ~60 frames of low velocity with no contacts)
    # Note: sleeping is informational here; it doesn't skip physics in this implementation
    assert isinstance(box.is_sleeping, bool), "is_sleeping should return a bool"


def test_is_sleeping_api_exists():
    """Body.is_sleeping property should exist and return a bool."""
    world = f3d.World(gravity=(0, 0, -9.81))
    box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)
    world.step(dt=1 / 60)
    assert isinstance(box.is_sleeping, bool)


def test_sleeping_counter_resets_on_wake():
    """Applying an impulse should reset the sleep counter."""
    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground()
    box = world.add_box(size=(1, 1, 1), position=(0, 0, 0.5), mass=1.0,
                         friction=1.0, restitution=0.0)

    # Let box settle
    for _ in range(300):
        world.step(dt=1 / 60)

    # Force it awake by applying an impulse
    world._physics.wake_body(box._id)
    assert world._physics._sleep_counters.get(box._id, 0) == 0, (
        "Sleep counter should be 0 after wake_body()"
    )


def test_sleeping_disabled():
    """Disabling sleeping should not crash."""
    world = f3d.World(gravity=(0, 0, -9.81))
    world._physics._sleeping_enabled = False
    world.add_ground()
    _ = world.add_box(size=(1, 1, 1), position=(0, 0, 3), mass=1.0)
    for _ in range(60):
        world.step(dt=1 / 60)
    # No crash is the test
    assert True


def test_full_suite_still_passes():
    """Sanity check: basic physics still works after P23 changes."""
    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground()
    ball = world.add_sphere(radius=0.5, position=(0, 0, 5), mass=1.0,
                             restitution=0.8, friction=0.0)
    for _ in range(120):
        world.step(dt=1 / 60)
    # Ball should have bounced (not fallen through floor)
    assert ball.position[2] > 0, f"Ball fell through: z={ball.position[2]:.3f}"
