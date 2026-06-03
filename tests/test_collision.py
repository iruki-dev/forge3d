"""Unit tests for collision/detection.py — ContactPoint geometry."""

from __future__ import annotations

import numpy as np
import pytest

from forge3d.collision.detection import (
    _box_vs_box_halfspace,
    _sphere_vs_box_halfspace,
    _sphere_vs_sphere,
    detect_contacts,
)
from forge3d.sim.world import _Body

# ── Helpers ───────────────────────────────────────────────────────────────────


def _sphere(pos, radius=0.5, mass=1.0) -> _Body:
    return _Body(
        body_id=0,
        name="s",
        pos=np.asarray(pos, dtype=float),
        quat=np.array([1.0, 0.0, 0.0, 0.0]),
        vel=np.zeros(3),
        omega=np.zeros(3),
        mass=mass,
        static=False,
        restitution=0.5,
        friction=0.5,
        shape_type="sphere",
        shape_params={"radius": float(radius)},
        material_id="default",
    )


def _static_ground(z_center=-0.1, half_z=0.1) -> _Body:
    return _Body(
        body_id=1,
        name="ground",
        pos=np.array([0.0, 0.0, z_center]),
        quat=np.array([1.0, 0.0, 0.0, 0.0]),
        vel=np.zeros(3),
        omega=np.zeros(3),
        mass=0.0,
        static=True,
        restitution=0.0,
        friction=0.8,
        shape_type="box",
        shape_params={"half_extents": np.array([20.0, 20.0, half_z])},
        material_id="ground",
    )


def _dyn_box(pos, half_extents=(0.5, 0.5, 0.5), mass=1.0) -> _Body:
    return _Body(
        body_id=0,
        name="b",
        pos=np.asarray(pos, dtype=float),
        quat=np.array([1.0, 0.0, 0.0, 0.0]),
        vel=np.zeros(3),
        omega=np.zeros(3),
        mass=mass,
        static=False,
        restitution=0.3,
        friction=0.5,
        shape_type="box",
        shape_params={"half_extents": np.asarray(half_extents, dtype=float)},
        material_id="default",
    )


# ── sphere vs. box halfspace ──────────────────────────────────────────────────


class TestSphereVsBoxHalfspace:
    def test_no_contact_above(self):
        sphere = _sphere([0, 0, 2.0], radius=0.5)
        ground = _static_ground()
        # plane_z = 0.0, sphere center at 2.0, r=0.5 → depth = 0.5 - 2.0 < 0
        contacts = _sphere_vs_box_halfspace(sphere, 0, ground, 1)
        assert len(contacts) == 0

    def test_no_contact_resting(self):
        # Sphere center at exactly r above plane → depth = 0
        sphere = _sphere([0, 0, 0.5], radius=0.5)
        ground = _static_ground()
        contacts = _sphere_vs_box_halfspace(sphere, 0, ground, 1)
        assert len(contacts) == 0

    def test_contact_penetrating(self):
        sphere = _sphere([0, 0, 0.3], radius=0.5)  # center at 0.3, plane at 0.0
        ground = _static_ground()
        contacts = _sphere_vs_box_halfspace(sphere, 0, ground, 1)
        assert len(contacts) == 1
        c = contacts[0]
        assert c.depth == pytest.approx(0.2, abs=1e-9)
        np.testing.assert_allclose(c.normal, [0, 0, 1])
        assert c.body_a_idx == 0
        assert c.body_b_idx == 1

    def test_contact_at_surface(self):
        # Sphere fully through — depth = r
        sphere = _sphere([0, 0, 0.0], radius=0.5)
        ground = _static_ground()
        contacts = _sphere_vs_box_halfspace(sphere, 0, ground, 1)
        assert len(contacts) == 1
        assert contacts[0].depth == pytest.approx(0.5, abs=1e-9)


# ── box vs. box halfspace ─────────────────────────────────────────────────────


