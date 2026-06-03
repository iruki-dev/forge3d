"""Backend abstraction smoke tests — runs for every available backend."""

from __future__ import annotations

import numpy as np
import pytest

# All tests in this file use the `backend` fixture from conftest.py,
# which sets ENGINE_BACKEND and reloads forge3d.backend.


def _bk():
    """Return the (possibly just-reloaded) backend module."""
    import forge3d.backend as bk

    return bk


class TestXpArrayOps:
    def test_zeros(self, backend: str) -> None:
        xp = _bk().xp
        arr = xp.zeros(3)
        assert arr.shape == (3,)

    def test_ones(self, backend: str) -> None:
        xp = _bk().xp
        arr = xp.ones((2, 3))
        assert arr.shape == (2, 3)

    def test_array_round_trip(self, backend: str) -> None:
        xp = _bk().xp
        data = [1.0, 2.0, 3.0]
        arr = xp.array(data)
        result = np.array(arr)
        np.testing.assert_allclose(result, data)


class TestSetAt:
    def test_no_inplace_mutation(self, backend: str) -> None:
        """set_at must not mutate the original array."""
        xp = _bk().xp
        bk = _bk()
        original = xp.zeros(4)
        updated = bk.set_at(original, 2, 99.0)
        assert float(updated[2]) == pytest.approx(99.0)
        assert float(original[2]) == pytest.approx(0.0)

    def test_value_written(self, backend: str) -> None:
        xp = _bk().xp
        bk = _bk()
        arr = xp.ones(5)
        out = bk.set_at(arr, 0, -7.5)
        assert float(out[0]) == pytest.approx(-7.5)


class TestPRNG:
    def test_new_prng_key_shape(self, backend: str) -> None:
        bk = _bk()
        key = bk.new_prng_key(seed=42)
        assert key is not None

    def test_split_key_count(self, backend: str) -> None:
        bk = _bk()
        key = bk.new_prng_key(0)
        parts = bk.split_key(key, num=3)
        assert len(parts) == 3

    def test_rand_uniform_range(self, backend: str) -> None:
        bk = _bk()
        key = bk.new_prng_key(0)
        samples = bk.rand_uniform(key, shape=(1000,), low=0.0, high=1.0)
        arr = np.array(samples)
        assert arr.min() >= 0.0
        assert arr.max() <= 1.0


class TestJit:
    def test_jit_preserves_output(self, backend: str) -> None:
        bk = _bk()
        xp = bk.xp

        @bk.jit
        def add_one(x):
            return x + 1.0

        result = add_one(xp.array(3.0))
        assert float(result) == pytest.approx(4.0)


class TestVmap:
    def test_vmap_basic(self, backend: str) -> None:
        bk = _bk()
        xp = bk.xp

        def square(x):
            return x * x

        batch = xp.array([1.0, 2.0, 3.0, 4.0])
        result = bk.vmap(square)(batch)
        expected = np.array([1.0, 4.0, 9.0, 16.0])
        np.testing.assert_allclose(np.array(result), expected)

    def test_vmap_multi_arg(self, backend: str) -> None:
        bk = _bk()
        xp = bk.xp

        def dot2(a, b):
            return (a * b).sum()

        a = xp.ones((3, 4))
        b = xp.ones((3, 4)) * 2.0
        result = bk.vmap(dot2)(a, b)
        expected = np.full(3, 8.0)
        np.testing.assert_allclose(np.array(result), expected)


class TestBackendName:
    def test_backend_name_matches_env(self, backend: str) -> None:
        bk = _bk()
        assert bk.backend_name() == backend
