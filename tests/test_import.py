"""Smoke test: import forge3d succeeds and version string is present."""

from __future__ import annotations


def test_import_forge3d() -> None:
    import forge3d

    assert forge3d.__version__ == "1.0.0"


def test_import_backend() -> None:
    import forge3d.backend as bk

    assert bk.backend_name() in ("numpy", "jax")


def test_import_subpackages() -> None:
    import forge3d.collision  # noqa: F401
    import forge3d.contact  # noqa: F401
    import forge3d.dynamics  # noqa: F401
    import forge3d.math  # noqa: F401
    import forge3d.model  # noqa: F401
    import forge3d.render  # noqa: F401
    import forge3d.render.hq  # noqa: F401
    import forge3d.render.realtime  # noqa: F401
    import forge3d.sim  # noqa: F401


def test_import_render_contracts() -> None:
    from forge3d.render.base import Renderer
    from forge3d.render.snapshot import SceneSnapshot

    assert SceneSnapshot is not None
    assert Renderer is not None


def test_import_logging() -> None:
    from forge3d.logging import MetricWriter

    w = MetricWriter()
    w.scalar("loss", 1.0)
    w.close()
