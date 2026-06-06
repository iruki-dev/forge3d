"""World serialization — save and load forge3d worlds to/from JSON.

Design:
  - ``World.save(path)``  → writes a JSON file describing all bodies.
  - ``World.load(path)``  → creates a fresh World with the same bodies.
  - ``StateRecorder``     → records per-step body states to an npz file
                             and can replay them back.

The JSON format is human-readable and version-stamped:

    {
      "version": "0.4.0",
      "gravity": [0, 0, -9.81],
      "time": 1.234,
      "bodies": [ ... ]
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    pass


# ── JSON save / load ───────────────────────────────────────────────────────────


def save_world(world: Any, path: str | Path) -> None:
    """Serialize the current world state to a JSON file.

    Args:
        world: A :class:`forge3d.World` instance.
        path: Output file path (e.g. ``"world.json"``).
    """
    from forge3d import __version__

    bodies_data = []
    for body in world.bodies:
        try:
            state = body._state()
        except Exception:
            continue

        shape_params_serializable: dict[str, Any] = {}
        for k, v in state.shape_params.items():
            if isinstance(v, np.ndarray):
                shape_params_serializable[k] = v.tolist()
            elif isinstance(v, (int, float, str, bool)):
                shape_params_serializable[k] = v
            # skip non-serializable objects (e.g. MeshData)

        bodies_data.append(
            {
                "id": state.body_id,
                "name": state.name,
                "shape_type": state.shape_type,
                "shape_params": shape_params_serializable,
                "position": state.pos.tolist(),
                "orientation": state.quat.tolist(),
                "velocity": state.vel.tolist(),
                "angular_velocity": state.omega.tolist(),
                "mass": state.mass,
                "restitution": state.restitution,
                "friction": state.friction,
                "is_static": state.static,
                "material": state.material_id,
            }
        )

    # Serialize constraints (joints)
    constraints_data = []
    for c in world._physics._constraints:
        ctype = type(c).__name__
        try:
            entry: dict[str, Any] = {"type": ctype, "id_a": c.id_a, "id_b": c.id_b}
            # Common anchors
            if hasattr(c, "anchor_a"):
                entry["anchor_a"] = np.asarray(c.anchor_a).tolist()
            if hasattr(c, "anchor_b"):
                entry["anchor_b"] = np.asarray(c.anchor_b).tolist()
            # Joint-type specifics
            if ctype == "HingeJoint":
                entry["axis"] = np.asarray(c.axis_a).tolist()  # stored as axis_a
                entry["limits"] = list(c.limits) if c.limits is not None else None
                entry["motor_velocity"] = c.motor_velocity
                entry["motor_max_torque"] = c.motor_max_torque
            elif ctype == "PrismaticJoint":
                axis = getattr(c, "axis_a", None) or getattr(c, "axis", None)
                entry["axis"] = np.asarray(axis).tolist() if axis is not None else [0, 0, 1]
                entry["limits"] = list(c.limits) if c.limits is not None else None
                entry["motor_velocity"] = c.motor_velocity
                entry["motor_max_force"] = c.motor_max_force
            elif ctype == "SpringJoint":
                entry["stiffness"] = c.stiffness
                entry["damping"] = c.damping
                entry["rest_length"] = c.rest_length
            elif ctype == "DistanceJoint":
                entry["target_distance"] = c.target_distance
            constraints_data.append(entry)
        except Exception:
            pass

    data = {
        "version": __version__,
        "gravity": world._physics._gravity.tolist(),
        "time": float(world.time),
        "bodies": bodies_data,
        "constraints": constraints_data,
    }

    path = Path(path)
    path.write_text(json.dumps(data, indent=2))


def load_world(path: str | Path) -> Any:
    """Load a world from a JSON file previously created by :func:`save_world`.

    Args:
        path: Path to a JSON file created by :meth:`forge3d.World.save`.

    Returns:
        A new :class:`forge3d.World` instance with all bodies restored.
    """
    import forge3d as f3d

    path = Path(path)
    data = json.loads(path.read_text())

    gravity = tuple(data.get("gravity", [0.0, 0.0, -9.81]))
    world = f3d.World(gravity=gravity)
    world._physics._time = float(data.get("time", 0.0))

    for b in data.get("bodies", []):
        shape_type = b["shape_type"]
        sp = b.get("shape_params", {})
        mass = float(b.get("mass", 1.0))
        pos = tuple(b.get("position", [0, 0, 0]))
        mat = b.get("material", "default")
        name = b.get("name", "")
        rest = float(b.get("restitution", 0.3))
        fric = float(b.get("friction", 0.5))
        is_static = bool(b.get("is_static", False))
        quat = b.get("orientation", [1, 0, 0, 0])
        vel = b.get("velocity", [0, 0, 0])
        omega = b.get("angular_velocity", [0, 0, 0])

        body: Any = None
        if shape_type == "box":
            he = sp.get("half_extents", [0.5, 0.5, 0.5])
            size = [2 * h for h in he]
            if is_static:
                bid = world._physics.add_static_box(
                    size=size,
                    position=pos,
                    material=mat,
                    name=name,
                    restitution=rest,
                    friction=fric,
                )
                body = f3d.Body(world._physics, bid)
                world._bodies[bid] = body
            else:
                body = world.add_box(
                    size=size,
                    position=pos,
                    mass=mass,
                    material=mat,
                    name=name,
                    restitution=rest,
                    friction=fric,
                )

        elif shape_type == "sphere":
            radius = float(sp.get("radius", 0.5))
            body = world.add_sphere(
                radius=radius,
                position=pos,
                mass=mass,
                material=mat,
                name=name,
                restitution=rest,
                friction=fric,
                static=is_static,
            )

        elif shape_type == "capsule":
            radius = float(sp.get("radius", 0.2))
            half_length = float(sp.get("half_length", 0.5))
            body = world.add_capsule(
                radius=radius,
                half_length=half_length,
                position=pos,
                mass=mass,
                material=mat,
                name=name,
                restitution=rest,
                friction=fric,
            )

        if body is not None:
            # Restore orientation and velocity
            from dataclasses import replace as _replace

            state = body._state()
            world._physics._replace_body(
                state.body_id,
                _replace(
                    state,
                    quat=np.asarray(quat, dtype=float),
                    vel=np.asarray(vel, dtype=float),
                    omega=np.asarray(omega, dtype=float),
                ),
            )

    # Restore joints / constraints
    for c in data.get("constraints", []):
        try:
            ctype = c.get("type", "")
            jtype_map = {
                "FixedJoint": "fixed",
                "BallJoint": "ball",
                "HingeJoint": "hinge",
                "PrismaticJoint": "prismatic",
                "DistanceJoint": "distance",
                "SpringJoint": "spring",
            }
            jtype = jtype_map.get(ctype)
            if jtype is None:
                continue

            id_a = int(c["id_a"])
            id_b = int(c.get("id_b", -1))

            # Find facade bodies by physics id
            body_a = world._bodies.get(id_a)
            body_b = world._bodies.get(id_b) if id_b >= 0 else None
            if body_a is None:
                continue

            kwargs: dict[str, Any] = {
                "joint_type": jtype,
                "body_a": body_a,
                "body_b": body_b,
                "anchor_a": c.get("anchor_a", [0, 0, 0]),
                "anchor_b": c.get("anchor_b", [0, 0, 0]),
            }
            if "axis" in c:
                kwargs["axis"] = c["axis"]
            if c.get("limits") is not None:
                kwargs["limits"] = tuple(c["limits"])
            if "motor_velocity" in c:
                kwargs["motor_velocity"] = c["motor_velocity"]
            if "motor_max_torque" in c:
                kwargs["motor_max_torque"] = c["motor_max_torque"]
            if "motor_max_force" in c:
                kwargs["motor_max_torque"] = c["motor_max_force"]
            if "stiffness" in c:
                kwargs["stiffness"] = c["stiffness"]
            if "damping" in c:
                kwargs["damping"] = c["damping"]
            if "rest_length" in c:
                kwargs["rest_length"] = c["rest_length"]
            if "target_distance" in c:
                kwargs["target_distance"] = c["target_distance"]

            world.add_joint(**kwargs)
        except Exception:
            pass

    return world


# ── StateRecorder ─────────────────────────────────────────────────────────────


class StateRecorder:
    """Records per-step body states and replays them.

    Usage::

        rec = StateRecorder(world)
        rec.start()
        for _ in range(1000):
            world.step()
            rec.record()
        rec.save("sim.states")

    Replay::

        world2 = World.load("world.json")
        rec2 = StateRecorder.load("sim.states")
        rec2.replay(world2)
    """

    def __init__(self, world: Any) -> None:
        self._world = world
        self._frames: list[dict[int, np.ndarray]] = []  # body_id → [pos,quat,vel,omega]
        self._recording = False
        self._loaded_data: np.ndarray | None = None
        self._loaded_body_ids: np.ndarray | None = None
        self._id_to_idx: dict[int, int] = {}

    def start(self) -> None:
        self._frames.clear()
        self._recording = True

    def record(self) -> None:
        """Capture current body states (call after each world.step())."""
        if not self._recording:
            return
        frame: dict[int, np.ndarray] = {}
        for body in self._world.bodies:
            try:
                s = body._state()
                frame[s.body_id] = np.concatenate([s.pos, s.quat, s.vel, s.omega])
            except Exception:
                pass
        self._frames.append(frame)

    def stop(self) -> None:
        self._recording = False

    def save(self, path: str | Path) -> None:
        """Save recorded states to a compressed npz file."""
        path = Path(path)
        n_frames = len(self._frames)
        if n_frames == 0:
            return

        # Collect all body ids that appear in any frame
        all_ids = sorted({bid for frame in self._frames for bid in frame})
        n_bodies = len(all_ids)
        id_to_idx = {bid: i for i, bid in enumerate(all_ids)}

        data = np.full((n_frames, n_bodies, 13), np.nan, dtype=np.float64)
        for f_idx, frame in enumerate(self._frames):
            for bid, state_vec in frame.items():
                b_idx = id_to_idx[bid]
                data[f_idx, b_idx] = state_vec

        np.savez_compressed(
            str(path),
            data=data,
            body_ids=np.array(all_ids, dtype=np.int64),
        )

    @classmethod
    def load(cls, path: str | Path) -> StateRecorder:
        """Load recorded states from an npz file."""
        path = Path(path)
        npz = np.load(str(path))
        data: np.ndarray = npz["data"]
        body_ids: np.ndarray = npz["body_ids"]

        n_frames, n_bodies, _ = data.shape
        id_to_idx = {int(bid): i for i, bid in enumerate(body_ids)}

        rec = cls(world=None)  # type: ignore[arg-type]
        rec._loaded_data = data
        rec._loaded_body_ids = body_ids
        rec._id_to_idx = id_to_idx
        return rec

    def replay(self, world: Any, dt: float = 1 / 60) -> None:
        """Teleport bodies to recorded positions each frame.

        Args:
            world: Target world to replay into.
            dt: Simulated time between frames (informational only).
        """
        if self._loaded_data is None:
            raise RuntimeError("No loaded data — call StateRecorder.load() first.")

        data = self._loaded_data
        id_to_idx = self._id_to_idx

        for frame_data in data:
            for body in world.bodies:
                try:
                    bid = body._state().body_id
                    if bid not in id_to_idx:
                        continue
                    b_idx = id_to_idx[bid]
                    row = frame_data[b_idx]
                    if np.any(np.isnan(row)):
                        continue
                    pos = row[0:3]
                    quat = row[3:7]
                    vel = row[7:10]
                    omega = row[10:13]
                    world._physics.update_body_pose(bid, pos, quat, vel=vel, omega=omega)
                except Exception:
                    pass
