"""P10 tests: weld abstraction + PickPlaceEnv API."""

from __future__ import annotations

import sys

import numpy as np
import pytest

sys.path.insert(0, ".")

from apps.robot_rl.envs.pick_place_env import PickPlaceEnv

import forge3d as f3d

# ── World.weld / World.release ────────────────────────────────────────────────


class TestWeld:
    def test_welded_body_follows_anchor(self):
        """After weld, obj.position tracks anchor."""
        world = f3d.World()
        obj = world.add_box(size=(0.1, 0.1, 0.1), position=(0.0, 0.0, 2.0), mass=1.0)
        anchor = world.add_sphere(radius=0.05, position=(0.0, 0.0, 2.2), static=True)
        world.weld(obj, anchor)

        # Move anchor up 1 m
        world.teleport(anchor, (0.0, 0.0, 3.2))
        world.step(dt=1 / 60)

        obj_z = float(obj.position[2])
        # Object should follow anchor: new_z ≈ 3.2 + original_offset = 3.2 - 0.2 = 3.0
        assert obj_z == pytest.approx(3.0, abs=0.05), f"obj_z={obj_z:.3f}"

    def test_released_body_falls(self):
        """After release, obj falls with gravity."""
        world = f3d.World()
        world.add_ground()
        # Anchor is ABOVE the box so the sphere is not in the box's fall path.
        # Box weld offset is computed automatically as pos_box - pos_anchor.
        anchor = world.add_sphere(radius=0.05, position=(0.0, 0.0, 3.0), static=True)
        obj = world.add_box(
            size=(0.1, 0.1, 0.1), position=(0.0, 0.0, 2.2), mass=1.0, restitution=0.0
        )
        world.weld(obj, anchor)

        # Weld holds
        world.step(dt=1 / 60)
        z_welded = float(obj.position[2])
        assert z_welded == pytest.approx(2.2, abs=0.05)

        # Release
        world.release(obj)
        for _ in range(60):
            world.step(dt=1 / 60)
        z_released = float(obj.position[2])
        assert z_released < 0.3, f"obj should have fallen: z={z_released:.3f}"

    def test_weld_auto_offset(self):
        """weld() computes offset from current relative position."""
        world = f3d.World()
        anchor = world.add_sphere(radius=0.05, position=(1.0, 0.0, 1.0), static=True)
        obj = world.add_box(size=(0.1, 0.1, 0.1), position=(1.0, 0.0, 1.3), mass=1.0)
        world.weld(obj, anchor)  # offset should be (0, 0, 0.3) in anchor frame

        world.step(dt=1 / 60)
        np.testing.assert_allclose(obj.position, [1.0, 0.0, 1.3], atol=0.05)

    def test_double_release_no_crash(self):
        """release() called twice should not raise."""
        world = f3d.World()
        anchor = world.add_sphere(radius=0.05, position=(0, 0, 1), static=True)
        obj = world.add_box(size=(0.1, 0.1, 0.1), position=(0, 0, 1.1), mass=1.0)
        world.weld(obj, anchor)
        world.release(obj)
        world.release(obj)  # second call is a no-op

    def test_weld_with_explicit_offset(self):
        """weld() with explicit local_offset stores it correctly."""
        world = f3d.World()
        anchor = world.add_sphere(radius=0.05, position=(0, 0, 1), static=True)
        obj = world.add_box(size=(0.1, 0.1, 0.1), position=(0, 0, 2), mass=1.0)
        world.weld(obj, anchor, local_offset=(0.0, 0.0, 0.5))
        world.step(dt=1 / 60)
        # obj should be at anchor_pos + [0, 0, 0.5] = (0, 0, 1.5)
        np.testing.assert_allclose(obj.position, [0.0, 0.0, 1.5], atol=0.05)


# ── PickPlaceEnv API ──────────────────────────────────────────────────────────


class TestPickPlaceEnv:
    @pytest.fixture
    def env(self):
        e = PickPlaceEnv(render_mode=None, max_steps=50)
        yield e
        e.close()

    def test_obs_shape(self, env):
        obs, _ = env.reset(seed=0)
        assert obs.shape == (16,)
        assert obs.dtype == np.float32

    def test_action_space(self, env):
        assert env.action_space.shape == (7,)

    def test_reset_returns_info(self, env):
        obs, info = env.reset(seed=42)
        assert "dist_ee_obj" in info
        assert "dist_obj_tgt" in info
        assert "grasped" in info
        assert info["grasped"] is False

    def test_step_return_types(self, env):
        env.reset(seed=0)
        obs, reward, term, trunc, info = env.step(env.action_space.sample())
        assert obs.shape == (16,)
        assert isinstance(reward, float)
        assert isinstance(term, bool)
        assert isinstance(trunc, bool)

    def test_grasp_trigger_activates_weld(self, env):
        """Grasp action near object should attach (grasped=True)."""
        env.reset(seed=0)
        # Force arm to be very close to object
        # (hard to do without IK, so we use env internals in test)
        # Teleport arm EE to be next to the object via obj teleport
        env._world.teleport(env._obj, tuple(env._arm.ee_pose()[0] + [0.02, 0, 0]))

        grasp_action = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], dtype=np.float32)
        _, _, _, _, info = env.step(grasp_action)
        # Should have grasped since obj is near EE
        assert info.get("grasped", False) or info.get("grasp_event", False)

    def test_truncation_at_max_steps(self, env):
        env.reset(seed=0)
        done = False
        steps = 0
        while not done:
            _, _, term, trunc, _ = env.step(env.action_space.sample())
            done = term or trunc
            steps += 1
        assert steps <= 50

    def test_grasped_flag_in_obs(self, env):
        """Obs last element is grasped flag (0 or 1)."""
        obs, _ = env.reset(seed=0)
        assert float(obs[-1]) == pytest.approx(0.0)  # not grasped at reset


# ── render_mode ───────────────────────────────────────────────────────────────


class TestPickPlaceRender:
    def test_rgb_array_returns_frame(self):
        env = PickPlaceEnv(render_mode="rgb_array", max_steps=5)
        env.reset(seed=0)
        frame = env.render()
        assert frame is not None
        assert frame.shape == (320, 480, 3)
        assert frame.dtype == np.uint8
        env.close()

    def test_none_render_returns_none(self):
        env = PickPlaceEnv(render_mode=None, max_steps=5)
        env.reset(seed=0)
        assert env.render() is None
        env.close()
