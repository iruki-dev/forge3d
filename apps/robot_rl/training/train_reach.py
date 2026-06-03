"""Train a PPO policy on ReachEnv using Stable-Baselines3.

Usage
-----
    python apps/robot_rl/training/train_reach.py
    python apps/robot_rl/training/train_reach.py --steps 500000
    python apps/robot_rl/training/train_reach.py --steps 50000 --out /tmp/reach

Outputs
-------
    <out>/best_model/        — SB3 checkpoint (best mean reward)
    <out>/logs/progress.csv  — per-step success_rate / mean_reward / ep_len
    <out>/dashboard.png      — learning curve (generated after training)
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from apps.robot_rl.envs.reach_env import ReachEnv
from apps.robot_rl.training.callbacks import SuccessRateCallback
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CallbackList, CheckpointCallback
from stable_baselines3.common.monitor import Monitor

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_STEPS = 200_000
DEFAULT_OUT = "training_output/reach_ppo"

# PPO hyperparameters (tuned for CPU, single-env reaching)
PPO_KWARGS: dict = dict(
    n_steps=1024,
    batch_size=128,
    n_epochs=10,
    gamma=0.99,
    gae_lambda=0.95,
    clip_range=0.2,
    ent_coef=0.005,
    vf_coef=0.5,
    learning_rate=3e-4,
    max_grad_norm=0.5,
    verbose=1,
)


def train(total_steps: int = DEFAULT_STEPS, out_dir: str = DEFAULT_OUT) -> PPO:
    """Train PPO on ReachEnv and return the trained model."""
    os.makedirs(out_dir, exist_ok=True)
    log_dir = os.path.join(out_dir, "logs")
    ckpt_dir = os.path.join(out_dir, "checkpoints")
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(ckpt_dir, exist_ok=True)

    env = Monitor(ReachEnv(render_mode=None, max_steps=200))
    model = PPO("MlpPolicy", env, **PPO_KWARGS)

    success_cb = SuccessRateCallback(
        log_path=os.path.join(log_dir, "progress.csv"),
        window=100,
        log_freq=PPO_KWARGS["n_steps"],
        verbose=1,
    )
    ckpt_cb = CheckpointCallback(
        save_freq=max(1, total_steps // 10),
        save_path=ckpt_dir,
        name_prefix="reach_ppo",
        verbose=0,
    )

    print(f"\n{'=' * 60}")
    print("  forge3d · Reaching PPO training")
    print(f"  total_steps  = {total_steps:,}")
    print(f"  out_dir      = {out_dir}")
    print(f"{'=' * 60}\n")

    model.learn(
        total_timesteps=total_steps,
        callback=CallbackList([success_cb, ckpt_cb]),
        progress_bar=False,
    )

    # Save final model
    final_path = os.path.join(out_dir, "final_model")
    model.save(final_path)
    print(f"\nFinal model saved → {final_path}.zip")
    print(f"Final success rate: {success_cb.latest_success_rate:.1%}")

    env.close()
    return model


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Train PPO on ReachEnv")
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    parser.add_argument("--out", type=str, default=DEFAULT_OUT)
    args = parser.parse_args()

    model = train(total_steps=args.steps, out_dir=args.out)

    # Generate dashboard after training
    from apps.robot_rl.dashboard import generate_dashboard

    csv_path = os.path.join(args.out, "logs", "progress.csv")
    png_path = os.path.join(args.out, "dashboard.png")
    if os.path.exists(csv_path):
        generate_dashboard(csv_path, png_path)

    # Record rollout video
    print("\nRecording policy rollout…")
    import forge3d as f3d

    env_rgb = ReachEnv(render_mode="rgb_array", max_steps=200)
    rec = f3d.Recorder(
        world=None,  # not used for run_policy
        mode="hq",
        resolution=(480, 320),
        output=os.path.join(args.out, "reaching_rollout.mp4"),
    )
    rec.run_policy(model, env_rgb, duration=5.0, fps=24, seed=42)
    env_rgb.close()


if __name__ == "__main__":
    main()
