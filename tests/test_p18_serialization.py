"""P18: World serialization (save/load/replay) tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

import forge3d as f3d
from forge3d.io.world_snapshot import StateRecorder, load_world, save_world


def _make_world() -> f3d.World:
    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground()
    world.add_box(size=(1, 1, 1), position=(0, 0, 3), mass=2.0,
                   name="my_box", restitution=0.3, friction=0.5)
    world.add_sphere(radius=0.4, position=(1, 0, 4), mass=0.5, name="my_sphere")
    return world


# ── G1: save produces a JSON file ────────────────────────────────────────────


def test_save_creates_json():
    """World.save() should create a JSON file at the specified path."""
    world = _make_world()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    world.save(path)
    assert Path(path).exists(), "JSON file was not created"
    import json
    data = json.loads(Path(path).read_text())
    assert "bodies" in data
    assert "gravity" in data
    assert isinstance(data["version"], str) and len(data["version"]) > 0


# ── G2: load restores the same body count and positions ───────────────────────


def test_load_restores_world():
    """World.load() should restore body count and approximate positions."""
    world = _make_world()
    positions_before = {b.name: b.position.copy() for b in world.bodies}

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    world.save(path)
    world2 = f3d.World.load(path)

    assert len(world2.bodies) == len(world.bodies), "Body count mismatch after load"

    for body in world2.bodies:
        if body.name in positions_before:
            assert np.allclose(
                body.position, positions_before[body.name], atol=1e-6
            ), f"Position mismatch for {body.name}"


# ── G3: determinism — save, load, step N times → same result ─────────────────


def test_determinism_after_load():
    """Stepping after load should produce the same result as the original."""
    world = _make_world()
    # Pre-step to get interesting state
    for _ in range(30):
        world.step(dt=1 / 120)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    world.save(path)
    world2 = f3d.World.load(path)

    # Step both worlds for 10 more steps
    for _ in range(10):
        world.step(dt=1 / 120)
        world2.step(dt=1 / 120)

    # Compare positions of non-ground bodies
    bodies1 = {b.name: b.position.copy() for b in world.bodies if not b.is_static}
    bodies2 = {b.name: b.position.copy() for b in world2.bodies if not b.is_static}

    for name in bodies1:
        if name in bodies2:
            assert np.allclose(bodies1[name], bodies2[name], atol=1e-4), (
                f"Determinism failed for {name}: {bodies1[name]} vs {bodies2[name]}"
            )


# ── G4: StateRecorder records and positions can be retrieved ─────────────────


def test_state_recorder_records():
    """StateRecorder should capture positions each frame."""
    world = _make_world()
    rec = StateRecorder(world)
    rec.start()

    n_steps = 60
    for _ in range(n_steps):
        world.step(dt=1 / 60)
        rec.record()

    assert len(rec._frames) == n_steps, f"Expected {n_steps} frames, got {len(rec._frames)}"


# ── G5: StateRecorder save and load ───────────────────────────────────────────


def test_state_recorder_save_load():
    """StateRecorder.save() and .load() should work without error."""
    world = _make_world()
    rec = StateRecorder(world)
    rec.start()
    for _ in range(30):
        world.step(dt=1 / 60)
        rec.record()
    rec.stop()

    with tempfile.NamedTemporaryFile(suffix=".states.npz", delete=False) as f:
        path = f.name

    rec.save(path)
    assert Path(path).exists(), ".npz file not created"

    rec2 = StateRecorder.load(path)
    assert hasattr(rec2, "_loaded_data")
    assert rec2._loaded_data.shape[0] == 30  # n_frames


# ── World.load classmethod ────────────────────────────────────────────────────


def test_world_load_classmethod():
    """forge3d.World.load(path) class method should work."""
    world = _make_world()
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    world.save(path)
    world2 = f3d.World.load(path)
    assert isinstance(world2, f3d.World)
    assert len(world2.bodies) > 0
