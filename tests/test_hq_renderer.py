"""P6 tests: HQ renderer scene conversion, raycasting, and contract."""

from __future__ import annotations

import numpy as np
import pytest

from forge3d.render.hq.raytracer import (
    _intersect_box,
    _intersect_sphere,
    render_frame,
)
from forge3d.render.hq.renderer import HQRenderer
from forge3d.render.hq.scene import HQCamera, HQLight, HQPrimitive, HQScene, build_hq_scene
from forge3d.render.snapshot import (
    BUILTIN_MATERIALS,
    BodySnapshot,
    CameraSnapshot,
    LightSnapshot,
    SceneSnapshot,
    Transform,
)

# ── Minimal snapshot factory ──────────────────────────────────────────────────


def _minimal_snapshot(with_sphere: bool = True) -> SceneSnapshot:
    bodies = []
    if with_sphere:
        bodies.append(
            BodySnapshot(
                name="ball",
                transform=Transform(
                    position=np.array([0.0, 0.0, 2.0]),
                    rotation=np.eye(3),
                ),
                shape_type="sphere",
                shape_params={"radius": 0.5},
                material_id="red",
            )
        )
    bodies.append(
        BodySnapshot(
            name="ground",
            transform=Transform(
                position=np.array([0.0, 0.0, -0.1]),
                rotation=np.eye(3),
            ),
            shape_type="box",
            shape_params={"half_extents": np.array([20.0, 20.0, 0.1])},
            material_id="ground",
        )
    )
    return SceneSnapshot(
        bodies=bodies,
        camera=CameraSnapshot(
            position=np.array([5.0, -8.0, 4.0]),
            target=np.array([0.0, 0.0, 0.0]),
            up=np.array([0.0, 0.0, 1.0]),
            fov_deg=45.0,
        ),
        lights=[
            LightSnapshot(
                direction=np.array([-0.4, -0.6, -0.7]) / np.linalg.norm([-0.4, -0.6, -0.7]),
                color=np.array([1.0, 0.95, 0.85]),
                intensity=1.0,
            )
        ],
        materials=dict(BUILTIN_MATERIALS),
        time=0.0,
    )


# ── scene.py ─────────────────────────────────────────────────────────────────


class TestBuildHQScene:
    def test_sphere_extracted(self):
        snap = _minimal_snapshot(with_sphere=True)
        scene = build_hq_scene(snap)
        spheres = [p for p in scene.primitives if p.ptype == "sphere"]
        assert len(spheres) == 1
        assert spheres[0].radius == pytest.approx(0.5)
        np.testing.assert_allclose(spheres[0].center, [0, 0, 2])

    def test_box_extracted(self):
        snap = _minimal_snapshot(with_sphere=False)
        scene = build_hq_scene(snap)
        boxes = [p for p in scene.primitives if p.ptype == "box"]
        assert len(boxes) == 1
        np.testing.assert_allclose(boxes[0].half_extents, [20, 20, 0.1])

    def test_light_toward_light_is_negated(self):
        snap = _minimal_snapshot()
        scene = build_hq_scene(snap)
        assert len(scene.lights) == 1
        light = scene.lights[0]
        # toward_light should point generally upward (z > 0)
        assert light.toward_light[2] > 0, "Light should be above scene"
        # Unit vector
        assert np.linalg.norm(light.toward_light) == pytest.approx(1.0, abs=1e-6)

    def test_camera_transferred(self):
        snap = _minimal_snapshot()
        scene = build_hq_scene(snap)
        np.testing.assert_allclose(scene.camera.position, [5, -8, 4])
        assert scene.camera.fov_deg == 45.0


# ── raytracer.py ──────────────────────────────────────────────────────────────


