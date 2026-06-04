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

# ── Rust 네이티브 확장 (P25) ──────────────────────────────────────────────────
# USE_RUST_CORE=0 → 강제 Python 폴백
# USE_RUST_CORE=1 → 강제 Rust (빌드 실패 시 ImportError)
# (기본) → Rust 임포트 성공 시 활성화, 실패 시 Python 폴백

_RUST_ENV = os.environ.get("USE_RUST_CORE", "auto").lower()
_rust_core: Any = None

if _RUST_ENV != "0":
    try:
        from forge3d import _core as _rust_core_module

        _rust_core = _rust_core_module
    except ImportError as _exc:
        if _RUST_ENV == "1":
            raise ImportError(
                "USE_RUST_CORE=1 이지만 forge3d._core 빌드를 찾을 수 없습니다. "
                "maturin build 후 재설치하세요."
            ) from _exc
        # auto: Python 폴백으로 조용히 계속

USE_RUST_CORE: bool = _rust_core is not None


def rust_core() -> Any:
    """Rust 네이티브 확장 모듈 반환. USE_RUST_CORE=False면 None."""
    return _rust_core
