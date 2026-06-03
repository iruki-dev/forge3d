"""P8 tests: ReachEnv Gymnasium compliance + render_mode gate."""

from __future__ import annotations

import sys

import numpy as np
import pytest

# apps/ is at project root, not in src/ — add to path for test imports
sys.path.insert(0, ".")

from apps.robot_rl.envs.reach_env import (
    JOINT_LIMIT,
    ReachEnv,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def env_headless():
    env = ReachEnv(render_mode=None, max_steps=50)
    yield env
    env.close()


@pytest.fixture()
def env_rgb():
    env = ReachEnv(render_mode="rgb_array", max_steps=10)
    yield env
    env.close()


# ── Observation / action space ────────────────────────────────────────────────


class TestSpaces:
    def test_obs_space_shape(self, env_headless):
        assert env_headless.observation_space.shape == (12,)

    def test_action_space_shape(self, env_headless):
        assert env_headless.action_space.shape == (6,)

    def test_action_space_bounds(self, env_headless):
        assert env_headless.action_space.low[0] == pytest.approx(-1.0)
        assert env_headless.action_space.high[0] == pytest.approx(1.0)

    def test_obs_space_dtype(self, env_headless):
        assert env_headless.observation_space.dtype == np.float32


# ── reset ─────────────────────────────────────────────────────────────────────


class TestReset:
    def test_reset_returns_obs_info(self, env_headless):
        obs, info = env_headless.reset(seed=42)
        assert isinstance(obs, np.ndarray)
        assert obs.shape == (12,)
        assert obs.dtype == np.float32
        assert isinstance(info, dict)

    def test_reset_info_has_distance(self, env_headless):
        _, info = env_headless.reset(seed=1)
        assert "distance" in info
        assert info["distance"] >= 0.0

    def test_reset_info_success_false(self, env_headless):
        _, info = env_headless.reset(seed=1)
        assert info["success"] is False

    def test_reset_obs_within_space(self, env_headless):
        obs, _ = env_headless.reset(seed=7)
        assert env_headless.observation_space.contains(obs), f"obs not in space: {obs}"

    def test_reset_reproducible(self, env_headless):
        obs1, _ = env_headless.reset(seed=99)
        obs2, _ = env_headless.reset(seed=99)
        np.testing.assert_array_equal(obs1, obs2)

    def test_reset_different_seeds_differ(self, env_headless):
        obs1, _ = env_headless.reset(seed=1)
        obs2, _ = env_headless.reset(seed=2)
        # Target positions (last 3 elements) should differ
        assert not np.allclose(obs1[9:], obs2[9:])


# ── step ──────────────────────────────────────────────────────────────────────


class TestStep:
    def test_step_return_types(self, env_headless):
        env_headless.reset(seed=0)
        obs, reward, terminated, truncated, info = env_headless.step(
            env_headless.action_space.sample()
        )
        assert obs.shape == (12,)
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)

    def test_step_info_has_distance_and_success(self, env_headless):
        env_headless.reset(seed=0)
        _, _, _, _, info = env_headless.step(np.zeros(6))
        assert "distance" in info and "success" in info

    def test_step_distance_nonneg(self, env_headless):
        env_headless.reset(seed=3)
        for _ in range(5):
            _, _, _, _, info = env_headless.step(np.zeros(6))
        assert info["distance"] >= 0.0

    def test_step_reward_decreases_with_distance(self, env_headless):
        env_headless.reset(seed=10)
        _, r, _, _, info = env_headless.step(np.zeros(6))
        assert r < 0 or info["success"], "reward should be negative unless success"

    def test_truncation_at_max_steps(self):
        env = ReachEnv(render_mode=None, max_steps=3)
        env.reset(seed=0)
        truncated = False
        for _ in range(3):
            _, _, _, truncated, _ = env.step(np.zeros(6))
        assert truncated, "Episode should truncate at max_steps"
        env.close()

    def test_action_clipping(self, env_headless):
        env_headless.reset(seed=0)
        large_action = np.full(6, 100.0)
        obs, _, _, _, _ = env_headless.step(large_action)
        # Joint angles should stay within limits
        q = obs[:6]
        assert np.all(q >= -JOINT_LIMIT - 1e-6) and np.all(q <= JOINT_LIMIT + 1e-6)


# ── Gate G1: render_mode 전환 ─────────────────────────────────────────────────


class TestRenderMode:
    def test_render_none_returns_none(self):
        env = ReachEnv(render_mode=None)
        env.reset(seed=0)
        result = env.render()
        assert result is None
        env.close()

    def test_render_rgb_array_returns_frame(self, env_rgb):
        env_rgb.reset(seed=0)
        frame = env_rgb.render()
        assert frame is not None
        assert isinstance(frame, np.ndarray)
        assert frame.ndim == 3
        assert frame.shape[2] == 3
        assert frame.dtype == np.uint8

    def test_render_rgb_array_frame_has_content(self, env_rgb):
        env_rgb.reset(seed=0)
        frame = env_rgb.render()
        assert frame is not None
        assert frame.max() > 10, "Frame appears to be all black"
        assert frame.std() > 5, "Frame has no variation"

    def test_render_human_mode_no_crash(self):
        """'human' render mode should not raise even in headless."""
        env = ReachEnv(render_mode="human", max_steps=3)
        env.reset(seed=0)
        env.step(np.zeros(6))
        env.close()

    def test_invalid_render_mode_raises(self):
        with pytest.raises(ValueError, match="render_mode"):
            ReachEnv(render_mode="invalid_mode")

    def test_render_after_multiple_steps(self, env_rgb):
        env_rgb.reset(seed=0)
        for _ in range(5):
            env_rgb.step(env_rgb.action_space.sample())
        frame = env_rgb.render()
        assert frame is not None and frame.shape[2] == 3

    def test_render_returns_none_before_reset(self):
        env = ReachEnv(render_mode="rgb_array")
        # No reset yet — world is None
        result = env.render()
        assert result is None
        env.close()


# ── Gate G2: Gymnasium API compliance ────────────────────────────────────────


class TestGymnasiumCompliance:
    def test_reset_step_loop(self):
        """Full episode loop should complete without error."""
        env = ReachEnv(render_mode=None, max_steps=20)
        obs, info = env.reset(seed=0)
        assert obs.shape == (12,)
        done = False
        steps = 0
        while not done:
            obs, reward, terminated, truncated, info = env.step(env.action_space.sample())
            done = terminated or truncated
            steps += 1
        assert steps <= 20
        env.close()

    def test_obs_in_space_after_step(self, env_headless):
        env_headless.reset(seed=0)
        for _ in range(5):
            obs, _, _, _, _ = env_headless.step(env_headless.action_space.sample())
        assert env_headless.observation_space.contains(obs)

    def test_action_sample_in_space(self, env_headless):
        for _ in range(10):
            a = env_headless.action_space.sample()
            assert env_headless.action_space.contains(a)

    def test_close_is_idempotent(self, env_headless):
        env_headless.reset(seed=0)
        env_headless.close()
        env_headless.close()  # second close should not raise

    def test_check_env(self):
        """gymnasium.utils.env_checker should pass without errors."""
        from gymnasium.utils.env_checker import check_env

        env = ReachEnv(render_mode=None, max_steps=20)
        check_env(env, warn=True)
        env.close()
