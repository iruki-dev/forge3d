"""Tests for forge3d.App — game-loop abstraction."""

from __future__ import annotations

import numpy as np
import pytest

import forge3d as f3d
from forge3d.app import App, _call_flexible
from forge3d.facade import World


class TestApp:
    def test_construction(self):
        app = App("Test", width=640, height=480, fps=30)
        assert app._title == "Test"
        assert app._width == 640
        assert app._height == 480
        assert app._fps == pytest.approx(30.0)
        assert app._dt == pytest.approx(1.0 / 30.0)

    def test_world_property(self):
        app = App()
        assert isinstance(app.world, World)

    def test_fps_setter(self):
        app = App(fps=60)
        app.fps = 120
        assert app.fps == pytest.approx(120.0)
        assert app._dt == pytest.approx(1.0 / 120.0)

    def test_fps_setter_rejects_nonpositive(self):
        app = App()
        with pytest.raises(ValueError, match="fps must be positive"):
            app.fps = 0

    def test_on_start_decorator(self):
        app = App()
        called = []

        @app.on_start
        def setup():
            called.append("start")

        assert app._on_start is setup

    def test_on_update_decorator(self):
        app = App()

        @app.on_update
        def update(world, dt, inp):
            pass

        assert app._on_update is update

    def test_on_render_decorator(self):
        app = App()

        @app.on_render
        def render(world):
            pass

        assert app._on_render is render

    def test_run_fires_on_start_no_args(self):
        app = App()
        called = []

        @app.on_start
        def setup():
            called.append("setup")

        app.run(max_frames=1)
        assert "setup" in called

    def test_run_fires_on_start_with_world(self):
        app = App()
        received = []

        @app.on_start
        def setup(world):
            received.append(world)

        app.run(max_frames=1)
        assert len(received) == 1
        assert isinstance(received[0], World)

    def test_run_fires_on_update(self):
        app = App()
        counts = [0]

        @app.on_update
        def update(world, dt, inp):
            counts[0] += 1

        app.run(max_frames=5)
        assert counts[0] == 5

    def test_run_update_receives_input(self):
        app = App()
        inputs = []

        @app.on_update
        def update(world, dt, inp):
            inputs.append(inp)

        app.run(max_frames=3)
        assert len(inputs) == 3
        # All inputs are Input objects
        assert all(isinstance(i, f3d.Input) for i in inputs)

    def test_run_update_receives_dt(self):
        app = App(fps=30)
        dts = []

        @app.on_update
        def update(world, dt, inp):
            dts.append(dt)

        app.run(max_frames=2)
        assert all(dt == pytest.approx(1 / 30) for dt in dts)

    def test_run_advances_physics(self):
        app = App()
        ball = None

        @app.on_start
        def setup(world):
            nonlocal ball
            world.add_ground()
            ball = world.add_sphere(position=(0, 0, 5), mass=1.0)

        app.run(max_frames=60)
        # Ball should have fallen from z=5
        assert ball is not None
        assert ball.position[2] < 5.0

    def test_update_flexible_signature_no_args(self):
        app = App()
        called = [False]

        @app.on_update
        def update():
            called[0] = True

        app.run(max_frames=1)
        assert called[0]

    def test_update_flexible_signature_world_only(self):
        app = App()
        received = []

        @app.on_update
        def update(world):
            received.append(world)

        app.run(max_frames=1)
        assert len(received) == 1

    def test_repr(self):
        app = App("Demo", fps=60)
        r = repr(app)
        assert "Demo" in r
        assert "fps=60" in r


class TestCallFlexible:
    def test_zero_args(self):
        called = []
        _call_flexible(lambda: called.append(1), "a", "b", "c")
        assert called == [1]

    def test_one_arg(self):
        received = []
        _call_flexible(lambda x: received.append(x), "hello", "ignored")
        assert received == ["hello"]

    def test_two_args(self):
        received = []
        _call_flexible(lambda x, y: received.extend([x, y]), "a", "b", "c")
        assert received == ["a", "b"]

    def test_three_args(self):
        received = []
        _call_flexible(lambda x, y, z: received.extend([x, y, z]), "a", "b", "c", "d")
        assert received == ["a", "b", "c"]

    def test_var_positional(self):
        received = []
        _call_flexible(lambda *args: received.extend(args), "a", "b", "c")
        assert received == ["a", "b", "c"]


class TestWorldNewAPI:
    def test_bodies_property(self):
        world = f3d.World()
        world.add_ground()
        b1 = world.add_box(position=(0, 0, 3))
        b2 = world.add_sphere(position=(1, 0, 3))
        bodies = world.bodies
        assert len(bodies) == 3  # ground + box + sphere
        assert b1 in bodies
        assert b2 in bodies

    def test_get_body_by_name(self):
        world = f3d.World()
        box = world.add_box(name="my_box", position=(0, 0, 3))
        found = world.get_body("my_box")
        assert found is box

    def test_get_body_missing_raises(self):
        world = f3d.World()
        with pytest.raises(KeyError):
            world.get_body("nonexistent")

    def test_remove_body(self):
        world = f3d.World()
        world.add_ground()
        box = world.add_box(position=(0, 0, 3))
        before = len(world.bodies)
        world.remove(box)
        assert len(world.bodies) == before - 1
        assert box not in world.bodies

    def test_clear_removes_dynamic(self):
        world = f3d.World()
        world.add_ground()   # static
        world.add_box(position=(0, 0, 3))
        world.add_sphere(position=(1, 0, 3))
        world.clear(keep_statics=True)
        bodies = world.bodies
        assert all(b.is_static for b in bodies)

    def test_clear_all(self):
        world = f3d.World()
        world.add_ground()
        world.add_box(position=(0, 0, 3))
        world.clear(keep_statics=False)
        assert world.bodies == []

    def test_body_name(self):
        world = f3d.World()
        box = world.add_box(name="test_box")
        assert box.name == "test_box"

    def test_body_is_static(self):
        world = f3d.World()
        ground = world.add_ground()
        box = world.add_box()
        assert ground.is_static
        assert not box.is_static

    def test_body_mass(self):
        world = f3d.World()
        box = world.add_box(mass=2.5)
        assert box.mass == pytest.approx(2.5)

    def test_body_apply_force(self):
        world = f3d.World()
        world.add_ground()
        box = world.add_box(position=(0, 0, 1), mass=1.0)
        # Apply upward force for 60 frames to counter gravity
        initial_z = box.position[2]
        for _ in range(60):
            box.apply_force((0, 0, 9.81))  # cancel gravity
            world.step(dt=1 / 60)
        # Box should stay approximately at starting height
        assert box.position[2] == pytest.approx(initial_z, abs=0.5)

    def test_body_set_velocity(self):
        world = f3d.World()
        box = world.add_box(position=(0, 0, 3))
        box.set_velocity((0, 0, -1))
        assert np.allclose(box.velocity, [0, 0, -1])

    def test_body_set_position(self):
        world = f3d.World()
        box = world.add_box(position=(0, 0, 3))
        box.set_position((5, 0, 0))
        assert np.allclose(box.position, [5, 0, 0])
