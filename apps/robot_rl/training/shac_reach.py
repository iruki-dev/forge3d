"""SHAC (Short Horizon Actor-Critic) for the UR5 reaching task.

Key idea
--------
The UR5 FK uses only differentiable trig functions, so jax.grad flows through
H physics steps analytically — no variance from stochastic gradient estimates.

Training loop
-------------
1. Actor update (SHAC):
   - Roll out H=16 steps with current deterministic policy.
   - Loss = -(sum of rewards + V(terminal state)).
   - jax.grad(loss, wrt=actor_params) via backprop through FK.

2. Critic update (TD):
   - Collect 1-step targets: r + γ * V(s').
   - Minimise MSE between V(s) and target.

Run::

    python apps/robot_rl/training/shac_reach.py

Produces: ``shac_training_curve.png`` (loss + reward curves).
"""

from __future__ import annotations

import functools
import os

os.environ.setdefault("JAX_ENABLE_X64", "1")

import time
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np
import optax

from forge3d.sim.jax_batch import (
    batch_reach_reset,
    reach_step_jax,
    ur5_fk_ee,
)

# ── Dimensions ────────────────────────────────────────────────────────────────

OBS_DIM = 12   # q(6) + ee_pos(3) + target(3)
ACT_DIM = 6    # delta-q actions

# ── MLP utilities (pure JAX, no external NN framework) ───────────────────────

Params = list[dict[str, jnp.ndarray]]


def init_mlp(key: jnp.ndarray, layer_sizes: list[int]) -> Params:
    """He-initialised MLP: list of {'W': (in, out), 'b': (out,)} dicts."""
    params: Params = []
    for i in range(len(layer_sizes) - 1):
        k, key = jax.random.split(key)
        fan_in = layer_sizes[i]
        scale = jnp.sqrt(2.0 / fan_in)
        W = jax.random.normal(k, (layer_sizes[i], layer_sizes[i + 1]), dtype=jnp.float64) * scale
        b = jnp.zeros(layer_sizes[i + 1], dtype=jnp.float64)
        params.append({"W": W, "b": b})
    return params


def mlp_apply(params: Params, x: jnp.ndarray) -> jnp.ndarray:
    """Forward pass: tanh activations on hidden layers, linear output."""
    for layer in params[:-1]:
        x = jnp.tanh(x @ layer["W"] + layer["b"])
    return x @ params[-1]["W"] + params[-1]["b"]


def init_shac(key: jnp.ndarray) -> dict[str, Params]:
    """Initialise actor + critic parameters."""
    k1, k2 = jax.random.split(key)
    actor = init_mlp(k1, [OBS_DIM, 64, 64, ACT_DIM])
    critic = init_mlp(k2, [OBS_DIM, 64, 64, 1])
    return {"actor": actor, "critic": critic}


# ── SHAC actor loss ───────────────────────────────────────────────────────────


def actor_loss_fn(
    actor_params: Params,
    critic_params: Params,
    q_batch: jnp.ndarray,
    target_batch: jnp.ndarray,
    key: jnp.ndarray,
    H: int = 16,
) -> jnp.ndarray:
    """SHAC actor loss: negative mean return over H differentiable steps.

    Gradient flows through UR5 FK (trig → smooth) via jax.lax.scan.
    critic_params is used read-only (stop_gradient applied internally).

    Parameters
    ----------
    actor_params  : actor MLP params
    critic_params : critic MLP params (detached from gradient)
    q_batch       : (B, 6) initial joint angles
    target_batch  : (B, 3) target positions
    key           : JAX RNG key
    H             : short horizon length

    Returns
    -------
    loss : scalar negative expected return (minimise → maximise reward)
    """

    def single_env(q0: jnp.ndarray, target: jnp.ndarray) -> jnp.ndarray:
        def step_fn(
            carry: tuple[jnp.ndarray, jnp.ndarray], _: Any
        ) -> tuple[tuple[jnp.ndarray, jnp.ndarray], jnp.ndarray]:
            q, t = carry
            obs = jnp.concatenate([q, ur5_fk_ee(q), t])
            action = jnp.tanh(mlp_apply(actor_params, obs))  # bounded ∈ (-1, 1)
            new_q, _, reward, _ = reach_step_jax(q, t, action)
            return (new_q, t), reward

        (q_final, _), rewards = jax.lax.scan(step_fn, (q0, target), None, length=H)

        # Terminal value: stop_gradient so critic loss is decoupled
        obs_final = jnp.concatenate([q_final, ur5_fk_ee(q_final), target])
        v_terminal = jax.lax.stop_gradient(mlp_apply(critic_params, obs_final)[0])
        return -(jnp.sum(rewards) + v_terminal)

    losses = jax.vmap(single_env)(q_batch, target_batch)
    return jnp.mean(losses)


# ── Critic loss ───────────────────────────────────────────────────────────────


def critic_loss_fn(
    critic_params: Params,
    actor_params: Params,
    q_batch: jnp.ndarray,
    target_batch: jnp.ndarray,
    gamma: float = 0.99,
    H: int = 16,
) -> jnp.ndarray:
    """Critic TD loss: MSE between V(s) and 1-step bootstrapped targets."""

    def single_env(q0: jnp.ndarray, target: jnp.ndarray) -> jnp.ndarray:
        obs = jnp.concatenate([q0, ur5_fk_ee(q0), target])
        v_pred = mlp_apply(critic_params, obs)[0]

        # 1-step target
        action = jax.lax.stop_gradient(
            jnp.tanh(mlp_apply(actor_params, obs))
        )
        new_q, _, reward, _ = reach_step_jax(q0, target, action)
        obs_next = jax.lax.stop_gradient(
            jnp.concatenate([new_q, ur5_fk_ee(new_q), target])
        )
        v_next = jax.lax.stop_gradient(mlp_apply(critic_params, obs_next)[0])
        td_target = reward + gamma * v_next
        return (v_pred - td_target) ** 2

    return jnp.mean(jax.vmap(single_env)(q_batch, target_batch))


