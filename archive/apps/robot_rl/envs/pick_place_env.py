"""PickPlaceEnv — UR5 pick-and-place with weld abstraction.

The robot must:
  1. Move its EE to the object,
  2. Trigger grasp (weld constraint activates when EE is close enough),
  3. Carry the object to the target position,
  4. Release.

Weld abstraction: no real friction/contact physics.  When the grasp action
is triggered and EE is within GRASP_DIST, the object is kinematically
attached to the EE link.

Observation (16,):  q[6] + ee_pos[3] + obj_pos[3] + tgt_pos[3] + grasped[1]
Action     (7,):    delta_q[6] + grasp_ctrl[1]
  grasp_ctrl > +0.5 AND dist(EE, obj) < GRASP_DIST → weld
  grasp_ctrl < -0.5 AND grasped               → release

Reward (phased):
  not grasped : -0.3 * dist(EE, obj)
  grasped     : +5 (once on grasp) -0.5 * dist(obj, tgt)
  placed      : +20, terminate
"""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError as exc:
    raise ImportError("gymnasium is required: pip install gymnasium") from exc

import forge3d as f3d
import forge3d.robot as f3r

# ── Constants ─────────────────────────────────────────────────────────────────

ACTION_SCALE = 0.04
JOINT_LIMIT = np.pi
GRASP_DIST = 0.12  # m: EE must be within this to allow grasp
PLACE_DIST = 0.10  # m: success threshold
GRASP_BONUS = 5.0
PLACE_BONUS = 20.0
CTRL_PENALTY = 0.005

_HOME_Q = np.array([0.0, -np.pi / 2, np.pi / 2, -np.pi / 2, -np.pi / 2, 0.0])
_OBJ_SIZE = (0.08, 0.08, 0.08)  # cube side length
_W, _H = 480, 320


