"""forge3d public Facade — World, Body, Shape, Material.

"Fast like native, beautiful like simulation."
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
    emissive: float = 0.0  # emissive glow intensity (0 = none)
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
                emissive=self.emissive,
                texture_path=self.texture_path,
                normal_map_path=self.normal_map_path,
            )
        return SM(
            color=tuple(self.color),
            roughness=self.roughness,
            metallic=self.metallic,
            emissive=self.emissive,
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
        # Per-body velocity damping (applied by World.step, per second)
        self._linear_damping: float = 0.0
        self._angular_damping: float = 0.0
        # Back-reference to World (set by World after creation) for per-body callbacks
        self._world_ref: Any = None

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
        """Human-readable name assigned at creation.  Can be changed at runtime."""
        return self._state().name

    @name.setter
    def name(self, value: str) -> None:
        from dataclasses import replace

        b = self._state()
        self._pw._replace_body(self._id, replace(b, name=str(value)))

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

    # ── Runtime physics property setters ─────────────────────────────────────

    @property
    def friction(self) -> float:
        """Coulomb friction coefficient (>= 0). Can be changed at runtime."""
        return self._state().friction

    @friction.setter
    def friction(self, value: float) -> None:
        from dataclasses import replace

        b = self._state()
        self._pw._replace_body(self._id, replace(b, friction=max(0.0, float(value))))

    @property
    def restitution(self) -> float:
        """Coefficient of restitution [0, 1]. Can be changed at runtime."""
        return self._state().restitution

    @restitution.setter
    def restitution(self, value: float) -> None:
        from dataclasses import replace

        b = self._state()
        self._pw._replace_body(self._id, replace(b, restitution=float(np.clip(value, 0.0, 1.0))))

    @property
    def linear_damping(self) -> float:
        """Linear velocity damping coefficient (per second, >= 0).

        Applied automatically each ``world.step()``.  A value of 0.1 removes
        ~10% of linear velocity per second.
        """
        return self._linear_damping

    @linear_damping.setter
    def linear_damping(self, value: float) -> None:
        self._linear_damping = max(0.0, float(value))

    @property
    def angular_damping(self) -> float:
        """Angular velocity damping coefficient (per second, >= 0).

        Applied automatically each ``world.step()``.
        """
        return self._angular_damping

    @angular_damping.setter
    def angular_damping(self, value: float) -> None:
        self._angular_damping = max(0.0, float(value))

    @property
    def shape_type(self) -> str:
        """Shape kind: ``'box'``, ``'sphere'``, ``'capsule'``, ``'mesh'``, etc."""
        return self._state().shape_type

    @property
    def shape_params(self) -> dict:
        """Shape parameters dict (e.g. ``{'half_extents': array([0.5, 0.5, 0.5])}``).

        Returns a copy — mutating the dict does not affect the simulation.
        """
        sp = self._state().shape_params
        return {k: (v.copy() if hasattr(v, "copy") else v) for k, v in sp.items()}

    @property
    def rotation_matrix(self) -> np.ndarray:
        """Body orientation as a 3×3 rotation matrix (world frame)."""
        from forge3d.math.quaternion import quat_to_rot

        return quat_to_rot(self._state().quat)

    @property
    def is_sleeping(self) -> bool:
        """True if this body is below the sleep velocity threshold for ≥ 1 s."""
        return self._pw.is_sleeping(self._id)

    @property
    def collision_layer(self) -> int:
        """Bit-field: which layer(s) this body belongs to."""
        return self._state().collision_layer

    @collision_layer.setter
    def collision_layer(self, value: int) -> None:
        from dataclasses import replace

        b = self._state()
        self._pw._replace_body(self._id, replace(b, collision_layer=int(value)))

    @property
    def collision_mask(self) -> int:
        """Bit-field: which layers this body detects collisions with."""
        return self._state().collision_mask

    @collision_mask.setter
    def collision_mask(self, value: int) -> None:
        from dataclasses import replace

        b = self._state()
        self._pw._replace_body(self._id, replace(b, collision_mask=int(value)))

    # ── Per-body collision callbacks ───────────────────────────────────────────

    def on_collision_begin(self, fn: Any) -> Any:
        """Register a callback fired when this body first contacts another.

        The callback receives ``(other: Body, event: CollisionEvent)``.

        Can be used as a decorator::

            @player.on_collision_begin
            def hit(other, event):
                print(f"player hit {other.name}")
        """
        if self._world_ref is not None:
            self._world_ref._events.add_body_begin_listener(self._id, fn)
        return fn

    def on_collision_end(self, fn: Any) -> Any:
        """Register a callback fired when this body separates from another."""
        if self._world_ref is not None:
            self._world_ref._events.add_body_end_listener(self._id, fn)
        return fn

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

                self._pw._replace_body(self._id, replace(b, omega=b.omega + d_omega))
            self._torque_accum = np.zeros(3)

    def __repr__(self) -> str:
        try:
            p = self.position
            return (
                f"Body(id={self._id}, name={self.name!r}, pos=({p[0]:.2f}, {p[1]:.2f}, {p[2]:.2f}))"
            )
        except Exception:
            return f"Body(id={self._id})"


# ── World ─────────────────────────────────────────────────────────────────────


class World:
    """forge3d physics world — minimal public API.

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
        from forge3d.errors import require_sequence

        require_sequence(gravity, 3, "gravity", "World()")
        self._physics = PhysicsWorld(gravity=list(gravity))
        self._bodies: dict[int, Body] = {}
        self._materials: dict[str, Material] = {}
        self._camera: tuple | None = None
        self._robots: list[Any] = []
        self._welds: dict[int, tuple[int, np.ndarray]] = {}
        # Event system
        from forge3d.events import EventDispatcher

        self._events = EventDispatcher()
        # Collision ignore set: frozenset of (id_a, id_b) pairs
        self._ignored_pairs: set[frozenset[int]] = set()

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
        self._register_body(body)
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
        static: bool = False,
    ) -> Body:
        """Add a box-shaped rigid body.

        Parameters
        ----------
        static : If True, creates an immovable static box (mass is ignored).
        """
        from forge3d.errors import (
            require_all_positive,
            require_nonneg,
            require_positive,
            require_range,
            require_sequence,
        )

        require_sequence(size, 3, "size", "World.add_box()")
        require_all_positive(size, "size", "World.add_box()")
        require_range(float(restitution), 0.0, 1.0, "restitution", "World.add_box()")
        require_nonneg(float(friction), "friction", "World.add_box()")
        if not static:
            require_positive(float(mass), "mass", "World.add_box()")
        mat_id, mat = _resolve_material(material)
        if mat:
            self._materials[mat_id] = mat
        if static:
            bid = self._physics.add_static_box(
                size=size,
                position=position,
                material=mat_id,
                name=name,
                restitution=restitution,
                friction=friction,
            )
        else:
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
        self._register_body(body)
        return body

    def add_static_box(
        self,
        size: Any = (1.0, 1.0, 1.0),
        position: Any = (0.0, 0.0, 0.0),
        material: Material | str = "default",
        name: str = "",
        restitution: float = 0.3,
        friction: float = 0.5,
    ) -> Body:
        """Add a static (non-moving) box and register it in world.bodies.

        Equivalent to ``add_box(..., static=True)`` — exposes ``_physics.add_static_box``
        as a properly tracked public method.
        """
        mat_id, mat = _resolve_material(material)
        if mat:
            self._materials[mat_id] = mat
        bid = self._physics.add_static_box(
            size=size,
            position=position,
            material=mat_id,
            name=name,
            restitution=restitution,
            friction=friction,
        )
        body = Body(self._physics, bid)
        self._register_body(body)
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
        static: bool = False,
    ) -> Body:
        """Add a capsule-shaped rigid body (cylinder + two hemispherical caps).

        The capsule axis is aligned with body-local +Z.  Use ``quat`` to orient it.

        Parameters
        ----------
        static : If True, creates an immovable static capsule.
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
            static=static,
        )
        body = Body(self._physics, bid)
        self._register_body(body)
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
        self._register_body(body)
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
        from forge3d.errors import require_nonneg, require_positive, require_range

        if not static:
            require_positive(float(mass), "mass", "World.add_sphere()")
        require_positive(float(radius), "radius", "World.add_sphere()")
        require_range(float(restitution), 0.0, 1.0, "restitution", "World.add_sphere()")
        require_nonneg(float(friction), "friction", "World.add_sphere()")
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
        self._register_body(body)
        return body

    def add_terrain(
        self,
        heights: Any,
        cell_size: float = 1.0,
        origin: Any = (0.0, 0.0, 0.0),
        material: Material | str = "ground",
        friction: float = 0.8,
        layer: int = 0x0008,
    ) -> Any:
        """Add a heightfield terrain (static, collision-only).

        Args:
            heights: 2D array of shape (rows, cols) with z-heights in metres.
            cell_size: World-space size of each grid cell (m).
            origin: World-space position of the (0, 0) grid corner.
            material: Surface material for rendering.
            friction: Coulomb friction coefficient (default 0.8).
            layer: Collision layer bit-flag (default CollisionLayer.TERRAIN = 0x0008).

        Returns:
            A :class:`~forge3d.collision.heightfield.Heightfield` object.

        Example::

            import numpy as np
            rng = np.random.default_rng(42)
            h = rng.uniform(0, 2, (32, 32)).astype(np.float32)
            terrain = world.add_terrain(h, cell_size=0.5, origin=(-8, -8, 0),
                                        friction=0.9, layer=f3d.CollisionLayer.TERRAIN)
        """
        from forge3d.collision.heightfield import Heightfield

        mat_id, mat = _resolve_material(material)
        if mat:
            self._materials[mat_id] = mat

        hf = Heightfield(
            heights=np.asarray(heights, dtype=np.float32),
            cell_size=float(cell_size),
            origin=np.asarray(origin, dtype=float),
            material_id=mat_id,
            friction=float(friction),
            collision_layer=int(layer),
        )
        self._physics._heightfields.append(hf)
        return hf

    def add_character(
        self,
        position: Any = (0.0, 0.0, 2.0),
        height: float = 1.8,
        radius: float = 0.3,
        mass: float = 70.0,
        name: str = "character",
        ground_layer_mask: int = 0xFFFF,
        ground_check_hz: float = 60.0,
    ) -> Any:
        """Add a capsule-based character controller.

        Returns a :class:`~forge3d.character.CharacterController` with
        ``move()``, ``jump()``, and ``glide()`` methods.

        Parameters
        ----------
        position : Initial world position (3,).
        height   : Total capsule height in metres (default 1.8 m).
        radius   : Capsule radius in metres (default 0.3 m).
        mass     : Body mass in kg (default 70.0).
        name     : Body name for collision queries.
        ground_layer_mask : Layers considered "ground" for the raycast check.

        Example::

            cc = world.add_character(position=(0, 0, 2), height=1.8)

            while viewer.is_open:
                cc.move(direction=(inp.dx, inp.dy, 0), speed=5.5, dt=viewer.dt)
                if inp.just_pressed("space"):
                    cc.jump(impulse=6.4)
                world.step(viewer.dt)

            print(cc.is_grounded)
        """
        from forge3d.character import CharacterController

        half_length = max(0.01, float(height) / 2.0 - float(radius))
        body = self.add_capsule(
            radius=radius,
            half_length=half_length,
            position=position,
            mass=mass,
            name=name,
            friction=0.1,
            restitution=0.0,
        )
        return CharacterController(
            world=self,
            body=body,
            height=height,
            radius=radius,
            ground_layer_mask=ground_layer_mask,
            ground_check_hz=ground_check_hz,
        )

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
        raise KeyError(
            f"No body named '{name}' in world. Available: {[b.name for b in self.bodies]}"
        )

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
        self._events.unregister_body(bid)

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
        local_rotation: Any = None,
    ) -> None:
        """Attach *body* kinematically to *anchor* (weld constraint).

        After welding, ``body`` follows ``anchor`` rigidly each ``step()``,
        preserving both relative position and relative orientation.

        Parameters
        ----------
        local_offset   : Position offset in *anchor* local frame.  Computed
                         automatically from current positions if omitted.
        local_rotation : Quaternion [w, x, y, z] expressing *body*'s rotation
                         relative to *anchor*.  Computed automatically if omitted.
        """
        from forge3d.math.quaternion import quat_multiply, quat_to_rot

        a_state = anchor._state()
        b_state = body._state()
        R_anchor = quat_to_rot(a_state.quat)

        if local_offset is None:
            local_offset = R_anchor.T @ (b_state.pos - a_state.pos)

        if local_rotation is None:
            # Relative rotation: R_anchor^T @ R_body = rotation of body in anchor frame
            from forge3d.math.quaternion import quat_conjugate

            # rel_q = q_anchor^-1 * q_body
            q_anc_inv = quat_conjugate(a_state.quat)
            rel_q = quat_multiply(q_anc_inv, b_state.quat)
        else:
            rel_q = np.asarray(local_rotation, dtype=float)

        self._welds[body._id] = (
            anchor._id,
            np.asarray(local_offset, dtype=float),
            np.asarray(rel_q, dtype=float),
        )

    def release(self, body: Body) -> None:
        """Remove weld constraint from *body* (body resumes normal physics)."""
        self._welds.pop(body._id, None)

    # ── Joint / constraint system ─────────────────────────────────────────────

    def add_joint(
        self,
        joint_type: str,
        body_a: Body,
        body_b: Body | None = None,
        anchor_a: Any = (0.0, 0.0, 0.0),
        anchor_b: Any = (0.0, 0.0, 0.0),
        axis: Any = (0.0, 0.0, 1.0),
        limits: tuple[float, float] | None = None,
        motor_velocity: float | None = None,
        motor_max_torque: float = 10.0,
        stiffness: float = 100.0,
        damping: float = 5.0,
        rest_length: float = 1.0,
        target_distance: float = 1.0,
    ) -> Any:
        """Add a joint constraint between two bodies.

        Args:
            joint_type: One of ``"fixed"``, ``"ball"``, ``"hinge"``,
                ``"prismatic"``, ``"distance"``, ``"spring"``.
            body_a: First body (required).
            body_b: Second body.  If ``None``, the joint anchors body_a
                to a world-fixed point (``anchor_b`` in world frame).
            anchor_a: Attachment point in body_a local frame.
            anchor_b: Attachment point in body_b local frame (or world frame
                if body_b is None).
            axis: Hinge / slide axis in body_a local frame
                (used for ``"hinge"`` and ``"prismatic"``).
            limits: Angular limits (rad) for hinge or distance limits (m)
                for prismatic.
            motor_velocity: Target velocity for hinge/prismatic motor.
            motor_max_torque: Torque cap for hinge motor (N·m).
            stiffness: Spring constant k (N/m) for spring joint.
            damping: Damping coefficient c (N·s/m) for spring joint.
            rest_length: Natural spring length (m) for spring joint.
            target_distance: Target distance (m) for distance joint.

        Returns:
            A :class:`forge3d.constraints.JointHandle` (pass to
            :meth:`remove_joint` to delete the joint).

        Examples::

            hinge = world.add_joint("hinge", door, frame,
                                    anchor_a=(-0.5, 0, 0),
                                    anchor_b=(0.5, 0, 0),
                                    axis=(0, 0, 1))
            spring = world.add_joint("spring", box, ceiling,
                                     stiffness=200.0, damping=10.0,
                                     rest_length=2.0)
        """
        from forge3d.constraints import (
            BallJoint,
            DistanceJoint,
            FixedJoint,
            HingeJoint,
            JointHandle,
            PrismaticJoint,
            SpringJoint,
        )

        id_a = body_a._id
        id_b = body_b._id if body_b is not None else -1
        anc_a = np.asarray(anchor_a, dtype=float)
        anc_b = np.asarray(anchor_b, dtype=float)
        ax = np.asarray(axis, dtype=float)

        from forge3d.constraints.base import Constraint as _Constraint  # noqa: F811

        jtype = joint_type.lower().replace("-", "_")
        constraint: _Constraint
        if jtype == "fixed":
            constraint = FixedJoint(id_a, id_b, anc_a, anc_b)
        elif jtype == "ball":
            constraint = BallJoint(id_a, id_b, anc_a, anc_b)
        elif jtype == "hinge":
            constraint = HingeJoint(
                id_a,
                id_b,
                anc_a,
                anc_b,
                ax,
                limits=limits,
                motor_velocity=motor_velocity,
                motor_max_torque=motor_max_torque,
            )
        elif jtype == "prismatic":
            constraint = PrismaticJoint(
                id_a,
                id_b,
                anc_a,
                anc_b,
                ax,
                limits=limits,
                motor_velocity=motor_velocity,
                motor_max_force=motor_max_torque,
            )
        elif jtype == "distance":
            constraint = DistanceJoint(id_a, id_b, anc_a, anc_b, target_distance)
        elif jtype == "spring":
            constraint = SpringJoint(
                id_a,
                id_b,
                anc_a,
                anc_b,
                stiffness=stiffness,
                damping=damping,
                rest_length=rest_length,
            )
        else:
            raise ValueError(
                f"Unknown joint type '{joint_type}'. "
                f"Choose from: fixed, ball, hinge, prismatic, distance, spring."
            )

        jid = self._physics.add_constraint(constraint)
        return JointHandle(joint_id=jid, joint_type=jtype)

    def remove_joint(self, handle: Any) -> None:
        """Remove a joint by its handle (returned from :meth:`add_joint`)."""
        self._physics.remove_constraint(handle.joint_id)

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

    def step(self, dt: float | None = None, substeps: int = 1) -> None:
        """Advance simulation by dt seconds (default: 1/60 s).

        Parameters
        ----------
        dt       : Time delta in seconds (default 1/60 s).
        substeps : Divide *dt* into this many equal sub-steps for stability.
                   ``substeps=4`` is recommended for fast or lightweight objects.
                   Collision callbacks fire once per full step (not per sub-step).

        Steps taken each call:

        1. Flush per-body force/torque accumulators.
        2. Apply per-body linear/angular damping.
        3. Physics integration (*substeps* times at *dt/substeps* each).
        4. Apply weld constraints.
        5. Dispatch collision events.
        """
        _dt = dt if dt is not None else self.DEFAULT_DT
        _sub = max(1, int(substeps))
        _sub_dt = _dt / _sub

        # Flush accumulators before physics step
        for body in self._bodies.values():
            if body._force_accum is not None and (
                np.any(body._force_accum != 0) or np.any(body._torque_accum != 0)
            ):
                body._flush_accumulators(_dt)
            # Apply per-body damping (exponential decay, dt-corrected)
            if body._linear_damping > 0 or body._angular_damping > 0:
                self._apply_body_damping(body, _dt)

        for _ in range(_sub):
            self._physics.step(_sub_dt)
        self._apply_welds()
        # Dispatch events once per full step
        self._dispatch_events()

    def update(self, frame_dt: float) -> None:
        """Fixed-timestep accumulator update — call once per rendered frame.

        Internally accumulates *frame_dt* and calls :meth:`step` with
        ``fixed_dt`` repeatedly until the accumulated time is consumed.
        Leftover time carries over to the next call.

        Configure via :attr:`fixed_dt` and :attr:`max_substeps` (set on the
        world instance)::

            world.fixed_dt    = 1 / 120   # default 1/120 s
            world.max_substeps = 8         # default 8 (caps spiral-of-death)

        Example::

            world = forge3d.World()
            world.fixed_dt = 1 / 120

            while viewer.is_open:
                world.update(viewer.dt)   # frame_dt varies; physics is stable
                viewer.draw()
        """
        fixed_dt = getattr(self, "fixed_dt", 1.0 / 120.0)
        max_sub = getattr(self, "max_substeps", 8)

        self._accum_time = getattr(self, "_accum_time", 0.0) + frame_dt
        steps = 0
        while self._accum_time >= fixed_dt and steps < max_sub:
            self.step(fixed_dt)
            self._accum_time -= fixed_dt
            steps += 1

    def _apply_body_damping(self, body: Body, dt: float) -> None:
        """Apply per-body linear/angular damping (exponential decay, dt-corrected)."""
        import math

        b = body._state()
        if b.static or b.mass <= 0:
            return
        from dataclasses import replace

        new_vel = b.vel
        new_omega = b.omega
        if body._linear_damping > 0:
            factor = math.exp(-body._linear_damping * dt)
            new_vel = b.vel * factor
        if body._angular_damping > 0:
            factor = math.exp(-body._angular_damping * dt)
            new_omega = b.omega * factor
        if new_vel is not b.vel or new_omega is not b.omega:
            self._physics._replace_body(body._id, replace(b, vel=new_vel, omega=new_omega))

    def _dispatch_events(self) -> None:
        """Dispatch collision begin/stay/end callbacks.

        Reuses contacts cached by _physics.step() to avoid double detection.
        Falls back to fresh detection if cache is empty (e.g., first frame).
        """

        # Reuse contacts cached during _physics.step() — no double detect_contacts
        contacts_raw = self._physics._last_contacts
        if not contacts_raw:
            # Only re-detect if no cache (step() hasn't run yet)
            from forge3d.collision.detection import detect_contacts

            contacts_raw = detect_contacts(self._physics._bodies)

        class _EvtContact:
            __slots__ = [
                "body_id_a",
                "body_id_b",
                "contact_point",
                "normal",
                "impulse",
                "relative_speed",
            ]

            def __init__(self, c: Any, bodies: list[Any]) -> None:
                ba = bodies[c.body_a_idx]
                self.body_id_a = ba.body_id
                if c.body_b_idx >= 0:
                    self.body_id_b = bodies[c.body_b_idx].body_id
                else:
                    self.body_id_b = -1
                self.contact_point = c.pos
                self.normal = c.normal
                self.impulse = 0.0
                self.relative_speed = 0.0

        evt_contacts = [_EvtContact(c, self._physics._bodies) for c in contacts_raw]
        # Filter ignored pairs
        if self._ignored_pairs:
            evt_contacts = [
                c
                for c in evt_contacts
                if frozenset({c.body_id_a, c.body_id_b}) not in self._ignored_pairs
            ]

        self._events._bodies = self._bodies  # type: ignore[assignment]  # share reference
        self._events.dispatch(evt_contacts)

    # ── Collision event API ────────────────────────────────────────────────────

    def on_collision_begin(self, fn: Any) -> Any:
        """Register a callback for when two bodies first collide.

        Can be used as a decorator::

            @world.on_collision_begin
            def hit(event: forge3d.CollisionEvent) -> None:
                print(event.body_a.name, "hit", event.body_b.name)
        """
        self._events.add_begin_listener(fn)
        return fn

    def on_collision_stay(self, fn: Any) -> Any:
        """Register a callback called every step while two bodies remain in contact."""
        self._events.add_stay_listener(fn)
        return fn

    def on_collision_end(self, fn: Any) -> Any:
        """Register a callback when two bodies separate."""
        self._events.add_end_listener(fn)
        return fn

    def add_collision_handler(self, body_a: Body, body_b: Body) -> Any:
        """Return a :class:`~forge3d.events.CollisionHandler` for a specific body pair.

        Example::

            handler = world.add_collision_handler(ball, floor)
            handler.on_begin = lambda e: print("Hit!")
        """
        handler = self._events.add_pair_handler(body_a._id, body_b._id)
        return handler

    def ignore_collision(self, body_a: Body, body_b: Body) -> None:
        """Permanently ignore physics collisions between two specific bodies."""
        pair: frozenset[int] = frozenset({body_a._id, body_b._id})
        self._ignored_pairs.add(pair)
        self._physics._ignored_pairs.add(pair)

    def add_trigger_zone(
        self,
        position: Any = (0.0, 0.0, 0.0),
        size: Any = (1.0, 1.0, 1.0),
        name: str = "trigger",
    ) -> Any:
        """Add an invisible trigger zone (no physics collision, events only).

        Returns a :class:`~forge3d.events.TriggerZone` with ``on_enter`` and
        ``on_exit`` decorator attributes.

        Example::

            goal = world.add_trigger_zone(position=(5, 0, 0.5), size=(1, 1, 1))

            @goal.on_enter
            def scored(body: forge3d.Body) -> None:
                print(f"GOAL! {body.name}")
        """
        pos = np.asarray(position, dtype=float)
        sz = np.asarray(size, dtype=float)
        half_extents = sz / 2.0
        zone = self._events.add_trigger_zone(pos, half_extents)
        return zone

    def _apply_welds(self) -> None:
        if not self._welds:
            return
        from forge3d.math.quaternion import quat_multiply, quat_to_rot

        _ZEROS3 = np.zeros(3)
        for body_id, weld_data in self._welds.items():
            # Support both old 2-tuple format (pos only) and new 3-tuple (pos + rot)
            if len(weld_data) == 2:
                anchor_id, offset = weld_data
                rel_q = None
            else:
                anchor_id, offset, rel_q = weld_data
            try:
                anchor = self._physics._get_body(anchor_id)
            except RuntimeError:
                continue
            R_anchor = quat_to_rot(anchor.quat)
            new_pos = anchor.pos + R_anchor @ offset
            new_quat = quat_multiply(anchor.quat, rel_q) if rel_q is not None else anchor.quat
            self._physics.update_body_pose(body_id, new_pos, new_quat, vel=_ZEROS3, omega=_ZEROS3)

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

    @property
    def profiler(self) -> Any:
        """Lazy-created :class:`~forge3d.profiler.PhysicsProfiler` for this world.

        Usage::

            with world.profiler:
                world.step(dt)

            print(world.profiler.last)
        """
        if not hasattr(self, "_profiler"):
            from forge3d.profiler import PhysicsProfiler

            self._profiler = PhysicsProfiler(self)
        return self._profiler

    # ── SceneSnapshot ─────────────────────────────────────────────────────────

    def snapshot(self) -> Any:
        """Build a SceneSnapshot for the current state (used by Viewer/Recorder)."""
        for robot in self._robots:
            self._sync_robot(robot)

        snap = self._physics.snapshot()

        # Register custom materials into snap.materials for ID-based lookup
        for mat_id, mat in self._materials.items():
            if mat_id not in snap.materials:
                snap.materials[mat_id] = mat._to_snapshot_material()

        # Back-fill resolved material objects into snapshots so renderers
        # don't need to consult BUILTIN_MATERIALS by ID.
        for body_snap in snap.bodies:
            if body_snap.material is None:
                body_snap.material = snap.materials.get(body_snap.material_id)

        for terrain_snap in snap.terrains:
            if terrain_snap.material is None:
                terrain_snap.material = snap.materials.get(terrain_snap.material_id)

        return snap

    # ── Serialization ─────────────────────────────────────────────────────────

    def save(self, path: Any) -> None:
        """Save the current world state to a JSON file.

        Args:
            path: Output path (str or :class:`pathlib.Path`).

        Example::

            world.save("checkpoint.json")
        """
        from forge3d.io.world_snapshot import save_world

        save_world(self, path)

    @classmethod
    def load(cls, path: Any) -> World:
        """Load a world from a JSON file saved by :meth:`save`.

        Returns a brand-new :class:`World` with all bodies restored::

            world = forge3d.World.load("checkpoint.json")

        To restore an **existing** world instance in-place, use
        :meth:`restore` instead::

            world.restore("checkpoint.json")

        Args:
            path: Path to a JSON file.
        """
        from forge3d.io.world_snapshot import load_world

        return load_world(path)  # type: ignore[return-value]

    def restore(self, path: Any) -> None:
        """Restore world state from *path* into this instance (clears existing bodies).

        Unlike the classmethod :meth:`load`, this modifies the current world
        in-place so existing Python references to ``self`` remain valid::

            world = forge3d.World()
            world.restore("checkpoint.json")
            print(len(world.bodies))  # bodies from the file
        """
        from forge3d.io.world_snapshot import load_world

        loaded = load_world(path)
        self._physics = loaded._physics
        self._bodies = loaded._bodies
        self._materials = loaded._materials
        self._camera = loaded._camera
        self._robots = loaded._robots
        self._welds = loaded._welds
        self._events = loaded._events
        self._ignored_pairs = loaded._ignored_pairs

    # ── Raycast ───────────────────────────────────────────────────────────────

    def raycast_all(
        self,
        origin: Any,
        direction: Any,
        max_dist: float = 100.0,
        layer_mask: int = 0xFFFF,
    ) -> list[Any]:
        """Cast a ray and return **all** hits sorted by distance (closest first).

        Parameters
        ----------
        origin, direction, max_dist : same as :meth:`raycast`.
        layer_mask : only bodies whose ``collision_layer & layer_mask != 0``
                     are tested.

        Returns
        -------
        List of :class:`RayHit` namedtuples ``(body, point, normal, distance)``.
        May be empty.

        Example::

            hits = world.raycast_all((0, 0, 5), (0, 0, -1), max_dist=20)
            for hit in hits:
                print(hit.body.name, hit.distance)
        """
        from collections import namedtuple

        from forge3d.collision.raycast import ray_cast_all

        RayHit = namedtuple("RayHit", ["body", "point", "normal", "distance"])

        filtered_bodies = [
            self._physics._get_body(bid)
            for bid in self._bodies
            if self._physics._get_body(bid).collision_layer & layer_mask
        ]
        results = ray_cast_all(
            np.asarray(origin, dtype=float),
            np.asarray(direction, dtype=float),
            float(max_dist),
            filtered_bodies,
        )
        hits = []
        for body_id, point, normal, dist in results:
            body = self._bodies.get(body_id)
            if body is not None:
                hits.append(RayHit(body=body, point=point, normal=normal, distance=dist))
        return hits

    def overlap_sphere(
        self,
        center: Any,
        radius: float,
        layer_mask: int = 0xFFFF,
    ) -> list[Body]:
        """Return all bodies whose origin is within *radius* of *center*.

        Uses AABB/position check (fast) — not exact shape intersection.

        Parameters
        ----------
        center     : (3,) world-space position.
        radius     : Search radius in metres.
        layer_mask : Filter by collision layer.

        Example::

            nearby = world.overlap_sphere(explosion_pos, radius=5.0)
            for body in nearby:
                body.apply_force(...)
        """
        c = np.asarray(center, dtype=float)
        r2 = float(radius) ** 2
        result = []
        for body in self._bodies.values():
            try:
                state = body._state()
                if not (state.collision_layer & layer_mask):
                    continue
                if float(np.dot(state.pos - c, state.pos - c)) <= r2:
                    result.append(body)
            except Exception:
                pass
        return result

    def overlap_box(
        self,
        center: Any,
        half_extents: Any,
        orientation: Any = None,
        layer_mask: int = 0xFFFF,
    ) -> list[Body]:
        """Return all bodies whose origin falls inside an AABB or OBB.

        Parameters
        ----------
        center      : (3,) world-space centre.
        half_extents: (3,) half-sizes of the query box.
        orientation : (4,) quaternion [w,x,y,z] rotating the box (None = axis-aligned).
        layer_mask  : Filter by collision layer.

        Example::

            bodies_in_room = world.overlap_box(room_center, half_extents=(5, 5, 3))
        """
        c = np.asarray(center, dtype=float)
        he = np.asarray(half_extents, dtype=float)
        if orientation is not None:
            from forge3d.math.quaternion import quat_to_rot

            R = quat_to_rot(np.asarray(orientation, dtype=float))
        else:
            R = None

        result = []
        for body in self._bodies.values():
            try:
                state = body._state()
                if not (state.collision_layer & layer_mask):
                    continue
                diff = state.pos - c
                if R is not None:
                    diff = R.T @ diff
                if np.all(np.abs(diff) <= he):
                    result.append(body)
            except Exception:
                pass
        return result

    def raycast(
        self,
        origin: Any,
        direction: Any,
        max_dist: float = 100.0,
    ) -> Any | None:
        """Cast a ray from *origin* along *direction* and return the first hit.

        Tests the ray against all physics bodies (AABB then exact shape) and
        returns the closest intersection, or ``None`` if nothing is hit.

        Parameters
        ----------
        origin    : (3,) ray start in world frame (m).
        direction : (3,) ray direction — need not be normalised.
        max_dist  : Maximum hit distance (m).

        Returns
        -------
        A :class:`RayHit` namedtuple with fields
        ``(body, point, normal, distance)`` or ``None``.

        Example::

            hit = world.raycast((0, 0, 5), (0, 0, -1), max_dist=10)
            if hit:
                print(hit.body.name, hit.distance)
        """
        from forge3d.collision.raycast import ray_cast

        result = ray_cast(
            np.asarray(origin, dtype=float),
            np.asarray(direction, dtype=float),
            float(max_dist),
            self._physics._bodies,
        )
        if result is None:
            return None
        body_id, point, normal, dist = result
        body = self._bodies.get(body_id)
        if body is None:
            return None
        from collections import namedtuple

        RayHit = namedtuple("RayHit", ["body", "point", "normal", "distance"])
        return RayHit(body=body, point=point, normal=normal, distance=dist)

    def _register_body(self, body: Body) -> Body:
        """Store body in _bodies, set its world back-reference, and register events."""
        self._bodies[body._id] = body
        body._world_ref = self
        self._events.register_body(body._id, body)
        return body

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