# ── Training loop ─────────────────────────────────────────────────────────────


def train(
    total_steps: int = 50_000,
    n_envs: int = 64,
    H: int = 16,
    lr: float = 3e-4,
    seed: int = 42,
    out_dir: str = "apps/robot_rl/outputs",
) -> dict[str, Any]:
    """Run SHAC training and return a results dict.

    Parameters
    ----------
    total_steps : total environment steps to run
    n_envs      : parallel environments (vmap batch size)
    H           : SHAC short horizon
    lr          : Adam learning rate
    seed        : RNG seed
    out_dir     : directory for output artefacts

    Returns
    -------
    dict with 'actor_loss', 'critic_loss', 'mean_reward' history arrays
    """
    os.makedirs(out_dir, exist_ok=True)
    key = jax.random.PRNGKey(seed)
    key, k_init, k_reset = jax.random.split(key, 3)

    params = init_shac(k_init)
    actor_opt = optax.adam(lr)
    critic_opt = optax.adam(lr)
    actor_opt_state = actor_opt.init(params["actor"])
    critic_opt_state = critic_opt.init(params["critic"])

    # JIT-compile gradient functions (H must be static for jax.lax.scan)
    _actor_loss_h = functools.partial(actor_loss_fn, H=H)
    actor_val_grad = jax.jit(jax.value_and_grad(_actor_loss_h, argnums=0))
    critic_val_grad = jax.jit(jax.value_and_grad(critic_loss_fn, argnums=0))

    q_batch, target_batch, _ = batch_reach_reset(k_reset, n_envs)

    n_iters = total_steps // (n_envs * H)
    history: dict[str, list[float]] = {
        "actor_loss": [],
        "critic_loss": [],
        "mean_reward": [],
    }

    print(
        f"SHAC: {n_envs} envs × H={H} × {n_iters} iters = "
        f"{n_envs * H * n_iters:,} total env-steps"
    )
    t0 = time.perf_counter()

    for iteration in range(n_iters):
        key, k_a, k_reset_maybe = jax.random.split(key, 3)

        # Actor update (analytic gradient through FK)
        a_loss, a_grads = actor_val_grad(
            params["actor"], params["critic"], q_batch, target_batch, k_a
        )
        a_updates, actor_opt_state = actor_opt.update(a_grads, actor_opt_state)
        params["actor"] = optax.apply_updates(params["actor"], a_updates)

        # Critic update (TD)
        c_loss, c_grads = critic_val_grad(
            params["critic"], params["actor"], q_batch, target_batch
        )
        c_updates, critic_opt_state = critic_opt.update(c_grads, critic_opt_state)
        params["critic"] = optax.apply_updates(params["critic"], c_updates)

        # Compute mean reward for logging
        def _get_reward(q: jnp.ndarray, target: jnp.ndarray) -> jnp.ndarray:
            obs = jnp.concatenate([q, ur5_fk_ee(q), target])
            action = jnp.tanh(mlp_apply(params["actor"], obs))
            _, _, reward, _ = reach_step_jax(q, target, action)
            return reward

        mean_rew = float(jnp.mean(jax.vmap(_get_reward)(q_batch, target_batch)))

        history["actor_loss"].append(float(a_loss))
        history["critic_loss"].append(float(c_loss))
        history["mean_reward"].append(mean_rew)

        # Refresh environments periodically
        if (iteration + 1) % 20 == 0:
            q_batch, target_batch, _ = batch_reach_reset(k_reset_maybe, n_envs)

        if (iteration + 1) % max(1, n_iters // 5) == 0:
            elapsed = time.perf_counter() - t0
            env_steps = (iteration + 1) * n_envs * H
            sps = env_steps / elapsed
            print(
                f"  iter {iteration+1:4d}/{n_iters}  "
                f"a_loss={float(a_loss):.4f}  c_loss={float(c_loss):.4f}  "
                f"rew={mean_rew:.4f}  {sps:,.0f} env-steps/s"
            )

    elapsed = time.perf_counter() - t0
    total_env_steps = n_iters * n_envs * H
    print(
        f"\nSHAC done: {total_env_steps:,} steps in {elapsed:.1f}s "
        f"({total_env_steps / elapsed:,.0f} env-steps/s)"
    )

    # Save training curve
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 3, figsize=(12, 4))
        axes[0].plot(history["actor_loss"])
        axes[0].set_title("Actor Loss (SHAC)")
        axes[0].set_xlabel("Iteration")
        axes[1].plot(history["critic_loss"])
        axes[1].set_title("Critic Loss (TD)")
        axes[1].set_xlabel("Iteration")
        axes[2].plot(history["mean_reward"])
        axes[2].set_title("Mean Reward")
        axes[2].set_xlabel("Iteration")
        plt.tight_layout()
        out_png = os.path.join(out_dir, "shac_training_curve.png")
        plt.savefig(out_png, dpi=100)
        plt.close()
        print(f"Saved: {out_png}")
    except ImportError:
        pass

    return {
        "actor_loss": np.array(history["actor_loss"]),
        "critic_loss": np.array(history["critic_loss"]),
        "mean_reward": np.array(history["mean_reward"]),
        "params": params,
    }


if __name__ == "__main__":
    train(total_steps=50_000, n_envs=64, H=16)
