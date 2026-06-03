"""JAX JIT+vmap batch physics for the UR5 reaching task.

Provides a functional, pure-JAX interface for high-throughput RL training:

  from forge3d.sim.jax_batch import batch_reach_step, batch_reach_reset

  q, target, obs = batch_reach_reset(key, n_envs=256)
  new_q, obs, reward, done = batch_reach_step(q, target, action)

Key design decisions
--------------------
* JAX_ENABLE_X64=1  — float64 throughout so NumPy FK results match to ~1e-16.
* UR5 DH transforms are precomputed at import time (static constants).
* Python ``for i in range(6)`` inside @jax.jit is unrolled by the tracer.
* All public functions are module-level (not methods) → compatible with jax.grad.
* Physics core (forge3d.sim.world) is NOT imported — pure JAX, no NumPy world.
"""

from __future__ import annotations

import os

os.environ.setdefault("JAX_ENABLE_X64", "1")

import jax
import jax.numpy as jnp
import numpy as np

# Re-enable x64 even if jax was already imported without it
jax.config.update("jax_enable_x64", True)

# ── Precompute UR5 static transforms (one-time at import) ─────────────────────


def _precompute_ur5_trees() -> tuple[np.ndarray, np.ndarray]:
    """Extract (R_tree, p_tree) per link from the UR5 DH model."""
    from forge3d.math.se3 import unskew
    from forge3d.robot.presets import make_ur5

    robot = make_ur5()
    model = robot._model
    n = model.n_links  # 6
    R_trees = np.zeros((n, 3, 3), dtype=np.float64)
    p_trees = np.zeros((n, 3), dtype=np.float64)
    for i in range(n):
        X_t = np.asarray(model.X_tree[i], dtype=np.float64)
        E = X_t[:3, :3]
        R_tree = E.T  # Featherstone passive → active rotation
        p_tree = unskew(-(R_tree @ X_t[3:, :3]))
        R_trees[i] = R_tree
        p_trees[i] = p_tree
    return R_trees, p_trees


_UR5_R_TREES_NP, _UR5_P_TREES_NP = _precompute_ur5_trees()
_UR5_R_TREES: jnp.ndarray = jnp.array(_UR5_R_TREES_NP)  # (6, 3, 3) f64 constant
_UR5_P_TREES: jnp.ndarray = jnp.array(_UR5_P_TREES_NP)  # (6, 3) f64 constant

_HOME_Q: jnp.ndarray = jnp.array(
    [0.0, -jnp.pi / 2, jnp.pi / 2, -jnp.pi / 2, -jnp.pi / 2, 0.0],
    dtype=jnp.float64,
)

# ── JAX-compiled FK ───────────────────────────────────────────────────────────


@jax.jit
def ur5_fk_ee(q: jnp.ndarray) -> jnp.ndarray:
    """UR5 end-effector position (3,) from joint angles (6,).

    Numerically equivalent to::

        forward_kinematics(model, q)[0]  # NumPy

    with float64 precision.  All UR5 joints are revolute about z-axis.

    Update rule (per link, serial chain):
        p ← p + R @ P_tree[i]      # p uses parent R before R is updated
        R ← R @ R_tree[i] @ Rz(q[i])
    """
    R = jnp.eye(3, dtype=jnp.float64)
    p = jnp.zeros(3, dtype=jnp.float64)
    for i in range(6):  # Python loop → unrolled by JAX tracer
        p = p + R @ _UR5_P_TREES[i]
        c = jnp.cos(q[i])
        s = jnp.sin(q[i])
        z = jnp.zeros_like(c)
        # Rz(q[i]) — revolute about z-axis
        Rz = jnp.stack(
            [
                jnp.stack([c, -s, z]),
                jnp.stack([s, c, z]),
                jnp.array([0.0, 0.0, 1.0], dtype=jnp.float64),
            ]
        )
        R = R @ _UR5_R_TREES[i] @ Rz
    return p