class TestBoxVsBoxHalfspace:
    def test_no_contact_floating(self):
        box = _dyn_box([0, 0, 2.0], half_extents=(0.5, 0.5, 0.5))
        ground = _static_ground()
        contacts = _box_vs_box_halfspace(box, 0, ground, 1)
        assert len(contacts) == 0

    def test_four_corners_penetrating(self):
        # Box resting with bottom face at z=0 → all 4 bottom corners at z=0
        # half_z = 0.5, so center at z=0.5, bottom corners at z=0.0
        box = _dyn_box([0, 0, 0.5], half_extents=(0.5, 0.5, 0.5))
        ground = _static_ground()
        contacts = _box_vs_box_halfspace(box, 0, ground, 1)
        # All 4 bottom corners exactly on plane → depth = 0 → no contacts
        assert len(contacts) == 0

    def test_corners_penetrating(self):
        # Box center at z=0.3, half_z=0.5 → bottom corners at z=-0.2 → depth=0.2
        box = _dyn_box([0, 0, 0.3], half_extents=(0.5, 0.5, 0.5))
        ground = _static_ground()
        contacts = _box_vs_box_halfspace(box, 0, ground, 1)
        assert len(contacts) == 4
        for c in contacts:
            assert c.depth == pytest.approx(0.2, abs=1e-9)
            np.testing.assert_allclose(c.normal, [0, 0, 1])


# ── sphere vs. sphere ─────────────────────────────────────────────────────────


class TestSphereVsSphere:
    def test_no_contact_far(self):
        a = _sphere([0, 0, 0], radius=0.5)
        b = _sphere([3, 0, 0], radius=0.5)
        contacts = _sphere_vs_sphere(a, 0, b, 1)
        assert len(contacts) == 0

    def test_no_contact_touching(self):
        a = _sphere([0, 0, 0], radius=0.5)
        b = _sphere([1, 0, 0], radius=0.5)
        contacts = _sphere_vs_sphere(a, 0, b, 1)
        assert len(contacts) == 0

    def test_contact_overlapping(self):
        a = _sphere([0, 0, 0], radius=0.5)
        b = _sphere([0.8, 0, 0], radius=0.5)
        contacts = _sphere_vs_sphere(a, 0, b, 1)
        assert len(contacts) == 1
        c = contacts[0]
        assert c.depth == pytest.approx(0.2, abs=1e-9)
        # normal: from b to a → [-1, 0, 0]
        np.testing.assert_allclose(c.normal, [-1, 0, 0], atol=1e-9)

    def test_contact_symmetry(self):
        # Overlap is symmetric regardless of index order
        a = _sphere([0, 0, 0], radius=0.5)
        b = _sphere([0.6, 0, 0], radius=0.5)
        c1 = _sphere_vs_sphere(a, 0, b, 1)
        assert len(c1) == 1
        assert c1[0].depth == pytest.approx(0.4, abs=1e-9)


# ── detect_contacts integration ───────────────────────────────────────────────


class TestDetectContacts:
    def test_sphere_on_ground(self):
        ground = _static_ground()
        sphere = _Body(
            body_id=1,
            name="s",
            pos=np.array([0.0, 0.0, 0.3]),
            quat=np.array([1.0, 0.0, 0.0, 0.0]),
            vel=np.zeros(3),
            omega=np.zeros(3),
            mass=1.0,
            static=False,
            restitution=0.5,
            friction=0.5,
            shape_type="sphere",
            shape_params={"radius": 0.5},
            material_id="default",
        )
        # bodies[0] = ground (static), bodies[1] = sphere (dynamic)
        contacts = detect_contacts([ground, sphere])
        assert len(contacts) == 1
        assert contacts[0].body_a_idx == 1  # sphere is a

    def test_no_contact_no_overlap(self):
        ground = _static_ground()
        sphere = _Body(
            body_id=1,
            name="s",
            pos=np.array([0.0, 0.0, 5.0]),
            quat=np.array([1.0, 0.0, 0.0, 0.0]),
            vel=np.zeros(3),
            omega=np.zeros(3),
            mass=1.0,
            static=False,
            restitution=0.5,
            friction=0.5,
            shape_type="sphere",
            shape_params={"radius": 0.5},
            material_id="default",
        )
        contacts = detect_contacts([ground, sphere])
        assert len(contacts) == 0

    def test_two_static_no_contact(self):
        g1 = _static_ground()
        g2 = _static_ground()
        contacts = detect_contacts([g1, g2])
        assert len(contacts) == 0