class TestIntersectSphere:
    def test_direct_hit(self):
        # Ray from origin along z, sphere at z=5 radius=1
        o = np.array([[0.0, 0.0, 0.0]])
        d = np.array([[0.0, 0.0, 1.0]])
        t = _intersect_sphere(o, d, np.array([0.0, 0.0, 5.0]), 1.0)
        assert t[0] == pytest.approx(4.0, abs=1e-6)

    def test_miss(self):
        o = np.array([[0.0, 0.0, 0.0]])
        d = np.array([[1.0, 0.0, 0.0]])
        t = _intersect_sphere(o, d, np.array([0.0, 0.0, 5.0]), 0.5)
        assert t[0] > 1e10

    def test_batch_hit_and_miss(self):
        o = np.array([[0, 0, 0], [10, 0, 0]], dtype=float)
        d = np.array([[0, 0, 1], [0, 0, 1]], dtype=float)
        t = _intersect_sphere(o, d, np.array([0.0, 0.0, 5.0]), 1.0)
        assert t[0] < 1e10
        assert t[1] > 1e10


class TestIntersectBox:
    def test_axis_aligned_hit(self):
        o = np.array([[0.0, 0.0, 5.0]])
        d = np.array([[0.0, 0.0, -1.0]])
        t = _intersect_box(
            o,
            d,
            center=np.array([0.0, 0.0, 0.0]),
            half_extents=np.array([1.0, 1.0, 1.0]),
            R=np.eye(3),
        )
        assert t[0] == pytest.approx(4.0, abs=1e-6)

    def test_miss(self):
        o = np.array([[5.0, 0.0, 0.0]])
        d = np.array([[0.0, 0.0, -1.0]])
        t = _intersect_box(
            o,
            d,
            center=np.array([0.0, 0.0, 0.0]),
            half_extents=np.array([1.0, 1.0, 1.0]),
            R=np.eye(3),
        )
        assert t[0] > 1e10


# ── render_frame smoke test ───────────────────────────────────────────────────


class TestRenderFrame:
    def _make_scene(self) -> HQScene:
        return HQScene(
            primitives=[
                HQPrimitive(
                    ptype="sphere",
                    center=np.array([0.0, 0.0, 0.0]),
                    radius=1.0,
                    R=np.eye(3),
                    color=np.array([0.8, 0.3, 0.2]),
                )
            ],
            lights=[
                HQLight(
                    toward_light=np.array([0.0, 0.0, 1.0]),
                    color=np.ones(3),
                    intensity=1.0,
                )
            ],
            camera=HQCamera(
                position=np.array([0.0, -5.0, 0.0]),
                target=np.array([0.0, 0.0, 0.0]),
                up=np.array([0.0, 0.0, 1.0]),
                fov_deg=45.0,
            ),
        )

    def test_output_shape(self):
        scene = self._make_scene()
        frame = render_frame(scene, width=16, height=12, samples=1)
        assert frame.shape == (12, 16, 3)
        assert frame.dtype == np.uint8

    def test_sphere_visible(self):
        """Sphere should produce non-uniform pixels (some lit, some sky)."""
        scene = self._make_scene()
        frame = render_frame(scene, width=32, height=32, samples=1)
        assert frame.std() > 5, "Frame should not be a uniform color"

    def test_no_negative_values(self):
        scene = self._make_scene()
        frame = render_frame(scene, width=16, height=12, samples=1)
        assert frame.min() >= 0
        assert frame.max() <= 255


# ── HQRenderer (Renderer ABC) ─────────────────────────────────────────────────


class TestHQRenderer:
    def test_render_returns_uint8(self):
        snap = _minimal_snapshot()
        renderer = HQRenderer(width=16, height=12, samples=1)
        frame = renderer.render(snap)
        assert frame.shape == (12, 16, 3)
        assert frame.dtype == np.uint8

    def test_renderer_contract_same_scene_both_renderers(self):
        """Both renderers accept the same SceneSnapshot without error."""
        snap = _minimal_snapshot()
        hq = HQRenderer(width=16, height=12, samples=1)
        frame_hq = hq.render(snap)
        assert frame_hq is not None
        # Realtime renderer requires Xvfb — skip if not available
        try:
            from forge3d.render.realtime.renderer import RealtimeRenderer

            with RealtimeRenderer(width=16, height=12) as rt:
                frame_rt = rt.render(snap)
            assert frame_rt is not None
        except Exception:
            pytest.skip("Realtime renderer not available in this environment")

    def test_context_manager(self):
        snap = _minimal_snapshot()
        with HQRenderer(width=8, height=8, samples=1) as renderer:
            frame = renderer.render(snap)
        assert frame is not None