class PickPlaceEnv(gym.Env):
    """UR5 pick-and-place using weld abstraction.

    Parameters
    ----------
    render_mode : None | "rgb_array" | "human"
    max_steps   : Episode horizon.
    dt          : Physics step size.
    """

    metadata: dict[str, Any] = {
        "render_modes": ["human", "rgb_array"],
        "render_fps": 24,
    }

    def __init__(
        self,
        render_mode: str | None = None,
        max_steps: int = 300,
        dt: float = 1.0 / 60.0,
    ) -> None:
        super().__init__()

        if render_mode is not None and render_mode not in self.metadata["render_modes"]:
            raise ValueError(f"render_mode={render_mode!r} not in {self.metadata['render_modes']}")

        self.render_mode = render_mode
        self._max_steps = max_steps
        self._dt = dt

        # Observation: q(6) + ee(3) + obj(3) + tgt(3) + grasped(1)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(16,), dtype=np.float32)
        # Action: delta_q(6) + grasp_ctrl(1)
        self.action_space = spaces.Box(
            low=np.array([-1.0] * 6 + [-1.0], dtype=np.float32),
            high=np.array([1.0] * 6 + [1.0], dtype=np.float32),
        )

        self._world: f3d.World | None = None
        self._arm: f3r.Robot | None = None
        self._obj: Any = None  # Body handle for cube
        self._ee_link: Any = None  # Body handle for EE visual link
        self._tgt_marker: Any = None  # Body handle for target marker
        self._target_pos: np.ndarray = np.zeros(3)
        self._grasped: bool = False
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

        # ── Lazy world build ──────────────────────────────────────────────────
        if self._world is None:
            world = f3d.World(gravity=(0.0, 0.0, -9.81))
            world.add_ground()
            arm = f3r.load("ur5")
            world.add(arm)

            # Graspable cube (dynamic, placed on ground)
            obj = world.add_box(
                size=_OBJ_SIZE,
                position=(0.35, 0.0, 0.04),
                mass=0.3,
                restitution=0.0,
                friction=0.8,
                material=f3d.Material(color="blue"),
            )
            # Target location marker (static, on ground)
            tgt = world.add_sphere(
                radius=0.06,
                position=(-0.35, 0.0, 0.06),
                static=True,
                material=f3d.Material(color="green"),
            )
            world.set_camera(position=(1.2, -1.8, 1.0), target=(0.0, 0.0, 0.3))

            self._world = world
            self._arm = arm
            self._obj = obj
            self._tgt_marker = tgt

        # ── Episode reset ─────────────────────────────────────────────────────
        # Release any existing weld
        if self._grasped:
            self._world.release(self._obj)
        self._grasped = False

        # Reset arm
        self._arm.set_joints(_HOME_Q.copy())

        # Random object position (table top, 0.2-0.45m from base)
        r = float(self.np_random.uniform(0.25, 0.45))
        theta = float(self.np_random.uniform(-np.pi / 3, np.pi / 3))
        obj_pos = np.array([r * np.cos(theta), r * np.sin(theta), _OBJ_SIZE[2] / 2])
        self._world.teleport(self._obj, tuple(obj_pos))
        # Zero out object velocity
        for b in self._world._physics._bodies:
            if b.body_id == self._obj._id:
                from dataclasses import replace

                idx = self._world._physics._bodies.index(b)
                self._world._physics._bodies[idx] = replace(b, vel=np.zeros(3), omega=np.zeros(3))
                break

        # Random target (on ground, other side of arm)
        tr = float(self.np_random.uniform(0.25, 0.45))
        # Keep target away from object
        ta = float(self.np_random.uniform(np.pi * 2 / 3, np.pi * 4 / 3))
        tgt_pos = np.array([tr * np.cos(ta), tr * np.sin(ta), 0.06])
        self._world.teleport(self._tgt_marker, tuple(tgt_pos))
        self._target_pos = tgt_pos

        self._step_count = 0

        if self.render_mode == "human":
            self.render()

        obs = self._obs()
        info: dict[str, Any] = {
            "dist_ee_obj": self._dist_ee_obj(),
            "dist_obj_tgt": self._dist_obj_tgt(),
            "grasped": False,
        }
        return obs, info

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        assert self._arm is not None and self._world is not None

        action = np.asarray(action, dtype=float).clip(-1.0, 1.0)
        dq = action[:6] * ACTION_SCALE
        grasp_ctrl = float(action[6])

        # Apply joint delta
        new_q = np.clip(self._arm._q + dq, -JOINT_LIMIT, JOINT_LIMIT)
        self._arm.set_joints(new_q)
        self._world.step(dt=self._dt)
        self._step_count += 1

        # FK: get EE pose (use last link of arm)
        ee_pos, _ = self._arm.ee_pose()
        obj_pos = np.asarray(self._obj.position, dtype=float)
        tgt_pos = self._target_pos

        dist_ee_obj = float(np.linalg.norm(ee_pos - obj_pos))
        dist_obj_tgt = float(np.linalg.norm(obj_pos - tgt_pos))

        reward = 0.0
        grasp_event = False
        place_success = False

        # ── Grasp / release logic ─────────────────────────────────────────────
        if grasp_ctrl > 0.5 and not self._grasped:
            if dist_ee_obj < GRASP_DIST:
                # Weld to the last link body (EE proxy)
                ee_link_id = self._arm._body_ids[-1]
                ee_handle = _PhysicsBodyHandle(self._world._physics, ee_link_id)
                self._world.weld(self._obj, ee_handle)
                self._grasped = True
                grasp_event = True
                reward += GRASP_BONUS

        elif grasp_ctrl < -0.5 and self._grasped:
            self._world.release(self._obj)
            self._grasped = False

        # ── Reward ────────────────────────────────────────────────────────────
        if not self._grasped:
            reward += -0.3 * dist_ee_obj
        else:
            reward += -0.5 * dist_obj_tgt

        reward -= CTRL_PENALTY * float(np.sum(action[:6] ** 2))

        # ── Success check ─────────────────────────────────────────────────────
        if dist_obj_tgt < PLACE_DIST and not self._grasped and self._step_count > 5:
            reward += PLACE_BONUS
            place_success = True

        terminated = place_success
        truncated = self._step_count >= self._max_steps

        obs = np.concatenate(
            [
                new_q.astype(np.float32),
                ee_pos.astype(np.float32),
                obj_pos.astype(np.float32),
                tgt_pos.astype(np.float32),
                np.array([float(self._grasped)], dtype=np.float32),
            ]
        )

        info: dict[str, Any] = {
            "dist_ee_obj": dist_ee_obj,
            "dist_obj_tgt": dist_obj_tgt,
            "grasped": self._grasped,
            "success": place_success,
            "grasp_event": grasp_event,
        }

        if self.render_mode == "human":
            self.render()

        return obs, float(reward), terminated, truncated, info

    def render(self) -> np.ndarray | None:
        if self.render_mode is None or self._world is None:
            return None
        snap = self._world.snapshot()
        if self.render_mode == "rgb_array":
            if self._renderer is None:
                from forge3d.render.hq.renderer import HQRenderer

                self._renderer = HQRenderer(width=_W, height=_H, samples=2)
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

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _obs(self) -> np.ndarray:
        assert self._arm is not None
        ee_pos, _ = self._arm.ee_pose()
        obj_pos = np.asarray(self._obj.position, dtype=float)
        return np.concatenate(
            [
                self._arm._q.astype(np.float32),
                ee_pos.astype(np.float32),
                obj_pos.astype(np.float32),
                self._target_pos.astype(np.float32),
                np.array([float(self._grasped)], dtype=np.float32),
            ]
        )

    def _dist_ee_obj(self) -> float:
        ee_pos, _ = self._arm.ee_pose()
        return float(np.linalg.norm(ee_pos - self._obj.position))

    def _dist_obj_tgt(self) -> float:
        return float(np.linalg.norm(self._obj.position - self._target_pos))


# ── Internal helper ───────────────────────────────────────────────────────────


class _PhysicsBodyHandle:
    """Minimal Body-like handle for weld() using a raw body_id."""

    def __init__(self, physics_world: Any, body_id: int) -> None:
        self._pw = physics_world
        self._id = body_id

    def _state(self) -> Any:
        return next(b for b in self._pw._bodies if b.body_id == self._id)
