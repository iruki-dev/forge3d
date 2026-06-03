"""Throughput benchmark: NumPy single env vs JAX JIT vs JAX vmap.

Run::

    python apps/robot_rl/training/benchmark_jax.py

Expected results (CPU-only, ~8 core)::

    NumPy  single env :   ~600 steps/s
    JAX    JIT single :  ~8000 steps/s   (~13×)
    JAX    vmap B=256 : ~300000 steps/s  (~500×)

P11 gate (G2): JAX vmap(B=256) total env-steps/s ≥ NumPy × 100.
"""

from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("JAX_ENABLE_X64", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

import jax
import jax.numpy as jnp

from forge3d.sim.jax_batch import batch_reach_reset, batch_reach_step, reach_step_jax

# ── NumPy baseline ────────────────────────────────────────────────────────────


def _benchmark_numpy(n_steps: int = 500) -> float:
    """Run N steps of the NumPy-based ReachEnv; return steps/sec."""
    from apps.robot_rl.envs.reach_env import ReachEnv

    env = ReachEnv()
    env.reset(seed=0)
    t0 = time.perf_counter()
    for _ in range(n_steps):
        env.step(env.action_space.sample())
    elapsed = time.perf_counter() - t0
    env.close()
    return n_steps / elapsed


# ── JAX JIT single env ────────────────────────────────────────────────────────


def _benchmark_jax_single(n_steps: int = 2000) -> float:
    """JIT-compiled single-env step; return steps/sec (excludes warmup)."""
    key = jax.random.PRNGKey(0)
    q, target, _ = batch_reach_reset(key, 1)
    q, target = q[0], target[0]
    action = jnp.zeros(6, dtype=jnp.float64)

    # Warmup (JIT compilation)
    out = reach_step_jax(q, target, action)
    jax.block_until_ready(out)

    t0 = time.perf_counter()
    for _ in range(n_steps):
        q, _, _, _ = reach_step_jax(q, target, action)
        jax.block_until_ready(q)
    return n_steps / (time.perf_counter() - t0)


# ── JAX vmap batch ────────────────────────────────────────────────────────────


def _benchmark_jax_vmap(batch_size: int = 256, n_steps: int = 500) -> float:
    """vmap batch step; return total env-steps/sec (B * steps/elapsed)."""
    key = jax.random.PRNGKey(1)
    q, target, _ = batch_reach_reset(key, batch_size)
    action = jnp.zeros((batch_size, 6), dtype=jnp.float64)

    # Warmup (JIT compilation + vmap trace)
    out = batch_reach_step(q, target, action)
    jax.block_until_ready(out)

    t0 = time.perf_counter()
    for _ in range(n_steps):
        q, _, _, _ = batch_reach_step(q, target, action)
        jax.block_until_ready(q)
    elapsed = time.perf_counter() - t0
    return (n_steps * batch_size) / elapsed


# ── Main ──────────────────────────────────────────────────────────────────────


def run_benchmark(batch_size: int = 256) -> dict[str, float]:
    """Run all benchmarks and print a comparison table."""
    print("=== P11 Throughput Benchmark ===\n")

    print("Benchmarking NumPy single env …", end=" ", flush=True)
    numpy_sps = _benchmark_numpy()
    print(f"{numpy_sps:>10,.0f} steps/s")

    print("Benchmarking JAX JIT single  …", end=" ", flush=True)
    jit_sps = _benchmark_jax_single()
    print(f"{jit_sps:>10,.0f} steps/s   ({jit_sps/numpy_sps:.1f}×)")

    print(f"Benchmarking JAX vmap B={batch_size:<3d} …", end=" ", flush=True)
    vmap_sps = _benchmark_jax_vmap(batch_size)
    print(f"{vmap_sps:>10,.0f} steps/s   ({vmap_sps/numpy_sps:.1f}×)")

    speedup = vmap_sps / numpy_sps
    status = "PASS ✓" if speedup >= 100 else f"FAIL (need ≥100×, got {speedup:.1f}×)"
    print(f"\nG2 gate: JAX vmap / NumPy = {speedup:.1f}× → {status}")

    return {"numpy_sps": numpy_sps, "jit_sps": jit_sps, "vmap_sps": vmap_sps}


if __name__ == "__main__":
    results = run_benchmark(batch_size=256)
