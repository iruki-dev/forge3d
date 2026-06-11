"""P11 gate tests: JAX JIT+vmap batch physics + SHAC gradient flow.

Run separately (JAX+torch fork segfault with combined suite)::

    pytest tests/test_p11_jax.py -q
"""

from __future__ import annotations

import functools
import math
import os
import time

os.environ["JAX_ENABLE_X64"] = "1"

import jax
import jax.numpy as jnp
import numpy as np
import pytest

jax.config.update("jax_enable_x64", True)

# ── G1: FK correctness ────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def ur5_model():
    from forge3d.robot.presets import make_ur5

    return make_ur5()._model


@pytest.mark.parametrize(
    "q",
    [
        [0.0, -np.pi / 2, np.pi / 2, -np.pi / 2, -np.pi / 2, 0.0],
        [0.5, -1.2, 1.8, -1.0, -1.5, 0.3],
        [0.1, -0.8, 1.2, -0.5, -1.0, 0.2],
        [-0.3, -1.0, 1.5, -0.8, -1.3, 0.1],
    ],
)
def test_jax_fk_matches_numpy(ur5_model, q):
    """G1: JAX FK must match NumPy FK within 1e-5 (actual: ~1e-16 with x64)."""
    from forge3d.model.kinematics import forward_kinematics
    from forge3d.sim.jax_batch import ur5_fk_ee

    q_np = np.array(q, dtype=np.float64)
    np_pos, _ = forward_kinematics(ur5_model, q_np)
    jax_pos = np.array(ur5_fk_ee(jnp.array(q_np)))
    np.testing.assert_allclose(jax_pos, np_pos, atol=1e-5)


def test_jax_fk_batch_shape():
    """Batch FK (B, 6) → (B, 3) with correct values."""
    from forge3d.sim.jax_batch import ur5_fk_ee, ur5_fk_ee_batch

    B = 32
    q_batch = jnp.zeros((B, 6), dtype=jnp.float64)
    ee_batch = ur5_fk_ee_batch(q_batch)
    assert ee_batch.shape == (B, 3)
    # All identical to single FK at q=0
    single = ur5_fk_ee(jnp.zeros(6, dtype=jnp.float64))
    np.testing.assert_allclose(np.array(ee_batch[0]), np.array(single), atol=1e-12)
    np.testing.assert_allclose(np.array(ee_batch[-1]), np.array(single), atol=1e-12)


# ── Single-env step shapes / values ──────────────────────────────────────────


def test_reach_step_shapes():
    """reach_step_jax output shapes and dtype."""
    from forge3d.sim.jax_batch import reach_step_jax

    q = jnp.zeros(6, dtype=jnp.float64)
    target = jnp.array([0.3, 0.1, 0.4], dtype=jnp.float64)
    action = jnp.zeros(6, dtype=jnp.float64)
    new_q, obs, reward, done = reach_step_jax(q, target, action)
    assert new_q.shape == (6,)
    assert obs.shape == (12,)
    assert reward.shape == ()
    assert done.shape == ()
    assert obs.dtype == jnp.float64


def test_reach_step_obs_consistency():
    """obs[0:6] must match new_q; obs[6:9] must match FK(new_q)."""
    from forge3d.sim.jax_batch import reach_step_jax, ur5_fk_ee

    q = jnp.array([0.1, -0.8, 1.2, -0.5, -1.0, 0.2], dtype=jnp.float64)
    target = jnp.array([-0.3, 0.2, 0.5], dtype=jnp.float64)
    action = jnp.ones(6, dtype=jnp.float64) * 0.3
    new_q, obs, _, _ = reach_step_jax(q, target, action)
    np.testing.assert_allclose(np.array(obs[:6]), np.array(new_q), atol=1e-12)
    expected_ee = ur5_fk_ee(new_q)
    np.testing.assert_allclose(np.array(obs[6:9]), np.array(expected_ee), atol=1e-12)


def test_reach_step_success_bonus():
    """Step at goal position must yield terminated=True and bonus reward."""
    from forge3d.sim.jax_batch import _SUCCESS_BONUS, reach_step_jax, ur5_fk_ee

    q_home = jnp.array([0.0, -np.pi / 2, np.pi / 2, -np.pi / 2, -np.pi / 2, 0.0], dtype=jnp.float64)
    ee_at_home = ur5_fk_ee(q_home)
    target = ee_at_home  # target IS the EE position → dist = 0
    action = jnp.zeros(6, dtype=jnp.float64)
    _, _, reward, terminated = reach_step_jax(q_home, target, action)
    assert bool(terminated), "Should be terminated when EE == target"
    assert float(reward) > _SUCCESS_BONUS * 0.5


# ── Batch step shapes ─────────────────────────────────────────────────────────


