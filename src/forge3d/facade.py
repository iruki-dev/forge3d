"""forge3d public Facade — World, Body, Shape, Material.

"Easy like pygame, beautiful like simulation."
Coordinate system: z-up, SI units.

Users only need::

    import forge3d as f3d
    world = f3d.World()
    box   = world.add_box(size=(1,1,1), position=(0,0,5))
    while viewer.is_open:
        world.step()
        viewer.draw()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from forge3d.sim.world import PhysicsWorld, _Body

# ── Material ──────────────────────────────────────────────────────────────────


@dataclass
class Material:
    """Surface appearance for a rigid body.

    Color can be a preset name (str) or an RGB tuple in [0, 1].
    Preset names: 'default', 'red', 'blue', 'green', 'orange', 'ground',
                  'gold', 'white'.
    Use ``texture_path`` for an albedo image (PNG/JPEG, loaded at render time).

    Examples
    --------
    >>> Material(color="red")
    >>> Material(color=(0.9, 0.4, 0.1), roughness=0.3)
    >>> Material(color="default", metallic=0.8, roughness=0.2)
    >>> Material(texture_path="wall.png")
    """

    color: Any = "default"  # str preset OR (R, G, B) tuple
    roughness: float = 0.5
    metallic: float = 0.0
    texture_path: str | None = None  # path to albedo texture image
    normal_map_path: str | None = None

    def _material_id(self) -> str:
        """Resolve to a snapshot material ID string."""
        if isinstance(self.color, str) and self.texture_path is None:
            return self.color
        if isinstance(self.color, str):
            from forge3d.render.snapshot import BUILTIN_MATERIALS

            base = BUILTIN_MATERIALS.get(self.color)
            r, g, b = base.color if base else (0.75, 0.75, 0.75)
        else:
            r, g, b = self.color
        suffix = f"_{hash(self.texture_path) & 0xFFFF:04x}" if self.texture_path else ""
        return f"custom#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}{suffix}"

    def _to_snapshot_material(self) -> Any:
        from forge3d.render.snapshot import Material as SM

        if isinstance(self.color, str):
            from forge3d.render.snapshot import BUILTIN_MATERIALS

            base = BUILTIN_MATERIALS.get(self.color)
            return SM(
                color=base.color if base else (0.75, 0.75, 0.75),
                roughness=self.roughness,
                metallic=self.metallic,
                texture_path=self.texture_path,
                normal_map_path=self.normal_map_path,
            )
        return SM(
            color=tuple(self.color),
            roughness=self.roughness,
            metallic=self.metallic,
            texture_path=self.texture_path,
            normal_map_path=self.normal_map_path,
        )


# ── Shape ─────────────────────────────────────────────────────────────────────


@dataclass
class Shape:
    """Collision / visual shape descriptor.

    Create via factory methods::

        Shape.box(size=(1, 1, 1))
        Shape.sphere(radius=0.5)
        Shape.capsule(radius=0.2, half_length=0.5)
        Shape.convex_mesh(mesh_data)   # MeshData from load_obj()
    """

    type: str
    params: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def box(size: Any = (1.0, 1.0, 1.0)) -> Shape:
        """Box shape with half-extents derived from *size*."""
        sx, sy, sz = size
        return Shape("box", {"half_extents": np.array([sx / 2, sy / 2, sz / 2])})

    @staticmethod
    def sphere(radius: float = 0.5) -> Shape:
        """Sphere shape."""
        return Shape("sphere", {"radius": float(radius)})

    @staticmethod
    def capsule(radius: float = 0.2, half_length: float = 0.5) -> Shape:
        """Capsule shape (cylinder + hemispherical end-caps, axis = body +Z)."""
        return Shape("capsule", {"radius": float(radius), "half_length": float(half_length)})

    @staticmethod
    def convex_mesh(mesh_data: Any) -> Shape:
        """Convex-hull collision shape from a MeshData object.

        Load mesh data with::

            from forge3d.io import load_obj
            mesh = load_obj("model.obj")
            shape = Shape.convex_mesh(mesh)
        """
        return Shape("mesh", {"mesh_data": mesh_data})


# ── Body ──────────────────────────────────────────────────────────────────────


class Body:
    """Handle to a simulated rigid body.

    Returned by ``world.add_box()``, ``world.add_sphere()``, etc.
    Use properties to read the body's current state and methods to control it.

    Examples
    --------
    >>> box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), name="my_box")
    >>> box.position
    array([0., 0., 5.])
    >>> box.name
    'my_box'
    >>> box.apply_force((0, 0, 10))     # applied on next world.step()
    """

    def __init__(self, physics_world: PhysicsWorld, body_id: int) -> None:
        self._pw = physics_world
        self._id = body_id
        # Pending per-frame force/torque accumulators (applied by World.step)
        self._force_accum: np.ndarray = np.zeros(3)
        self._torque_accum: np.ndarray = np.zeros(3)

    def _state(self) -> _Body:
        return self._pw._get_body(self._id)

    # ── Read-only state ───────────────────────────────────────────────────────

    @property
    def position(self) -> np.ndarray:
        """World-frame position (3,) in metres."""
        return self._state().pos.copy()

    @property
    def velocity(self) -> np.ndarray:
        """Linear velocity (3,) in m/s."""
        return self._state().vel.copy()

    @property
    def orientation(self) -> np.ndarray:
        """Unit quaternion [w, x, y, z]."""
        return self._state().quat.copy()

    @property
    def angular_velocity(self) -> np.ndarray:
        """Angular velocity (3,) in rad/s."""
        return self._state().omega.copy()

    @property
    def name(self) -> str:
        """Human-readable name assigned at creation."""
        return self._state().name

    @property
    def is_static(self) -> bool:
        """True if this body does not move under physics forces."""
        return self._state().static

    @property
    def mass(self) -> float:
        """Body mass in kg (0.0 for static bodies)."""
        return self._state().mass

    # ── Control ───────────────────────────────────────────────────────────────

    def apply_force(self, force: Any) -> None:
        """Accumulate a world-frame force (N) to apply on the next step.

        Forces reset to zero after each :meth:`World.step` call.

        Parameters
        ----------
        force : (3,) force vector in Newtons, world frame.

        Notes
        -----
        For per-frame forces use this instead of ``apply_impulse``::

            body.apply_force(np.array([0, 0, 50]))   # 50 N upward thrust
            world.step(dt=1/60)                       # force applied here
        """
        self._force_accum = self._force_accum + np.asarray(force, dtype=float)

    def apply_torque(self, torque: Any) -> None:
        """Accumulate a world-frame torque (N·m) to apply on the next step.

        Torques reset to zero after each :meth:`World.step` call.
        """
        self._torque_accum = self._torque_accum + np.asarray(torque, dtype=float)

    def set_position(self, position: Any) -> None:
        """Instantly teleport this body to *position* (keeps orientation)."""
        b = self._state()
        self._pw.update_body_pose(self._id, np.asarray(position, dtype=float), b.quat)

    def set_orientation(self, quat: Any) -> None:
        """Instantly set orientation (keeps position).  quat = [w, x, y, z]."""
        b = self._state()
        self._pw.update_body_pose(self._id, b.pos, np.asarray(quat, dtype=float))

    def set_velocity(self, vel: Any) -> None:
        """Override linear velocity (m/s)."""
        b = self._state()
        from dataclasses import replace

        self._pw._replace_body(self._id, replace(b, vel=np.asarray(vel, dtype=float)))

    def set_angular_velocity(self, omega: Any) -> None:
        """Override angular velocity (rad/s)."""
        b = self._state()
        from dataclasses import replace

        self._pw._replace_body(self._id, replace(b, omega=np.asarray(omega, dtype=float)))

    def _flush_accumulators(self, dt: float) -> None:
        """Apply accumulated force/torque as impulses (called by World.step)."""
        if np.any(self._force_accum != 0):
            b = self._state()
            if not b.static and b.mass > 0.0:
                dv = self._force_accum * dt / b.mass
                self._pw.apply_impulse(self._id, dv * b.mass)
            self._force_accum = np.zeros(3)
        if np.any(self._torque_accum != 0):
            b = self._state()
            if not b.static and b.inertia_inv_local is not None:
                from forge3d.math.quaternion import quat_to_rot

                R = quat_to_rot(b.quat)
                I_world_inv = R @ b.inertia_inv_local @ R.T
                d_omega = I_world_inv @ self._torque_accum * dt
                from dataclasses import replace

                self._pw._replace_body(
                    self._id, replace(b, omega=b.omega + d_omega)
                )
            self._torque_accum = np.zeros(3)

    def __repr__(self) -> str:
        try:
            p = self.position
            return (
                f"Body(id={self._id}, name={self.name!r}, "
                f"pos=({p[0]:.2f}, {p[1]:.2f}, {p[2]:.2f}))"
            )
        except Exception:
            return f"Body(id={self._id})"


# ── World ─────────────────────────────────────────────────────────────────────


class World:
    """forge3d physics world — pygame-style public API.

    Coordinate system: z-up, SI units.  Start here::

        world = forge3d.World()
        world.add_ground()
        box = world.add_box(size=(1, 1, 1), position=(0, 0, 5))
        world.step()          # advances by default_dt=1/60 s
        snap = world.snapshot()

    The internal ``PhysicsWorld`` is accessible via ``world._physics`` for
    advanced use, but the public API never needs it.
    """

    DEFAULT_DT: float = 1.0 / 60.0

    def __init__(self, gravity: Any = (0.0, 0.0, -9.81)) -> None:
        self._physics = PhysicsWorld(gravity=list(gravity))
        self._bodies: dict[int, Body] = {}
        self._materials: dict[str, Material] = {}
        self._camera: tuple | None = None
        self._robots: list[Any] = []
        self._welds: dict[int, tuple[int, np.ndarray]] = {}

    # ── Scene construction ────────────────────────────────────────────────────

    def add_ground(
        self,
        material: Material | str = "ground",
        size: Any = (40.0, 40.0, 0.2),
        height: float = 0.0,
    ) -> Body:
        """Add a static ground plane.  By default: 40×40 m slab at z=0."""
        mat_id, mat = _resolve_material(material)
        if mat:
            self._materials[mat_id] = mat
        bid = self._physics.add_static_box(
            size=size,
            position=(0.0, 0.0, height - size[2] / 2),
            material=mat_id,
            name="ground",
        )
        body = Body(self._physics, bid)
        self._bodies[bid] = body
        return body

    def add_box(
        self,
        size: Any = (1.0, 1.0, 1.0),
        position: Any = (0.0, 0.0, 0.0),
        mass: float = 1.0,
        material: Material | str = "default",
        name: str = "",
        restitution: float = 0.3,
        friction: float = 0.5,
    ) -> Body:
        """Add a box-shaped rigid body."""
        mat_id, mat = _resolve_material(material)
        if mat:
            self._materials[mat_id] = mat
        bid = self._physics.add_box(
            size=size,
            position=position,
            mass=mass,
            material=mat_id,
            name=name,
            restitution=restitution,
            friction=friction,
        )
        body = Body(self._physics, bid)
        self._bodies[bid] = body
        return body

    def add_capsule(
        self,
        radius: float = 0.2,
        half_length: float = 0.5,
        position: Any = (0.0, 0.0, 0.0),
        quat: Any = None,
        mass: float = 1.0,
        material: Material | str = "default",
        name: str = "",
        restitution: float = 0.3,
        friction: float = 0.5,
    ) -> Body:
        """Add a capsule-shaped rigid body (cylinder + two hemispherical caps).

        The capsule axis is aligned with body-local +Z.  Use ``quat`` to orient it.
        """
        mat_id, mat = _resolve_material(material)
        if mat:
            self._materials[mat_id] = mat
        bid = self._physics.add_capsule(
            radius=radius,
            half_length=half_length,
            position=position,
            quat=quat,
            mass=mass,
            material=mat_id,
            name=name,
            restitution=restitution,
            friction=friction,
        )
        body = Body(self._physics, bid)
        self._bodies[bid] = body
        return body

    def add_mesh(
        self,
        mesh_data: Any,
        position: Any = (0.0, 0.0, 0.0),
        quat: Any = None,
        mass: float = 1.0,
        material: Material | str = "default",
        name: str = "",
        restitution: float = 0.3,
        friction: float = 0.5,
        static: bool = False,
    ) -> Body:
        """Add a convex-hull rigid body from a MeshData object.

        Typical use::

            from forge3d.io import load_obj
            mesh = load_obj("assets/models/cube.obj")
            body = world.add_mesh(mesh, position=(0, 0, 3), mass=1.0)
        """
        mat_id, mat = _resolve_material(material)
        if mat:
            self._materials[mat_id] = mat
        bid = self._physics.add_convex_mesh(
            mesh_data=mesh_data,
            position=position,
            quat=quat,
            mass=mass,
            material=mat_id,
            name=name,
            restitution=restitution,
            friction=friction,
            static=static,
        )
        body = Body(self._physics, bid)
        self._bodies[bid] = body
        return body

    def add_sphere(
        self,
        radius: float = 0.5,
        position: Any = (0.0, 0.0, 0.0),
        mass: float = 1.0,
        material: Material | str = "default",
        name: str = "",
        restitution: float = 0.3,
        friction: float = 0.5,
        static: bool = False,
    ) -> Body:
        """Add a sphere-shaped rigid body.

        ``static=True`` creates a non-moving marker (e.g. target visualization).
        """
        mat_id, mat = _resolve_material(material)
        if mat:
            self._materials[mat_id] = mat
        bid = self._physics.add_sphere(
            radius=radius,
            position=position,
            mass=mass,
            material=mat_id,
            name=name,
            restitution=restitution,
            friction=friction,
            static=static,
        )
        body = Body(self._physics, bid)
        self._bodies[bid] = body
        return body

    def add(self, obj: Any) -> Any:
        """Add a Body or Robot to the world.  Returns the object passed in."""
        if isinstance(obj, Body):
            bid = obj._id
            if bid not in self._bodies:
                self._bodies[bid] = obj
            return obj
        if hasattr(obj, "n_joints") and hasattr(obj, "link_visual_boxes"):
            return self._add_robot(obj)
        raise TypeError(f"world.add() expects a Body or Robot, got {type(obj).__name__}.")

    def _add_robot(self, robot: Any) -> Any:
        from forge3d.math.quaternion import quat_from_rot

        boxes = robot.link_visual_boxes()
        for i, (center, R, he) in enumerate(boxes):
            quat = quat_from_rot(R)
            bid = self._physics.add_static_box(
                size=tuple(float(v) for v in he * 2),
                position=tuple(float(v) for v in center),
                material=robot.material,
                name=f"{robot.name}_link{i}",
                restitution=0.0,
                friction=0.5,
                quat=quat,
            )
            robot._body_ids.append(bid)
        self._robots.append(robot)
        return robot

    # ── Scene query ───────────────────────────────────────────────────────────

    @property
    def bodies(self) -> list[Body]:
        """All body handles currently in the world (order: insertion)."""
        return list(self._bodies.values())

    def get_body(self, name: str) -> Body:
        """Return the first body with *name*.

        Raises
        ------
        KeyError
            If no body with that name exists.
        """
        for body in self._bodies.values():
            try:
                if body.name == name:
                    return body
            except Exception:
                pass
        raise KeyError(f"No body named '{name}' in world. "
                       f"Available: {[b.name for b in self.bodies]}")

    # ── Scene mutation ────────────────────────────────────────────────────────

    def remove(self, body: Body) -> None:
        """Remove a body from the simulation.

        The body handle becomes stale after this call.

        Parameters
        ----------
        body : Body handle returned by an add_* method.
        """
        bid = body._id
        self._physics.remove_body(bid)
        self._bodies.pop(bid, None)
        self._welds.pop(bid, None)

    def clear(self, keep_statics: bool = False) -> None:
        """Remove all bodies from the world.

        Parameters
        ----------
        keep_statics : If True, static bodies (ground planes, robot links)
                       are kept; only dynamic bodies are removed.
        """
        to_remove = []
        for bid, body in list(self._bodies.items()):
            try:
                is_static = body.is_static
            except Exception:
                is_static = False
            if keep_statics and is_static:
                continue
            to_remove.append(bid)

        for bid in to_remove:
            self._physics.remove_body(bid)
            self._bodies.pop(bid, None)
            self._welds.pop(bid, None)

    # ── Physical interactions ─────────────────────────────────────────────────

    def apply_impulse(self, body: Body, impulse: Any) -> None:
        """Apply an instantaneous velocity impulse to *body* (Δv = impulse / mass).

        Use this to apply per-frame forces from a game loop::

            # Apply force F for time dt:
            world.apply_impulse(ball, np.array([F_x, F_y, 0]) * dt)
            world.step(dt)
        """
        self._physics.apply_impulse(body._id, impulse)

    def teleport(
        self,
        body: Body,
        position: Any,
        quat: Any = None,
    ) -> None:
        """Instantly move a body to a new position (and optionally orientation)."""
        b = body._state()
        q = b.quat.copy() if quat is None else np.asarray(quat, dtype=float)
        self._physics.update_body_pose(body._id, np.asarray(position, dtype=float), q)

    def weld(
        self,
        body: Body,
        anchor: Body,
        local_offset: Any = None,
    ) -> None:
        """Attach *body* kinematically to *anchor* (weld constraint).

        After welding, ``body`` will follow ``anchor`` rigidly each ``step()``.
        """
        from forge3d.math.quaternion import quat_to_rot

        if local_offset is None:
            a_state = anchor._state()
            b_state = body._state()
            R_anchor = quat_to_rot(a_state.quat)
            local_offset = R_anchor.T @ (b_state.pos - a_state.pos)
        self._welds[body._id] = (anchor._id, np.asarray(local_offset, dtype=float))

    def release(self, body: Body) -> None:
        """Remove weld constraint from *body* (body resumes normal physics)."""
        self._welds.pop(body._id, None)

    def set_camera(
        self,
        position: Any,
        target: Any = (0.0, 0.0, 0.0),
        up: Any = (0.0, 0.0, 1.0),
        fov_deg: float = 45.0,
    ) -> None:
        """Set the default camera pose for snapshots and the Viewer."""
        self._physics.set_camera(position, target, up, fov_deg)
        self._camera = (position, target, up, fov_deg)

    # ── Simulation ────────────────────────────────────────────────────────────

    def step(self, dt: float | None = None) -> None:
        """Advance simulation by dt seconds (default: 1/60 s).

        1. Flush per-body force/torque accumulators (apply_force / apply_torque).
        2. Physics step (gravity → contacts → impulses → position update).
        3. Apply weld constraints.
        """
        _dt = dt if dt is not None else self.DEFAULT_DT
        # Flush accumulators before physics step
        for body in self._bodies.values():
            if body._force_accum is not None and (
                np.any(body._force_accum != 0) or np.any(body._torque_accum != 0)
            ):
                body._flush_accumulators(_dt)
        self._physics.step(_dt)
        self._apply_welds()

    def _apply_welds(self) -> None:
        if not self._welds:
            return
        from forge3d.math.quaternion import quat_to_rot

        _ZEROS3 = np.zeros(3)
        for body_id, (anchor_id, offset) in self._welds.items():
            try:
                anchor = self._physics._get_body(anchor_id)
            except RuntimeError:
                continue
            R_anchor = quat_to_rot(anchor.quat)
            new_pos = anchor.pos + R_anchor @ offset
            self._physics.update_body_pose(
                body_id, new_pos, anchor.quat, vel=_ZEROS3, omega=_ZEROS3
            )

    def _sync_robot(self, robot: Any) -> None:
        from forge3d.math.quaternion import quat_from_rot

        boxes = robot.link_visual_boxes()
        for bid, (center, R, _he) in zip(robot._body_ids, boxes, strict=True):
            quat = quat_from_rot(R)
            self._physics.update_body_pose(bid, center, quat)

    @property
    def time(self) -> float:
        """Elapsed simulation time in seconds."""
        return self._physics.time

    # ── SceneSnapshot ─────────────────────────────────────────────────────────

    def snapshot(self) -> Any:
        """Build a SceneSnapshot for the current state (used by Viewer/Recorder)."""
        for robot in self._robots:
            self._sync_robot(robot)

        snap = self._physics.snapshot()

        for mat_id, mat in self._materials.items():
            if mat_id not in snap.materials:
                snap.materials[mat_id] = mat._to_snapshot_material()

        return snap

    def __repr__(self) -> str:
        return (
            f"World(t={self.time:.3f}s, "
            f"bodies={len(self._physics._bodies)}, "
            f"gravity={self._physics._gravity.tolist()})"
        )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _resolve_material(m: Material | str) -> tuple[str, Material | None]:
    """Return (material_id, Material|None) from a Material object or string."""
    if isinstance(m, str):
        return m, None
    if isinstance(m, Material):
        return m._material_id(), m
    raise TypeError(
        f"material must be a str preset name or a Material object, "
        f"got {type(m).__name__!r}.  "
        f"Valid presets: 'default', 'red', 'blue', 'green', 'orange', 'ground', 'gold', 'white'."
    )
