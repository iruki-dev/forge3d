"""ReachEnv — UR5 end-effector reaching task.

A Gymnasium environment where a UR5 arm must move its end-effector to a
randomly sampled target position.  Uses forge3d as an *external library*
(import-only, no internal modifications).

Observation (12,):  q[6] + ee_pos[3] + target_pos[3]
Action     (6,):    delta-q ∈ [-1, 1],  applied as  q += action * ACTION_SCALE
Reward:             -dist(EE, target)  - ctrl_penalty + success_bonus
Termination:        dist < SUCCESS_THRESHOLD  (success)
Truncation:         step >= max_steps

Render modes
------------
None        : no rendering (fastest, for training hot-loops)
"rgb_array" : HQRenderer → (H, W, 3) uint8 array
"human"     : RealtimeRenderer → offscreen frame (headless-compatible)
"""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError as e:
    raise ImportError("gymnasium is required: pip install gymnasium") from e

import forge3d as f3d
import forge3d.robot as f3r

# ── Constants ────────────────────────────────────────────────────────────────

ACTION_SCALE = 0.05  # rad per action unit
SUCCESS_THRESHOLD = 0.05  # m
CTRL_PENALTY = 0.01
SUCCESS_BONUS = 10.0
JOINT_LIMIT = np.pi  # rad

# UR5 neutral / home configuration
_HOME_Q = np.array([0.0, -np.pi / 2, np.pi / 2, -np.pi / 2, -np.pi / 2, 0.0])

# Workspace for random target (cylindrical shell)
_TARGET_R_MIN, _TARGET_R_MAX = 0.3, 0.65
_TARGET_Z_MIN, _TARGET_Z_MAX = 0.15, 0.70

# Render resolution
_W, _H = 480, 320


class ReachEnv(gym.Env):
    """UR5 end-effector reaching — Gymnasium-compliant environment.

    Parameters
    ----------
    render_mode : None | "human" | "rgb_array"
    max_steps   : Episode horizon (default 200).
    dt          : Physics step size in seconds (default 1/60).
    """

    metadata: dict[str, Any] = {
        "render_modes": ["human", "rgb_array"],
        "render_fps": 30,
    }

    def __init__(
        self,
        render_mode: str | None = None,
        max_steps: int = 200,
        dt: float = 1.0 / 60.0,
    ) -> None:
        super().__init__()

        if render_mode is not None and render_mode not in self.metadata["render_modes"]:
            raise ValueError(
                f"render_mode={render_mode!r} not supported. "
                f"Choose from {self.metadata['render_modes']} or None."
            )

        self.render_mode = render_mode
        self._max_steps = max_steps
        self._dt = dt

        # ── Spaces ────────────────────────────────────────────────────────────
        q_low = np.full(6, -JOINT_LIMIT, dtype=np.float32)
        q_high = np.full(6, JOINT_LIMIT, dtype=np.float32)
        ee_low = np.full(3, -2.0, dtype=np.float32)
        ee_high = np.full(3, 2.0, dtype=np.float32)
        tgt_low = np.full(3, -2.0, dtype=np.float32)
        tgt_high = np.full(3, 2.0, dtype=np.float32)

        self.observation_space = spaces.Box(
            low=np.concatenate([q_low, ee_low, tgt_low]),
            high=np.concatenate([q_high, ee_high, tgt_high]),
            dtype=np.float32,
        )
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32)

        # ── Internal state (created lazily in first reset) ───────────────────
        self._world: f3d.World | None = None
        self._arm: f3r.Robot | None = None
        self._target_marker: Any = None  # Body handle for target sphere
        self._target_pos: np.ndarray = np.zeros(3)
        self._step_count: int = 0
        self._renderer: Any = None

    # ── Gymnasium API ─────────────────────────────────────────────────────────

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)

        # ── Lazy world construction (reused across episodes for speed) ────────
        if self._world is None:
            world = f3d.World(gravity=(0.0, 0.0, -9.81))
            world.add_ground()
            arm = f3r.load("ur5")
            world.add(arm)
            target_marker = world.add_sphere(
                radius=0.04,
                position=(1.0, 0.0, 0.3),  # placeholder; moved below
                static=True,
                material=f3d.Material(color="red"),
                name="target",
            )
            world.set_camera(position=(1.4, -1.6, 1.0), target=(0.0, 0.0, 0.4))
            self._world = world
            self._arm = arm
            self._target_marker = target_marker

        # ── Episode reset (cheap: joint angles + target position only) ────────
        self._arm.set_joints(_HOME_Q.copy())

        r = float(self.np_random.uniform(_TARGET_R_MIN, _TARGET_R_MAX))
        theta = float(self.np_random.uniform(-np.pi, np.pi))
        z = float(self.np_random.uniform(_TARGET_Z_MIN, _TARGET_Z_MAX))
        target_pos = np.array([r * np.cos(theta), r * np.sin(theta), z])

        self._world.teleport(self._target_marker, tuple(target_pos))

        self._target_pos = target_pos
        self._step_count = 0

        obs = self._obs()
        info: dict[str, Any] = {"distance": self._distance(), "success": False}

        if self.render_mode == "human":
            self.render()

        return obs, info

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        assert self._arm is not None and self._world is not None

        action = np.asarray(action, dtype=float).clip(-1.0, 1.0)

        # Apply delta-q, clamp to joint limits
        new_q = np.clip(self._arm._q + action * ACTION_SCALE, -JOINT_LIMIT, JOINT_LIMIT)
        self._arm.set_joints(new_q)
        self._world.step(dt=self._dt)
        self._step_count += 1

        # Compute FK once, share between obs + reward
        ee_pos, _ = self._arm.ee_pose()
        dist = float(np.linalg.norm(ee_pos - self._target_pos))
        success = dist < SUCCESS_THRESHOLD

        reward = float(
            -dist - CTRL_PENALTY * float(np.sum(action**2)) + (SUCCESS_BONUS if success else 0.0)
        )

        terminated = bool(success)
        truncated = self._step_count >= self._max_steps

        obs = np.concatenate(
            [
                new_q.astype(np.float32),
                ee_pos.astype(np.float32),
                self._target_pos.astype(np.float32),
            ]
        )
        info: dict[str, Any] = {"distance": float(dist), "success": bool(success)}

        if self.render_mode == "human":
            self.render()

        return obs, reward, terminated, truncated, info

    def render(self) -> np.ndarray | None:
        """Render the current state.

        Returns
        -------
        None if render_mode is None or "human".
        (H, W, 3) uint8 if render_mode is "rgb_array".
        """
        if self.render_mode is None or self._world is None:
            return None

        snap = self._world.snapshot()

        if self.render_mode == "rgb_array":
            if self._renderer is None:
                from forge3d.render.hq.renderer import HQRenderer

                self._renderer = HQRenderer(width=_W, height=_H, samples=1)
            return self._renderer.render(snap)

        if self.render_mode == "human":
            if self._renderer is None:
                from forge3d.render.realtime.renderer import RealtimeRenderer

                self._renderer = RealtimeRenderer(width=_W, height=_H)
            self._renderer.render(snap)
            return None

        return None

    def close(self) -> None:
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _obs(self) -> np.ndarray:
        assert self._arm is not None
        q = self._arm.q.astype(np.float32)
        ee_pos, _ = self._arm.ee_pose()
        return np.concatenate([q, ee_pos.astype(np.float32), self._target_pos.astype(np.float32)])

    def _distance(self) -> float:
        assert self._arm is not None
        ee_pos, _ = self._arm.ee_pose()
        return float(np.linalg.norm(ee_pos - self._target_pos))
