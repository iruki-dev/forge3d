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
