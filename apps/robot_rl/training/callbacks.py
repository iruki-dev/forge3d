"""Training callbacks for robot_rl.

SuccessRateCallback: tracks per-episode success and logs to CSV.
"""

from __future__ import annotations

import csv
import os

import numpy as np

try:
    from stable_baselines3.common.callbacks import BaseCallback
except ImportError as exc:
    raise ImportError("stable-baselines3 is required: pip install stable-baselines3") from exc


class SuccessRateCallback(BaseCallback):
    """Log success rate, mean reward, and mean episode length to a CSV file.

    Aggregates over the last ``window`` completed episodes and writes a row
    every ``log_freq`` timesteps.

    CSV columns: timestep, success_rate, mean_reward, mean_ep_length
    """

    def __init__(
        self,
        log_path: str,
        window: int = 100,
        log_freq: int = 2048,
        verbose: int = 0,
    ) -> None:
        super().__init__(verbose)
        self._log_path = log_path
        self._window = window
        self._log_freq = log_freq
        self._last_log_step = 0

        # Per-episode buffers
        self._ep_successes: list[float] = []
        self._ep_rewards: list[float] = []
        self._ep_lengths: list[int] = []

        os.makedirs(os.path.dirname(log_path) if os.path.dirname(log_path) else ".", exist_ok=True)
        with open(log_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestep", "success_rate", "mean_reward", "mean_ep_length"])

    def _on_step(self) -> bool:
        for i, done in enumerate(self.locals.get("dones", [])):
            if done:
                info = self.locals["infos"][i]
                ep_info = info.get("episode", {})
                self._ep_successes.append(1.0 if info.get("success", False) else 0.0)
                if "r" in ep_info:
                    self._ep_rewards.append(float(ep_info["r"]))
                if "l" in ep_info:
                    self._ep_lengths.append(int(ep_info["l"]))

        if self.num_timesteps - self._last_log_step >= self._log_freq:
            self._write_row()
            self._last_log_step = self.num_timesteps

        return True

    def _on_training_end(self) -> None:
        if self._ep_successes:
            self._write_row()

    def _write_row(self) -> None:
        n = self._window
        sr = float(np.mean(self._ep_successes[-n:])) if self._ep_successes else 0.0
        mr = float(np.mean(self._ep_rewards[-n:])) if self._ep_rewards else 0.0
        ml = float(np.mean(self._ep_lengths[-n:])) if self._ep_lengths else 0.0
        with open(self._log_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([self.num_timesteps, f"{sr:.4f}", f"{mr:.4f}", f"{ml:.1f}"])
        if self.verbose >= 1:
            print(
                f"  [t={self.num_timesteps:>7d}]  "
                f"success={sr:.1%}  reward={mr:.3f}  ep_len={ml:.0f}"
            )

    @property
    def latest_success_rate(self) -> float:
        n = self._window
        return float(np.mean(self._ep_successes[-n:])) if self._ep_successes else 0.0
