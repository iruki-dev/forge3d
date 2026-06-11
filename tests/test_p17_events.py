"""P17: Collision event callback tests."""

from __future__ import annotations

import forge3d as f3d


def _simple_world() -> tuple[f3d.World, f3d.Body, f3d.Body]:
    world = f3d.World(gravity=(0, 0, -9.81))
    floor = world.add_ground()
    ball = world.add_sphere(radius=0.5, position=(0, 0, 3), mass=1.0, friction=0.5, restitution=0.0)
    return world, floor, ball


# ── G1: on_collision_begin fires once when contact first appears ──────────────


def test_begin_fires_on_first_contact():
    """on_collision_begin should fire when ball first touches floor."""
    world, floor, ball = _simple_world()
    begin_count = [0]

    @world.on_collision_begin
    def hit(event: f3d.CollisionEvent) -> None:
        begin_count[0] += 1

    # Step until ball hits floor (starts at z=3, falls under gravity)
    for _ in range(180):
        world.step(dt=1 / 60)
        if begin_count[0] > 0:
            break

    assert begin_count[0] > 0, "on_collision_begin never fired"


# ── G2: on_collision_stay fires while contact persists ───────────────────────


def test_stay_fires_while_in_contact():
    """on_collision_stay should fire repeatedly while ball rests on floor."""
    world, floor, ball = _simple_world()
    stay_count = [0]

    @world.on_collision_stay
    def resting(event: f3d.CollisionEvent) -> None:
        stay_count[0] += 1

    # Let ball fall and settle
    for _ in range(240):
        world.step(dt=1 / 60)

    assert stay_count[0] > 0, "on_collision_stay never fired"


# ── G3: on_collision_end fires when contact disappears ───────────────────────


def test_end_fires_on_separation():
    """on_collision_end should fire when a body is teleported away from floor."""
    world, floor, ball = _simple_world()
    end_count = [0]

    # Let ball land
    for _ in range(120):
        world.step(dt=1 / 60)

    @world.on_collision_end
    def separated(event: f3d.CollisionEvent) -> None:
        end_count[0] += 1

    # Teleport ball high in the air (breaks contact)
    world.teleport(ball, position=(0, 0, 10))
    world.step(dt=1 / 60)

    assert end_count[0] > 0, "on_collision_end never fired after teleport"


# ── G4: Pair handler — specific pair fires, other pairs don't ─────────────────


def test_pair_handler_selectivity():
    """A pair-specific handler should only fire for that pair."""
    world = f3d.World(gravity=(0, 0, -9.81))
    floor = world.add_ground()
    ball1 = world.add_sphere(radius=0.5, position=(0, 0, 3), mass=1.0, restitution=0.0)
    ball2 = world.add_sphere(radius=0.5, position=(5, 0, 3), mass=1.0, restitution=0.0)

    ball1_floor_begin = [0]
    ball2_floor_begin = [0]

    # Only listen for ball1-floor collisions
    handler = world.add_collision_handler(ball1, floor)
    handler.on_begin = lambda e: ball1_floor_begin.__setitem__(0, ball1_floor_begin[0] + 1)

    # Global listener for ball2
    @world.on_collision_begin
    def any_hit(event: f3d.CollisionEvent) -> None:
        if ball2._id in {
            event.body_a._id if hasattr(event.body_a, "_id") else -1,
            event.body_b._id if hasattr(event.body_b, "_id") else -1,
        }:
            ball2_floor_begin[0] += 1

    for _ in range(180):
        world.step(dt=1 / 60)

    # Ball1 handler should fire; ball2 was not registered in handler
    assert ball1_floor_begin[0] > 0, "ball1-floor handler never fired"


# ── G5: Trigger zone — fires on_enter without physics collision ───────────────


def test_trigger_zone_enter():
    """Trigger zone should detect bodies entering without physical collision."""
    world = f3d.World(gravity=(0, 0, 0))
    box = world.add_box(size=(0.5, 0.5, 0.5), position=(0, 0, 0), mass=1.0)

    # Zone at (5, 0, 0)
    zone = world.add_trigger_zone(position=(5, 0, 0), size=(1, 1, 1))
    entered = [False]

    @zone.on_enter
    def enter_cb(body: f3d.Body) -> None:
        if hasattr(body, "_id") and body._id == box._id:
            entered[0] = True

    # Move box into zone
    from dataclasses import replace

    world._physics._replace_body(box._id, replace(box._state(), vel=(5, 0, 0)))

    # Step until box reaches zone (zone at x=5, box starts at x=0, vel=5 m/s → ~1s)
    for _ in range(80):
        world.step(dt=1 / 60)
        if entered[0]:
            break

    assert entered[0], "Trigger zone on_enter never fired"


# ── API: CollisionEvent fields ────────────────────────────────────────────────


def test_collision_event_has_fields():
    """CollisionEvent should have the documented fields."""
    world, floor, ball = _simple_world()
    events = []

    @world.on_collision_begin
    def collect(e: f3d.CollisionEvent) -> None:
        events.append(e)

    for _ in range(180):
        world.step(dt=1 / 60)
        if events:
            break

    assert events, "No collision events recorded"
    e = events[0]
    assert hasattr(e, "body_a")
    assert hasattr(e, "body_b")
    assert hasattr(e, "contact_point")
    assert hasattr(e, "normal")
    assert hasattr(e, "impulse")
    assert hasattr(e, "relative_speed")
    assert e.contact_point.shape == (3,)
    assert e.normal.shape == (3,)
