"""Backend abstraction: numpy ↔ jax.

Select via environment variable before process start:
    ENGINE_BACKEND=numpy  (default)
    ENGINE_BACKEND=jax

Engine code imports names from here:
    from forge3d.backend import xp, jit, vmap, set_at, new_prng_key, split_key, rand_uniform

xp   — numpy or jax.numpy module
jit  — jax.jit or no-op decorator
vmap — jax.vmap or loop-based fallback
"""

from __future__ import annotations

import functools
import os
from typing import Any

import numpy as _np

_BACKEND: str = os.environ.get("ENGINE_BACKEND", "numpy")

# Declare so static analysis sees these names regardless of which branch runs.
xp: Any
jit: Any
vmap: Any


def backend_name() -> str:
    """Return the active backend name ('numpy' or 'jax')."""
    return _BACKEND


# ── JAX backend ───────────────────────────────────────────────────────────────
if _BACKEND == "jax":
    import jax as _jax
    import jax.numpy as _jnp

    xp = _jnp
    jit = _jax.jit
    vmap = _jax.vmap

    def set_at(arr: Any, idx: Any, val: Any) -> Any:
        """Return arr with arr[idx] = val — JAX functional update."""
        return arr.at[idx].set(val)

    def new_prng_key(seed: int = 0) -> Any:
        return _jax.random.PRNGKey(seed)

    def split_key(key: Any, num: int = 2) -> Any:
        return _jax.random.split(key, num)

    def rand_uniform(
        key: Any,
        shape: tuple[int, ...],
        low: float = 0.0,
        high: float = 1.0,
    ) -> Any:
        return _jax.random.uniform(key, shape=shape, minval=low, maxval=high)

# ── NumPy backend ─────────────────────────────────────────────────────────────
elif _BACKEND == "numpy":
    xp = _np

    def jit(fn: Any, **_: Any) -> Any:  # type: ignore[misc]
        """No-op decorator: functions run eagerly under NumPy."""
        return fn

    def vmap(  # type: ignore[misc]
        fn: Any,
        in_axes: int = 0,
        out_axes: int = 0,
    ) -> Any:
        """Loop-based vmap fallback: maps fn over axis-0 of all inputs."""

        @functools.wraps(fn)
        def _wrapped(*args: Any) -> Any:
            n: int = args[0].shape[0]
            results = [fn(*[a[i] for a in args]) for i in range(n)]
            if not results:
                return _np.array([])
            if isinstance(results[0], tuple):
                return tuple(_np.stack([r[j] for r in results]) for j in range(len(results[0])))
            return _np.stack(results)

        return _wrapped

    def set_at(arr: Any, idx: Any, val: Any) -> Any:  # type: ignore[misc]
        """Return a copy of arr with arr[idx] replaced by val."""
        out = _np.array(arr, copy=True)
        out[idx] = val
        return out

    def new_prng_key(seed: int = 0) -> Any:  # type: ignore[misc]
        """Create a uint32[2] key compatible with JAX PRNG conventions."""
        return _np.array([seed, 0], dtype=_np.uint32)

    def split_key(key: Any, num: int = 2) -> Any:  # type: ignore[misc]
        """Split key into num independent keys (deterministic, sequential seeds)."""
        return _np.stack(
            [_np.array([int(key[0]) + i, int(key[1])], dtype=_np.uint32) for i in range(num)]
        )

    def rand_uniform(  # type: ignore[misc]
        key: Any,
        shape: tuple[int, ...],
        low: float = 0.0,
        high: float = 1.0,
    ) -> Any:
        rng = _np.random.default_rng(int(key[0]))
        return rng.uniform(low=low, high=high, size=shape)

else:
    raise ValueError(
        f"Unknown ENGINE_BACKEND={_BACKEND!r}. Set the environment variable to 'numpy' or 'jax'."
    )
