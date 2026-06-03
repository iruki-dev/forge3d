"""P20: API hardening & error message tests."""

from __future__ import annotations

import pytest

import forge3d as f3d
from forge3d import ValidationError


# ── Gravity validation ────────────────────────────────────────────────────────


def test_gravity_must_be_3_element():
    """World() should raise ValidationError for non-3-element gravity."""
    with pytest.raises(ValidationError, match="3-element"):
        f3d.World(gravity=(0, -9.81))

    with pytest.raises(ValidationError, match="3-element"):
        f3d.World(gravity=(0, 0, -9.81, 0))


# ── add_box validation ────────────────────────────────────────────────────────


def test_add_box_negative_mass():
    """add_box should raise ValidationError for mass <= 0."""
    world = f3d.World()
    with pytest.raises(ValidationError, match="mass"):
        world.add_box(size=(1, 1, 1), mass=-1.0)

    with pytest.raises(ValidationError, match="mass"):
        world.add_box(size=(1, 1, 1), mass=0.0)


def test_add_box_zero_size():
    """add_box should raise ValidationError for zero or negative size components."""
    world = f3d.World()
    with pytest.raises(ValidationError, match="size"):
        world.add_box(size=(1, 0, 1))

    with pytest.raises(ValidationError, match="size"):
        world.add_box(size=(-1, 1, 1))


def test_add_box_invalid_restitution():
    """add_box should raise ValidationError for restitution outside [0, 1]."""
    world = f3d.World()
    with pytest.raises(ValidationError, match="restitution"):
        world.add_box(size=(1, 1, 1), restitution=1.5)

    with pytest.raises(ValidationError, match="restitution"):
        world.add_box(size=(1, 1, 1), restitution=-0.1)


def test_add_box_negative_friction():
    """add_box should raise ValidationError for friction < 0."""
    world = f3d.World()
    with pytest.raises(ValidationError, match="friction"):
        world.add_box(size=(1, 1, 1), friction=-0.1)


# ── add_sphere validation ─────────────────────────────────────────────────────


def test_add_sphere_negative_radius():
    """add_sphere should raise ValidationError for radius <= 0."""
    world = f3d.World()
    with pytest.raises(ValidationError, match="radius"):
        world.add_sphere(radius=-0.5)


def test_add_sphere_negative_mass():
    """add_sphere should raise ValidationError for mass <= 0."""
    world = f3d.World()
    with pytest.raises(ValidationError, match="mass"):
        world.add_sphere(radius=0.5, mass=-1.0)


# ── Error hierarchy ───────────────────────────────────────────────────────────


def test_validation_error_is_value_error():
    """ValidationError should be a subclass of ValueError for compatibility."""
    assert issubclass(ValidationError, ValueError)
    assert issubclass(ValidationError, f3d.Forge3dError)


def test_error_message_format():
    """Error messages should mention the method name and parameter."""
    world = f3d.World()
    try:
        world.add_box(size=(1, 1, 1), mass=-5.0)
        assert False, "Should have raised"
    except ValidationError as e:
        msg = str(e)
        assert "World.add_box" in msg, f"Method name missing: {msg}"
        assert "mass" in msg, f"Parameter name missing: {msg}"


# ── forge3d.__all__ completeness ──────────────────────────────────────────────


def test_all_exports_present():
    """forge3d.__all__ should contain the documented symbols."""
    import forge3d
    expected = {"World", "Body", "Shape", "Material", "App", "Input", "Key",
                "OrbitCamera", "FollowCamera", "Viewer", "Recorder",
                "JointHandle", "CollisionEvent", "CollisionHandler",
                "CollisionLayer", "StateRecorder", "Forge3dError",
                "ValidationError", "__version__"}
    missing = expected - set(forge3d.__all__)
    assert not missing, f"Missing from __all__: {missing}"
