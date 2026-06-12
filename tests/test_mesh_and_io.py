"""Tests for forge3d.io (OBJ loader, MeshData) and mesh collision shapes."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

ASSETS = Path(__file__).parent.parent / "assets" / "models"


# ── OBJ loader ────────────────────────────────────────────────────────────────


class TestOBJLoader:
    def test_load_cube(self) -> None:
        from forge3d.io import load_obj

        mesh = load_obj(ASSETS / "cube.obj")
        assert mesh.n_vertices > 0
        assert mesh.n_triangles > 0
        assert mesh.vertices.shape[1] == 3
        assert mesh.normals.shape == mesh.vertices.shape
        assert mesh.uvs.shape == (mesh.n_vertices, 2)
        assert mesh.indices.shape[0] % 3 == 0

    def test_load_tetrahedron(self) -> None:
        from forge3d.io import load_obj

        mesh = load_obj(ASSETS / "tetrahedron.obj")
        assert mesh.n_triangles == 4
        assert len(mesh.hull_vertices) == 4  # tetrahedron has 4 hull points

    def test_interleaved_layout(self) -> None:
        from forge3d.io import load_obj

        mesh = load_obj(ASSETS / "cube.obj")
        v = mesh.interleaved()
        assert v.dtype == np.float32
        assert v.shape == (mesh.n_vertices, 8)  # [pos3, normal3, uv2]

    def test_hull_vertices_are_subset(self) -> None:
        from forge3d.io import load_obj

        mesh = load_obj(ASSETS / "cube.obj")
        # Convex hull of a unit cube has 8 corners
        assert len(mesh.hull_vertices) == 8

    def test_normals_unit_length(self) -> None:
        from forge3d.io import load_obj

        mesh = load_obj(ASSETS / "cube.obj")
        norms = np.linalg.norm(mesh.normals, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5)

    def test_missing_file_raises(self) -> None:
        from forge3d.io import load_obj

        with pytest.raises(FileNotFoundError):
            load_obj("no_such_file.obj")

    def test_mesh_id_is_unique(self) -> None:
        from forge3d.io import load_obj

        m1 = load_obj(ASSETS / "cube.obj")
        m2 = load_obj(ASSETS / "cube.obj")
        assert m1.mesh_id != m2.mesh_id  # different object, different id


# ── MeshData from_arrays ──────────────────────────────────────────────────────


class TestMeshDataFromArrays:
    def test_from_triangle(self) -> None:
        from forge3d.io.mesh_data import MeshData

        pos = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
        nrm = np.array([[0, 0, 1], [0, 0, 1], [0, 0, 1]], dtype=np.float32)
        uvs = np.array([[0, 0], [1, 0], [0, 1]], dtype=np.float32)
        idx = np.array([0, 1, 2], dtype=np.uint32)
        mesh = MeshData.from_arrays(pos, nrm, uvs, idx)
        assert mesh.n_triangles == 1
        assert len(mesh.hull_vertices) == 3

    def test_auto_normals_without_uv(self) -> None:
        from forge3d.io.mesh_data import MeshData

        pos = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
        nrm = np.zeros((4, 3), dtype=np.float32)  # all zero → will be recomputed
        idx = np.array([0, 1, 2, 0, 1, 3, 0, 2, 3, 1, 2, 3], dtype=np.uint32)
        mesh = MeshData.from_arrays(pos, nrm, None, idx)
        assert mesh.n_triangles == 4


# ── Mesh collision physics ─────────────────────────────────────────────────────


class TestMeshPhysics:
    def test_add_mesh_to_world(self) -> None:
        import forge3d as f3d
        from forge3d.io import load_obj

        world = f3d.World()
        world.add_ground()
        mesh = load_obj(ASSETS / "cube.obj")
        body = world.add_mesh(mesh, position=(0, 0, 3), mass=1.0)
        assert body is not None

    def test_mesh_falls_under_gravity(self) -> None:
        import forge3d as f3d
        from forge3d.io import load_obj

        world = f3d.World()
        world.add_ground()
        mesh = load_obj(ASSETS / "cube.obj")
        body = world.add_mesh(mesh, position=(0, 0, 5), mass=1.0)
        initial_z = body.position[2]
        for _ in range(60):
            world.step(1 / 60)
        assert body.position[2] < initial_z  # fell under gravity

    def test_mesh_vs_plane_collision(self) -> None:
        from forge3d.io import load_obj
        from forge3d.sim.world import PhysicsWorld

        w = PhysicsWorld()
        w.add_static_box((20, 20, 0.2), (0, 0, -0.1))  # ground plane as box
        mesh = load_obj(ASSETS / "cube.obj")
        w.add_convex_mesh(mesh, position=(0, 0, 0.3), mass=1.0)  # cube just above ground
        for _ in range(120):
            w.step(1 / 60)
        # After settling, cube should be resting near z=0.5 (half-height)
        cube_body = w._bodies[-1]
        assert cube_body.pos[2] < 2.0  # didn't fly off

    def test_mesh_snapshot_contains_mesh_data(self) -> None:
        from forge3d.io import load_obj
        from forge3d.sim.world import PhysicsWorld

        w = PhysicsWorld()
        mesh = load_obj(ASSETS / "cube.obj")
        w.add_convex_mesh(mesh, position=(0, 0, 3), mass=1.0)
        snap = w.snapshot()
        mesh_body = snap.bodies[-1]
        assert mesh_body.shape_type == "mesh"
        assert "hull_vertices" in mesh_body.shape_params
        assert "mesh_data" in mesh_body.shape_params

    def test_gjk_contact_between_meshes(self) -> None:
        from forge3d.collision.gjk import gjk, gjk_contact
        from forge3d.io import load_obj
        from forge3d.sim.world import PhysicsWorld

        w = PhysicsWorld()
        mesh = load_obj(ASSETS / "cube.obj")
        w.add_convex_mesh(mesh, position=(0, 0, 0), mass=1.0)
        w.add_convex_mesh(mesh, position=(0, 0, 0.5), mass=1.0)  # overlapping

        a, b = w._bodies[0], w._bodies[1]
        intersecting, dist = gjk(a, b)
        assert intersecting  # they overlap

        result = gjk_contact(a, b)
        assert result is not None
        depth, normal = result
        assert depth > 0.0
        assert abs(np.linalg.norm(normal) - 1.0) < 1e-5  # unit normal


# ── New primitive shapes ──────────────────────────────────────────────────────


class TestBuiltinShapes:
    """Smoke tests for add_cylinder, add_cone, add_wedge, add_convex."""

    def _world_with_ground(self):
        import forge3d as f3d

        world = f3d.World(gravity=(0, 0, -9.81))
        world.add_ground(size=(40, 40, 0.2))
        return world

    def test_add_cylinder_exists(self) -> None:
        world = self._world_with_ground()
        body = world.add_cylinder(radius=0.5, half_length=0.5, position=(0, 0, 2), mass=1.0)
        assert body is not None
        assert body.position[2] == pytest.approx(2.0, abs=0.01)

    def test_add_cone_exists(self) -> None:
        world = self._world_with_ground()
        body = world.add_cone(radius=0.5, height=1.0, position=(0, 0, 2), mass=1.0)
        assert body is not None

    def test_add_wedge_exists(self) -> None:
        world = self._world_with_ground()
        body = world.add_wedge(size=(1, 1, 1), position=(0, 0, 2), mass=1.0)
        assert body is not None

    def test_add_convex_exists(self) -> None:
        world = self._world_with_ground()
        pts = np.array([[1, 0, 0], [0, 1, 0], [-1, 0, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], dtype=float)
        body = world.add_convex(pts, position=(0, 0, 3), mass=1.0)
        assert body is not None

    def test_cylinder_lands_on_ground(self) -> None:
        """Cylinder must not fall through the ground."""
        from forge3d.collision.detection import _quat_to_rot_unit

        world = self._world_with_ground()
        body = world.add_cylinder(radius=0.5, half_length=0.5, position=(0, 0, 2), mass=1.0)
        for _ in range(300):
            world.step(dt=1 / 60)

        b = world._physics._bodies[1]
        R = _quat_to_rot_unit(b.quat)
        hull_world_z = (b.pos + b.shape_params["hull_vertices"] @ R.T)[:, 2]
        assert hull_world_z.min() > -0.05, "Cylinder hull vertex fell below ground"
        assert body.position[2] < 2.0, "Cylinder didn't fall"

    def test_wedge_lands_on_ground(self) -> None:
        """Wedge must not fall through the ground."""
        from forge3d.collision.detection import _quat_to_rot_unit

        world = self._world_with_ground()
        body = world.add_wedge(size=(1, 1, 1), position=(0, 0, 2), mass=1.0)
        for _ in range(300):
            world.step(dt=1 / 60)

        b = world._physics._bodies[1]
        R = _quat_to_rot_unit(b.quat)
        hull_world_z = (b.pos + b.shape_params["hull_vertices"] @ R.T)[:, 2]
        assert hull_world_z.min() > -0.05, "Wedge hull vertex fell below ground"
        assert body.position[2] < 2.0, "Wedge didn't fall"

    def test_convex_lands_on_ground(self) -> None:
        """Convex octahedron must not fall through the ground."""
        from forge3d.collision.detection import _quat_to_rot_unit

        world = self._world_with_ground()
        pts = np.array([[1, 0, 0], [0, 1, 0], [-1, 0, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], dtype=float)
        body = world.add_convex(pts, position=(0, 0, 3), mass=1.0)
        for _ in range(300):
            world.step(dt=1 / 60)

        b = world._physics._bodies[1]
        R = _quat_to_rot_unit(b.quat)
        hull_world_z = (b.pos + b.shape_params["hull_vertices"] @ R.T)[:, 2]
        assert hull_world_z.min() > -0.05, "Convex hull vertex fell below ground"
        assert body.position[2] < 3.0, "Convex didn't fall"

    def test_cylinder_shape_params(self) -> None:
        """Cylinder body must expose hull_vertices and mesh_data in shape_params."""
        world = self._world_with_ground()
        world.add_cylinder(radius=0.5, half_length=0.5, position=(0, 0, 2), mass=1.0)
        b = world._physics._bodies[1]
        assert "hull_vertices" in b.shape_params
        assert b.shape_params["hull_vertices"].shape[1] == 3
        assert b.shape_type == "mesh"

    def test_add_convex_hull_computed(self) -> None:
        """add_convex must compute a valid convex hull from the input points."""
        world = self._world_with_ground()
        pts = np.random.default_rng(42).standard_normal((20, 3)).astype(float)
        world.add_convex(pts, position=(0, 0, 3), mass=1.0)
        b = world._physics._bodies[1]
        hv = b.shape_params["hull_vertices"]
        assert hv.shape[0] <= 20, "Hull should not have more vertices than input"
        assert hv.shape[1] == 3

    def test_static_cylinder(self) -> None:
        """Static cylinder must not move."""
        world = self._world_with_ground()
        body = world.add_cylinder(radius=0.3, half_length=1.0, position=(0, 0, 1), static=True)
        initial_pos = body.position.copy()
        for _ in range(60):
            world.step(dt=1 / 60)
        assert np.allclose(body.position, initial_pos), "Static cylinder moved"


# ── Capsule rendering smoke ────────────────────────────────────────────────────


class TestCapsuleRendering:
    def test_capsule_in_snapshot(self) -> None:
        import forge3d as f3d

        world = f3d.World()
        world.add_ground()
        world.add_capsule(radius=0.3, half_length=0.5, position=(0, 0, 2))
        snap = world.snapshot()
        cap_body = next(b for b in snap.bodies if b.shape_type == "capsule")
        assert cap_body is not None
        assert cap_body.shape_params["radius"] == 0.3

    @pytest.mark.skipif(
        not __import__(
            "forge3d.render.realtime.context", fromlist=["check_opengl_available"]
        ).check_opengl_available(),
        reason="OpenGL not available",
    )
    def test_capsule_renders_without_error(self) -> None:
        from forge3d.render.realtime.context import check_opengl_available

        if not check_opengl_available():
            pytest.skip("OpenGL not available")

        import forge3d as f3d
        from forge3d.render.realtime.renderer import RealtimeRenderer

        world = f3d.World()
        world.add_ground()
        world.add_capsule(radius=0.3, half_length=0.5, position=(0, 0, 2))
        world.set_camera((5, -8, 4), (0, 0, 0))
        snap = world.snapshot()

        with RealtimeRenderer(width=160, height=120) as r:
            frame = r.render(snap)
        assert frame.shape == (120, 160, 3)
        # Some non-background pixels expected
        diff = np.abs(frame.astype(int) - np.array([13, 18, 26], dtype=int)).sum(axis=-1)
        assert (diff > 10).sum() > 100

    @pytest.mark.skipif(
        not __import__(
            "forge3d.render.realtime.context", fromlist=["check_opengl_available"]
        ).check_opengl_available(),
        reason="OpenGL not available",
    )
    def test_mesh_renders_without_error(self) -> None:
        from forge3d.render.realtime.context import check_opengl_available

        if not check_opengl_available():
            pytest.skip("OpenGL not available")

        import forge3d as f3d
        from forge3d.io import load_obj
        from forge3d.render.realtime.renderer import RealtimeRenderer

        world = f3d.World()
        world.add_ground()
        mesh = load_obj(ASSETS / "cube.obj")
        world.add_mesh(mesh, position=(0, 0, 2), mass=1.0)
        world.set_camera((5, -8, 4), (0, 0, 0))
        snap = world.snapshot()

        with RealtimeRenderer(width=160, height=120) as r:
            frame = r.render(snap)
        assert frame.shape == (120, 160, 3)
