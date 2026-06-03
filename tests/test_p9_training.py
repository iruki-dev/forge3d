"""P9 tests: training infrastructure, dashboard, run_policy."""

from __future__ import annotations

import csv
import os
import sys
import tempfile

import numpy as np
import pytest

sys.path.insert(0, ".")

from apps.robot_rl.envs.reach_env import ReachEnv
from apps.robot_rl.training.callbacks import SuccessRateCallback

# ── SuccessRateCallback ───────────────────────────────────────────────────────


class TestSuccessRateCallback:
    def test_csv_created_on_init(self, tmp_path):
        SuccessRateCallback(str(tmp_path / "log.csv"), log_freq=10)
        assert (tmp_path / "log.csv").exists()

    def test_csv_has_header(self, tmp_path):
        SuccessRateCallback(str(tmp_path / "log.csv"), log_freq=10)
        with open(tmp_path / "log.csv") as f:
            reader = csv.reader(f)
            header = next(reader)
        assert "timestep" in header
        assert "success_rate" in header
        assert "mean_reward" in header

    def test_latest_success_rate_zero_initially(self, tmp_path):
        cb = SuccessRateCallback(str(tmp_path / "log.csv"), log_freq=10)
        assert cb.latest_success_rate == 0.0  # noqa: F841


# ── Dashboard ─────────────────────────────────────────────────────────────────


class TestDashboard:
    def _write_csv(self, path: str, rows: list[tuple]) -> None:
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestep", "success_rate", "mean_reward", "mean_ep_length"])
            writer.writerows(rows)

    def test_generate_dashboard_creates_png(self, tmp_path):
        from apps.robot_rl.dashboard import generate_dashboard

        csv_p = str(tmp_path / "log.csv")
        png_p = str(tmp_path / "dash.png")
        rows = [(i * 1000, i / 100, -5 + i * 0.1, 200 - i) for i in range(20)]
        self._write_csv(csv_p, rows)
        generate_dashboard(csv_p, png_p)
        assert os.path.exists(png_p), "dashboard PNG not created"
        assert os.path.getsize(png_p) > 1000, "dashboard PNG is too small"

    def test_generate_dashboard_missing_csv(self, tmp_path):
        from apps.robot_rl.dashboard import generate_dashboard

        # Should not raise, just print a warning
        generate_dashboard(str(tmp_path / "nonexistent.csv"), str(tmp_path / "out.png"))

    def test_load_csv(self, tmp_path):
        from apps.robot_rl.dashboard import load_csv

        csv_p = str(tmp_path / "log.csv")
        rows = [(1000, 0.1, -5.0, 200), (2000, 0.2, -4.0, 180)]
        self._write_csv(csv_p, rows)
        data = load_csv(csv_p)
        assert "timestep" in data
        assert data["timestep"] == [1000.0, 2000.0]
        assert data["success_rate"] == pytest.approx([0.1, 0.2])


# ── PPO smoke training ────────────────────────────────────────────────────────


class TestPPOSmoke:
    """Short training run to verify infrastructure works end-to-end."""

    def test_short_training_no_crash(self, tmp_path):
        """Train for 2048 steps (1 rollout buffer) and verify no errors."""
        try:
            from stable_baselines3 import PPO
            from stable_baselines3.common.monitor import Monitor
        except ImportError:
            pytest.skip("stable-baselines3 not installed")

        env = Monitor(ReachEnv(render_mode=None, max_steps=50))
        model = PPO(
            "MlpPolicy",
            env,
            n_steps=512,
            batch_size=64,
            n_epochs=2,
            verbose=0,
        )

        cb = SuccessRateCallback(str(tmp_path / "log.csv"), log_freq=512)
        model.learn(total_timesteps=1024, callback=cb)
        env.close()

        assert os.path.exists(str(tmp_path / "log.csv"))

    def test_model_predict_after_training(self, tmp_path):
        """Trained model must be able to predict actions."""
        try:
            from stable_baselines3 import PPO
            from stable_baselines3.common.monitor import Monitor
        except ImportError:
            pytest.skip("stable-baselines3 not installed")

        env = Monitor(ReachEnv(render_mode=None, max_steps=50))
        model = PPO("MlpPolicy", env, n_steps=512, batch_size=64, n_epochs=1, verbose=0)
        model.learn(total_timesteps=512)

        obs, _ = env.reset(seed=0)
        action, _ = model.predict(obs, deterministic=True)
        assert action.shape == (6,)
        assert np.all(np.isfinite(action))
        env.close()


# ── Recorder.run_policy ───────────────────────────────────────────────────────


class TestRunPolicy:
    def test_run_policy_produces_output(self, tmp_path):
        """run_policy should produce a video file."""
        try:
            from stable_baselines3 import PPO
            from stable_baselines3.common.monitor import Monitor
        except ImportError:
            pytest.skip("stable-baselines3 not installed")

        import forge3d as f3d

        env_train = Monitor(ReachEnv(render_mode=None, max_steps=50))
        model = PPO("MlpPolicy", env_train, n_steps=512, batch_size=64, n_epochs=1, verbose=0)
        model.learn(total_timesteps=512)
        env_train.close()

        out = str(tmp_path / "rollout.mp4")
        env_rgb = ReachEnv(render_mode="rgb_array", max_steps=30)
        rec = f3d.Recorder(output=out, mode="hq", resolution=(80, 60), samples=1)
        rec.run_policy(model, env_rgb, duration=1.0, fps=10, seed=0)
        env_rgb.close()

        assert os.path.exists(out), "rollout.mp4 not created"
        assert os.path.getsize(out) > 1000

    def test_run_policy_requires_render_mode(self):
        """run_policy with render_mode=None env returns no frames (no crash)."""
        try:
            from stable_baselines3 import PPO
            from stable_baselines3.common.monitor import Monitor
        except ImportError:
            pytest.skip("stable-baselines3 not installed")

        import forge3d as f3d

        env_train = Monitor(ReachEnv(render_mode=None, max_steps=50))
        model = PPO("MlpPolicy", env_train, n_steps=512, batch_size=64, n_epochs=1, verbose=0)
        model.learn(total_timesteps=512)
        env_train.close()

        with tempfile.TemporaryDirectory() as td:
            env_none = ReachEnv(render_mode=None, max_steps=10)
            rec = f3d.Recorder(
                output=os.path.join(td, "out.mp4"), mode="hq", resolution=(32, 24), samples=1
            )
            rec.run_policy(model, env_none, duration=0.5, fps=5)
            env_none.close()


# ── World.teleport ────────────────────────────────────────────────────────────


class TestWorldTeleport:
    def test_teleport_changes_body_position(self):
        import forge3d as f3d

        world = f3d.World()
        box = world.add_box(size=(0.5, 0.5, 0.5), position=(0, 0, 5))
        original_pos = box.position.copy()
        world.teleport(box, (3.0, 2.0, 1.0))
        new_pos = box.position
        assert not np.allclose(original_pos, new_pos)
        np.testing.assert_allclose(new_pos, [3.0, 2.0, 1.0], atol=1e-10)

    def test_teleport_static_body(self):
        import forge3d as f3d

        world = f3d.World()
        world.add_ground()
        target = world.add_sphere(radius=0.05, position=(0, 0, 1), static=True, material="red")
        world.teleport(target, (1.0, 2.0, 0.5))
        np.testing.assert_allclose(target.position, [1.0, 2.0, 0.5], atol=1e-10)
