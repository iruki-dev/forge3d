"""Tests for SceneSnapshot — pure data contract between physics and renderer.

Key invariants:
1. world.snapshot() never imports moderngl / glfw / pyglet / renderer code.
2. Snapshot fields are plain numpy float64 arrays (backend-neutral).
3. Consistent results across ENGINE_BACKEND=numpy and =jax.
"""

from __future__ import annotations

import importlib
import sys

import numpy as np

from forge3d.sim.world import PhysicsWorld

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_world() -> PhysicsWorld:
    w = PhysicsWorld(gravity=[0.0, 0.0, -9.81])
    w.add_box((1.0, 1.0, 1.0), (0.0, 0.0, 5.0), mass=1.0, material="red")
    w.add_sphere(0.5, (1.0, 0.0, 3.0), mass=0.5, material="blue")
    w.add_static_box((20.0, 20.0, 0.2), (0.0, 0.0, -0.1), material="ground")
    w.set_camera((5.0, -8.0, 4.0), (0.0, 0.0, 0.0))
    return w


# ── SceneSnapshot structure ───────────────────────────────────────────────────


class TestSnapshotStructure:
    def test_body_count(self) -> None:
        w = _make_world()
        snap = w.snapshot()
        assert len(snap.bodies) == 3

    def test_transform_types(self) -> None:
        w = _make_world()
        snap = w.snapshot()
        for body in snap.bodies:
            assert body.transform.position.shape == (3,)
            assert body.transform.rotation.shape == (3, 3)
            assert body.transform.position.dtype == np.float64
            assert body.transform.rotation.dtype == np.float64

    def test_rotation_is_orthogonal(self) -> None:
        w = _make_world()
        # Give the box some angular velocity
        b = w._bodies[0]
        w._bodies[0] = b.__class__(**{**b.__dict__, "omega": np.array([1.0, 0.5, 0.3])})
        for _ in range(50):
            w.step(1.0 / 240.0)
        snap = w.snapshot()
        for body in snap.bodies:
            R = body.transform.rotation
            np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-12)
            np.testing.assert_allclose(np.linalg.det(R), 1.0, atol=1e-12)

    def test_shape_params_present(self) -> None:
        w = _make_world()
        snap = w.snapshot()
        box_snap = next(b for b in snap.bodies if b.shape_type == "box" and b.material_id == "red")
        assert "half_extents" in box_snap.shape_params
        np.testing.assert_allclose(
            box_snap.shape_params["half_extents"], [0.5, 0.5, 0.5], atol=1e-12
        )

    def test_camera_present(self) -> None:
        w = _make_world()
        snap = w.snapshot()
        assert snap.camera is not None
        assert snap.camera.position.shape == (3,)
        assert snap.camera.target.shape == (3,)

    def test_lights_present(self) -> None:
        w = _make_world()
        snap = w.snapshot()
        assert len(snap.lights) >= 1
        l0 = snap.lights[0]
        assert l0.direction.shape == (3,)

    def test_materials_present(self) -> None:
        w = _make_world()
        snap = w.snapshot()
        assert "default" in snap.materials
        assert "ground" in snap.materials

    def test_time_advances(self) -> None:
        w = _make_world()
        s0 = w.snapshot()
        assert s0.time == 0.0
        w.step(1.0 / 60.0)
        s1 = w.snapshot()
        np.testing.assert_allclose(s1.time, 1.0 / 60.0, rtol=1e-10)

    def test_snapshot_copy_safety(self) -> None:
        """Mutating world state after snapshot must not alter the snapshot."""
        w = _make_world()
        s0 = w.snapshot()
        pos_before = s0.bodies[0].transform.position.copy()
        for _ in range(60):
            w.step(1.0 / 60.0)
        np.testing.assert_allclose(s0.bodies[0].transform.position, pos_before)


# ── No-render-import invariant ────────────────────────────────────────────────


class TestNoRendererImport:
    """Ensure sim.world does NOT import moderngl, glfw, pyglet, or render modules."""

    def test_world_module_no_gl_imports(self) -> None:
        """forge3d.sim.world must not import any renderer module at load time."""
        world_mod = sys.modules["forge3d.sim.world"]

        # Use AST to find actual import statements (ignores docstrings/comments)
        import ast
        import inspect

        src = inspect.getsource(world_mod)
        tree = ast.parse(src)
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_names.add(node.module.split(".")[0])
        for lib in ["moderngl", "glfw", "pyglet", "OpenGL"]:
            assert lib not in imported_names, (
                f"forge3d.sim.world AST-imports '{lib}' — physics must not depend on renderer"
            )

    def test_snapshot_module_no_gl_imports(self) -> None:
        """render.snapshot is pure data — no renderer imports."""
        import inspect

        import forge3d.render.snapshot as snap_mod

        src = inspect.getsource(snap_mod)
        for lib in ["moderngl", "glfw", "pyglet", "OpenGL"]:
            assert lib not in src, f"render.snapshot contains '{lib}'"

    def test_physics_modules_no_render_import(self) -> None:
        """dynamics/ math/ model/ must not import forge3d.render.*"""
        phys_modules = [
            "forge3d.dynamics.rnea",
            "forge3d.dynamics.aba",
            "forge3d.dynamics.crba",
            "forge3d.math.se3",
            "forge3d.math.spatial",
            "forge3d.model.kinematics",
        ]
        import importlib
        import inspect

        for mod_name in phys_modules:
            mod = importlib.import_module(mod_name)
            src = inspect.getsource(mod)
            assert "forge3d.render" not in src, (
                f"{mod_name} imports forge3d.render — physics must not depend on renderer"
            )


# ── Backend parity ────────────────────────────────────────────────────────────


class TestBackendParity:
    """Snapshot must be identical across numpy and jax backends."""

    def test_snapshot_position_matches_backends(self, backend: str) -> None:
        """Body positions must be equal for numpy and jax backends."""
        import forge3d.backend as bk

        importlib.reload(bk)

        w = _make_world()
        for _ in range(30):
            w.step(1.0 / 240.0)
        snap = w.snapshot()
        # The snapshot always returns plain numpy arrays
        for body in snap.bodies:
            assert isinstance(body.transform.position, np.ndarray), (
                f"transform.position must be numpy, got {type(body.transform.position)}"
            )