#: Batch FK: (B, 6) → (B, 3). JIT-compiled vmap.
ur5_fk_ee_batch: object = jax.jit(jax.vmap(ur5_fk_ee, in_axes=0))

# ── Reaching step (single environment) ───────────────────────────────────────

_Q_LIMIT: float = float(jnp.pi)
_DELTA_SCALE: float = 0.05  # action scaling — same as NumPy ReachEnv
_SUCCESS_DIST: float = 0.05  # success threshold (m)
_SUCCESS_BONUS: float = 10.0


@jax.jit
def reach_step_jax(
    q: jnp.ndarray,
    target: jnp.ndarray,
    action: jnp.ndarray,
) -> tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray, jnp.ndarray]:
    """One reaching-task step (single environment).

    Parameters
    ----------
    q      : (6,) current joint angles
    target : (3,) target EE position in world frame
    action : (6,) delta-q action, nominally in [-1, 1]

    Returns
    -------
    new_q      : (6,)  updated joint angles
    obs        : (12,) [q, ee_pos, target]
    reward     : ()    -dist + success_bonus (if dist < threshold)
    terminated : ()    bool scalar
    """
    new_q = jnp.clip(q + action * _DELTA_SCALE, -_Q_LIMIT, _Q_LIMIT)
    ee_pos = ur5_fk_ee(new_q)
    dist = jnp.linalg.norm(ee_pos - target)
    reward = -dist + jnp.where(dist < _SUCCESS_DIST, _SUCCESS_BONUS, 0.0)
    obs = jnp.concatenate([new_q, ee_pos, target])
    terminated = dist < _SUCCESS_DIST
    return new_q, obs, reward, terminated


#: Batch step: (B,6), (B,3), (B,6) → (B,6), (B,12), (B,), (B,). JIT+vmap.
batch_reach_step: object = jax.jit(jax.vmap(reach_step_jax, in_axes=(0, 0, 0)))

# ── Batch reset ───────────────────────────────────────────────────────────────


def batch_reach_reset(
    key: jnp.ndarray,
    n_envs: int,
) -> tuple[jnp.ndarray, jnp.ndarray, jnp.ndarray]:
    """Reset N environments with random targets.

    Parameters
    ----------
    key    : JAX RNG key
    n_envs : number of parallel environments

    Returns
    -------
    q_batch      : (n_envs, 6)  joint angles near home config
    target_batch : (n_envs, 3)  random reachable targets
    obs_batch    : (n_envs, 12) initial observations
    """
    k_q, k_r, k_theta, k_phi = jax.random.split(key, 4)

    # Joint angles: home ± 0.1 rad noise
    q_batch = jnp.tile(_HOME_Q, (n_envs, 1)) + jax.random.uniform(
        k_q, (n_envs, 6), dtype=jnp.float64, minval=-0.1, maxval=0.1
    )

    # Random spherical targets in reachable workspace
    r = jax.random.uniform(k_r, (n_envs,), dtype=jnp.float64, minval=0.3, maxval=0.65)
    theta = jax.random.uniform(
        k_theta, (n_envs,), dtype=jnp.float64, minval=-jnp.pi / 3, maxval=jnp.pi / 3
    )
    phi = jax.random.uniform(
        k_phi, (n_envs,), dtype=jnp.float64, minval=jnp.pi / 6, maxval=jnp.pi / 2
    )
    target_batch = jnp.stack(
        [
            r * jnp.sin(phi) * jnp.cos(theta),
            r * jnp.sin(phi) * jnp.sin(theta),
            r * jnp.cos(phi),
        ],
        axis=1,
    )

    # Initial observation
    ee_batch = ur5_fk_ee_batch(q_batch)  # type: ignore[operator]
    obs_batch = jnp.concatenate([q_batch, ee_batch, target_batch], axis=1)
    return q_batch, target_batch, obs_batch
