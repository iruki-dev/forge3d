"""Shared pytest fixtures — backend parametrization.

The `backend` fixture re-initialises forge3d.backend for each backend by
reloading the module after setting ENGINE_BACKEND.  Engine tests that need
`xp` / `set_at` / PRNG helpers should request the `backend` fixture; they
can then access the module attributes via `import forge3d.backend as bk`.

Reload strategy: importlib.reload() mutates the *same* module object so any
already-held reference (e.g. `bk = sys.modules['forge3d.backend']`) sees the
updated attributes after the reload.
"""

from __future__ import annotations

import importlib

import pytest


def _available_backends() -> list[str]:
    backends = ["numpy"]
    try:
        import jax  # noqa: F401

        backends.append("jax")
    except ImportError:
        pass
    return backends


@pytest.fixture(params=_available_backends(), ids=_available_backends())
def backend(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> str:
    """Parametrized fixture: runs each test for every available backend.

    Sets ENGINE_BACKEND, reloads forge3d.backend, and restores numpy afterward.
    """
    name: str = request.param
    monkeypatch.setenv("ENGINE_BACKEND", name)

    import forge3d.backend as bk

    importlib.reload(bk)

    yield name

    monkeypatch.setenv("ENGINE_BACKEND", "numpy")
    importlib.reload(bk)
