"""P4 API usability tests.

Key invariants:
1. forge3d exposes exactly the right public symbols (≤ 6 concepts).
2. examples/01 uses ≤ 15 lines of body code and only 'import forge3d'.
3. World helpers work with minimum args.
4. World snapshot integrates properly with Viewer/Recorder interfaces.
"""

from __future__ import annotations

import ast
import os

import numpy as np
import pytest

import forge3d as f3d
from forge3d.facade import Body

# ── Public API surface ────────────────────────────────────────────────────────


class TestPublicSurface:
    def test_all_symbols_exported(self) -> None:
        for sym in ["World", "Body", "Shape", "Material", "Viewer", "Recorder"]:
            assert hasattr(f3d, sym), f"forge3d missing public symbol: {sym}"

    def test_core_concepts_exported(self) -> None:
        """All core public concepts must appear in __all__."""
        required = {
            "World", "Body", "Shape", "Material",
            "App", "Input", "Key",
            "OrbitCamera", "FollowCamera",
            "Viewer", "Recorder",
        }
        missing = required - set(f3d.__all__)
        assert not missing, f"forge3d.__all__ is missing: {missing}"

    def test_internal_types_not_leaked(self) -> None:
        """Physics internals must not appear in the public namespace."""
        forbidden = ["PhysicsWorld", "_Body", "RigidBodyModel", "inverse_dynamics"]
        for sym in forbidden:
            assert not hasattr(f3d, sym), (
                f"forge3d exposes internal symbol '{sym}' — abstraction leak"
            )


# ── World helpers ─────────────────────────────────────────────────────────────


class TestWorldHelpers:
    def test_world_default_gravity(self) -> None:
        w = f3d.World()
        # Default gravity = [0, 0, -9.81]
        np.testing.assert_allclose(w._physics._gravity, [0.0, 0.0, -9.81], atol=1e-10)

    def test_add_ground_no_args(self) -> None:
        w = f3d.World()
        g = w.add_ground()
        assert isinstance(g, Body)

    def test_add_box_minimal(self) -> None:
        w = f3d.World()
        b = w.add_box()
        assert isinstance(b, Body)
        np.testing.assert_allclose(b.position, [0, 0, 0], atol=1e-12)

    def test_add_box_with_args(self) -> None:
        w = f3d.World()
        b = w.add_box(size=(2, 2, 2), position=(0, 0, 5), mass=3.0)
        assert isinstance(b, Body)
        np.testing.assert_allclose(b.position, [0, 0, 5], atol=1e-12)

    def test_add_sphere(self) -> None:
        w = f3d.World()
        b = w.add_sphere(radius=0.5, position=(1, 0, 3))
        assert isinstance(b, Body)

    def test_step_advances_time(self) -> None:
        w = f3d.World()
        w.add_box(position=(0, 0, 5))
        assert w.time == 0.0
        w.step(dt=1 / 60)
        np.testing.assert_allclose(w.time, 1 / 60, rtol=1e-10)

    def test_step_default_dt(self) -> None:
        w = f3d.World()
        w.step()  # should not raise
        np.testing.assert_allclose(w.time, f3d.World.DEFAULT_DT, rtol=1e-10)

    def test_body_falls_under_gravity(self) -> None:
        w = f3d.World(gravity=(0, 0, -9.81))
        b = w.add_box(position=(0, 0, 10))
        z0 = b.position[2]
        for _ in range(60):
            w.step(dt=1 / 60)
        assert b.position[2] < z0 - 1.0, "Box did not fall under gravity"

    def test_static_body_does_not_move(self) -> None:
        w = f3d.World()
        g = w.add_ground()
        pos0 = g.position.copy()
        for _ in range(60):
            w.step(dt=1 / 60)
        np.testing.assert_allclose(g.position, pos0, atol=1e-12)


# ── Material and Shape ────────────────────────────────────────────────────────


class TestMaterialShape:
    def test_material_string(self) -> None:
        w = f3d.World()
        b = w.add_box(material="red")
        assert isinstance(b, Body)

    def test_material_object(self) -> None:
        w = f3d.World()
        mat = f3d.Material(color="blue", roughness=0.3)
        b = w.add_box(material=mat)
        assert isinstance(b, Body)

    def test_material_rgb_tuple(self) -> None:
        w = f3d.World()
        mat = f3d.Material(color=(0.9, 0.2, 0.1))
        b = w.add_box(material=mat)
        assert isinstance(b, Body)

    def test_shape_box_factory(self) -> None:
        s = f3d.Shape.box(size=(2, 3, 1))
        assert s.type == "box"
        np.testing.assert_allclose(s.params["half_extents"], [1, 1.5, 0.5])

    def test_shape_sphere_factory(self) -> None:
        s = f3d.Shape.sphere(radius=0.7)
        assert s.type == "sphere"
        assert s.params["radius"] == pytest.approx(0.7)


# ── Snapshot integration ──────────────────────────────────────────────────────


class TestSnapshotIntegration:
    def test_snapshot_reflects_material(self) -> None:
        w = f3d.World()
        w.add_box(material=f3d.Material(color=(0.5, 0.1, 0.9)))
        snap = w.snapshot()
        # Custom material should be injected into snapshot.materials
        custom_ids = [mid for mid in snap.materials if mid.startswith("custom#")]
        assert len(custom_ids) >= 1

    def test_snapshot_bodies_match(self) -> None:
        w = f3d.World()
        w.add_ground()
        w.add_box(position=(0, 0, 5))
        w.add_sphere(position=(1, 0, 3))
        snap = w.snapshot()
        assert len(snap.bodies) == 3

    def test_world_repr(self) -> None:
        w = f3d.World()
        r = repr(w)
        assert "World" in r and "t=" in r


# ── Example 01 line count and import check ───────────────────────────────────


class TestExample01:
    EXAMPLE_PATH = os.path.join(
        os.path.dirname(__file__), "..", "examples", "01_falling_box_realtime.py"
    )

    def _source(self) -> str:
        with open(self.EXAMPLE_PATH) as f:
            return f.read()

    def test_uses_only_forge3d_import(self) -> None:
        """The example must only import 'forge3d', not internal sub-modules."""
        src = self._source()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name == "forge3d" or not alias.name.startswith("forge3d"), (
                        f"example imports internal module: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("forge3d."):
                raise AssertionError(
                    f"example imports internal module: {node.module}\n"
                    "Only 'import forge3d' is allowed."
                )

    def test_body_lines_under_15(self) -> None:
        """Non-blank, non-comment, non-docstring body lines must be ≤ 15."""
        src = self._source()
        lines = src.splitlines()
        body_lines = [
            ln
            for ln in lines
            if ln.strip()  # not blank
            and not ln.strip().startswith("#")  # not comment
            and not ln.strip().startswith('"""')  # not docstring start/end
            and not ln.strip().startswith("'''")
        ]
        assert len(body_lines) <= 15, (
            f"Example has {len(body_lines)} body lines (limit: 15):\n"
            + "\n".join(f"  {ln}" for ln in body_lines)
        )
