"""Tests for forge3d.camera — OrbitCamera, FollowCamera."""

from __future__ import annotations


import numpy as np
import pytest

import forge3d as f3d
from forge3d.camera import FollowCamera, OrbitCamera
from forge3d.render.snapshot import CameraSnapshot


class TestOrbitCamera:
    def test_default_construction(self):
        cam = OrbitCamera()
        assert cam.distance == pytest.approx(10.0)
        assert cam.azimuth == pytest.approx(45.0)
        assert cam.elevation == pytest.approx(30.0)
        assert cam.fov_deg == pytest.approx(45.0)
        assert np.allclose(cam.target, [0.0, 0.0, 0.0])

    def test_position_on_sphere(self):
        cam = OrbitCamera(target=(0, 0, 0), distance=5.0, azimuth=0.0, elevation=0.0)
        pos = cam.position
        # azimuth=0, elevation=0 → eye on +x axis
        assert pos[0] == pytest.approx(5.0, abs=1e-6)
        assert pos[1] == pytest.approx(0.0, abs=1e-6)
        assert pos[2] == pytest.approx(0.0, abs=1e-6)

    def test_position_distance(self):
        cam = OrbitCamera(distance=8.0, azimuth=37.0, elevation=22.0)
        dist = np.linalg.norm(cam.position - cam.target)
        assert dist == pytest.approx(8.0, rel=1e-5)

    def test_rotate(self):
        cam = OrbitCamera(azimuth=0.0, elevation=0.0)
        cam.rotate(d_azimuth=90.0, d_elevation=15.0)
        assert cam.azimuth == pytest.approx(90.0)
        assert cam.elevation == pytest.approx(15.0)

    def test_elevation_clamped(self):
        cam = OrbitCamera(elevation=80.0)
        cam.rotate(d_elevation=20.0)   # would be 100°
        assert cam.elevation == pytest.approx(89.0)
        cam.rotate(d_elevation=-200.0)
        assert cam.elevation == pytest.approx(-89.0)

    def test_zoom_reduces_distance(self):
        cam = OrbitCamera(distance=10.0)
        cam.zoom(1.0)   # positive → closer
        assert cam.distance < 10.0

    def test_zoom_negative_increases_distance(self):
        cam = OrbitCamera(distance=10.0)
        cam.zoom(-1.0)
        assert cam.distance > 10.0

    def test_zoom_minimum_distance(self):
        cam = OrbitCamera(distance=0.1)
        cam.zoom(100.0)   # extreme zoom in
        assert cam.distance >= 0.05

    def test_set_distance(self):
        cam = OrbitCamera()
        cam.set_distance(3.0)
        assert cam.distance == pytest.approx(3.0)

    def test_look_at(self):
        cam = OrbitCamera(target=(0, 0, 0))
        cam.look_at((1.0, 2.0, 3.0))
        assert np.allclose(cam.target, [1.0, 2.0, 3.0])
        dist = np.linalg.norm(cam.position - cam.target)
        assert dist == pytest.approx(cam.distance, rel=1e-5)

    def test_pan_moves_target(self):
        cam = OrbitCamera(target=(0, 0, 0))
        original_target = cam.target.copy()
        cam.pan(100.0, 0.0)
        assert not np.allclose(cam.target, original_target)

    def test_to_snapshot_type(self):
        cam = OrbitCamera()
        snap = cam.to_snapshot()
        assert isinstance(snap, CameraSnapshot)

    def test_to_snapshot_values(self):
        cam = OrbitCamera(target=(1.0, 2.0, 3.0), fov_deg=60.0)
        snap = cam.to_snapshot()
        assert np.allclose(snap.target, [1.0, 2.0, 3.0])
        assert snap.fov_deg == pytest.approx(60.0)
        assert np.allclose(snap.up, [0.0, 0.0, 1.0])

    def test_to_snapshot_position_consistent(self):
        cam = OrbitCamera()
        snap = cam.to_snapshot()
        assert np.allclose(snap.position, cam.position)

    def test_chaining(self):
        cam = OrbitCamera()
        result = cam.rotate(d_azimuth=10).zoom(1).set_distance(5).look_at((1, 0, 0))
        assert result is cam

    def test_repr(self):
        cam = OrbitCamera()
        r = repr(cam)
        assert "OrbitCamera" in r
        assert "az=" in r

    def test_f3d_export(self):
        cam = f3d.OrbitCamera()
        assert isinstance(cam, OrbitCamera)


class TestFollowCamera:
    def _make_body(self, position=(0, 0, 0)):
        world = f3d.World()
        world.add_ground()
        body = world.add_box(position=position)
        return body

    def test_construction(self):
        body = self._make_body((1, 2, 3))
        cam = FollowCamera(body, offset=(0, -8, 4))
        assert cam.alpha == pytest.approx(0.1)
        assert np.allclose(cam.offset, [0, -8, 4])

    def test_to_snapshot_type(self):
        body = self._make_body()
        cam = FollowCamera(body)
        snap = cam.to_snapshot()
        assert isinstance(snap, CameraSnapshot)

    def test_snapshot_target_is_body_position(self):
        body = self._make_body((1.0, 2.0, 3.0))
        cam = FollowCamera(body)
        snap = cam.to_snapshot()
        assert np.allclose(snap.target, [1.0, 2.0, 3.0])

    def test_smoothing_converges(self):
        body = self._make_body((0, 0, 0))
        cam = FollowCamera(body, offset=(0, 0, 10), alpha=1.0)
        snap = cam.to_snapshot()
        # alpha=1 → instant snap
        assert np.allclose(snap.position, [0, 0, 10], atol=1e-6)

    def test_repr(self):
        body = self._make_body()
        cam = FollowCamera(body)
        assert "FollowCamera" in repr(cam)