def test_batch_reach_step_shapes():
    """batch_reach_step output shapes."""
    from forge3d.sim.jax_batch import batch_reach_step

    B = 64
    q = jnp.zeros((B, 6), dtype=jnp.float64)
    target = jnp.tile(jnp.array([0.3, 0.1, 0.4]), (B, 1))
    action = jnp.zeros((B, 6), dtype=jnp.float64)
    new_q, obs, reward, done = batch_reach_step(q, target, action)
    assert new_q.shape == (B, 6)
    assert obs.shape == (B, 12)
    assert reward.shape == (B,)
    assert done.shape == (B,)


def test_batch_reach_reset():
    """batch_reach_reset shapes and obs consistency."""
    from forge3d.sim.jax_batch import batch_reach_reset, ur5_fk_ee

    key = jax.random.PRNGKey(7)
    n = 16
    q, tgt, obs = batch_reach_reset(key, n)
    assert q.shape == (n, 6)
    assert tgt.shape == (n, 3)
    assert obs.shape == (n, 12)
    # Verify obs[0:6] == q and obs[6:9] == FK(q)
    for i in range(n):
        np.testing.assert_allclose(np.array(obs[i, :6]), np.array(q[i]), atol=1e-12)
        ee = ur5_fk_ee(q[i])
        np.testing.assert_allclose(np.array(obs[i, 6:9]), np.array(ee), atol=1e-12)


# ── G3: SHAC gradient flow ────────────────────────────────────────────────────


def test_shac_gradient_flows():
    """G3: SHAC actor gradient norm must be > 0 (FK is differentiable)."""
    from apps.robot_rl.training.shac_reach import actor_loss_fn, init_shac

    from forge3d.sim.jax_batch import batch_reach_reset

    key = jax.random.PRNGKey(42)
    k1, k2 = jax.random.split(key)
    params = init_shac(k1)
    q_batch, target_batch, _ = batch_reach_reset(k2, 8)

    loss, grads = jax.value_and_grad(actor_loss_fn, argnums=0)(
        params["actor"], params["critic"], q_batch, target_batch, key, 4
    )
    # grad_norm over all actor weights
    grad_norm = math.sqrt(sum(float(jnp.sum(g["W"] ** 2) + jnp.sum(g["b"] ** 2)) for g in grads))
    assert math.isfinite(float(loss)), f"actor loss is not finite: {loss}"
    assert grad_norm > 0.0, f"Gradient is zero! norm={grad_norm}"


def test_shac_loss_decreases():
    """SHAC actor loss should decrease after a few gradient steps."""
    import optax
    from apps.robot_rl.training.shac_reach import actor_loss_fn, init_shac

    from forge3d.sim.jax_batch import batch_reach_reset

    key = jax.random.PRNGKey(99)
    k1, k2 = jax.random.split(key)
    params = init_shac(k1)
    q_batch, target_batch, _ = batch_reach_reset(k2, 16)

    optimizer = optax.adam(3e-4)
    opt_state = optimizer.init(params["actor"])
    # H must be a Python constant (not traced) for jax.lax.scan
    _loss_h4 = functools.partial(actor_loss_fn, H=4)
    grad_fn = jax.jit(jax.value_and_grad(_loss_h4, argnums=0))

    losses = []
    for _ in range(20):
        k, key = jax.random.split(key)
        loss, grads = grad_fn(params["actor"], params["critic"], q_batch, target_batch, k)
        updates, opt_state = optimizer.update(grads, opt_state)
        params["actor"] = optax.apply_updates(params["actor"], updates)
        losses.append(float(loss))

    # Loss must improve at some point (not necessarily monotone, but final < initial)
    assert losses[-1] < losses[0], (
        f"Actor loss did not decrease: initial={losses[0]:.4f}, final={losses[-1]:.4f}"
    )


# ── G2: Throughput ─────────────────────────────────────────────────────────────


def test_jax_throughput_vs_numpy():
    """G2: JAX vmap(B=256) must be ≥100× faster than NumPy single env."""
    from apps.robot_rl.envs.reach_env import ReachEnv

    from forge3d.sim.jax_batch import batch_reach_reset, batch_reach_step

    # NumPy baseline
    env = ReachEnv()
    env.reset(seed=0)
    n_np = 200
    t0 = time.perf_counter()
    for _ in range(n_np):
        env.step(env.action_space.sample())
    np_sps = n_np / (time.perf_counter() - t0)
    env.close()

    # JAX vmap
    B = 256
    key = jax.random.PRNGKey(0)
    q, tgt, _ = batch_reach_reset(key, B)
    action = jnp.zeros((B, 6), dtype=jnp.float64)

    # Warmup (JIT compilation)
    out = batch_reach_step(q, tgt, action)
    jax.block_until_ready(out)

    n_jax = 100
    t1 = time.perf_counter()
    for _ in range(n_jax):
        q, _, _, _ = batch_reach_step(q, tgt, action)
        jax.block_until_ready(q)
    jax_sps = (n_jax * B) / (time.perf_counter() - t1)

    speedup = jax_sps / np_sps
    print(f"\nNumPy: {np_sps:,.0f} sps | JAX vmap B={B}: {jax_sps:,.0f} sps | {speedup:.1f}×")
    assert speedup >= 100, f"G2: expected ≥100× speedup, got {speedup:.1f}×"
