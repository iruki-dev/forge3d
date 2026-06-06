"""PhysicsWorld — rigid-body world with primitive collision and impulse contact.

Design invariant (checked by test_snapshot.py):
  `forge3d.sim.world` must NOT transitively import moderngl / glfw / pyglet
  or any other renderer module.  The only render-directory import allowed is
  the pure-data SceneSnapshot from render.snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np

from forge3d.io.mesh_data import convex_hull_inertia
from forge3d.math.inertia import box_inertia, capsule_inertia, sphere_inertia
from forge3d.math.quaternion import quat_multiply, quat_normalize, quat_to_rot

# ── Body state ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Body:
    """Immutable state of one rigid body (world-frame quantities)."""

    body_id: int
    name: str
    # Kinematics (world frame, z-up)
    pos: Any  # (3,) float64
    quat: Any  # (4,) [w,x,y,z] unit quaternion
    vel: Any  # (3,) linear velocity
    omega: Any  # (3,) angular velocity
    # Physical properties
    mass: float
    static: bool
    restitution: float  # coefficient of restitution [0, 1]
    friction: float  # Coulomb friction coefficient >= 0
    # Shape
    shape_type: str
    shape_params: dict[str, Any]
    material_id: str
    # Rotational inertia (3×3 diagonal tensor in body-local frame).
    # None → treated as point mass (zero rotational contribution).
    # Set automatically by add_box / add_sphere / add_capsule.
    inertia_local: Any = field(default=None)
    # Pre-computed inverse of inertia_local (constant per body — never changes).
    # Cached here to avoid np.linalg.inv every physics step.
    inertia_inv_local: Any = field(default=None)
    # Collision layer/mask (bit fields). Default: layer=0x0001, mask=0xFFFF
    collision_layer: int = 0x0001
    collision_mask: int = 0xFFFF


# ── World ─────────────────────────────────────────────────────────────────────


class PhysicsWorld:
    """Rigid-body physics world with primitive collision response.

    Coordinate system: z-up, SI units.

    Usage::

        world = PhysicsWorld(gravity=[0, 0, -9.81])
        world.add_ground()
        box = world.add_box((1, 1, 1), position=(0, 0, 5))
        for _ in range(100):
            world.step(dt=1/60)
        snap = world.snapshot()
    """

    def __init__(self, gravity: Any = None, contact_spring_k: float = 0.0) -> None:
        self._gravity = np.asarray(
            gravity if gravity is not None else [0.0, 0.0, -9.81], dtype=float
        )
        self._bodies: list[_Body] = []
        self._next_id = 0
        self._time: float = 0.0
        self._camera: Any = None  # CameraSnapshot or None
        self._contact_spring_k: float = float(contact_spring_k)
        # Body-id → list-index cache for O(1) lookups (invalidated on remove)
        self._id_to_idx: dict[int, int] = {}
        # Constraint / joint system
        self._constraints: list[Any] = []  # list[Constraint]
        self._next_joint_id: int = 0
        # Physics-level ignored pairs — frozenset({id_a, id_b})
        self._ignored_pairs: set[frozenset[int]] = set()
        # Heightfield terrain list
        self._heightfields: list[Any] = []
        # Cached contacts from last step (reused by facade._dispatch_events)
        self._last_contacts: list[Any] = []
        # Island sleeping — count of consecutive steps below threshold
        self._sleep_counters: dict[int, int] = {}  # body_id → sleep_frames
        # Sleeping parameters
        self._sleep_vel_threshold: float = 0.01  # m/s
        self._sleep_omega_threshold: float = 0.01  # rad/s
        self._sleep_frames_required: int = 60  # ~1 s @ 60 Hz
        self._sleeping_enabled: bool = True

    # ── Scene construction ────────────────────────────────────────────────────

    def add_box(
        self,
        size: Any = (1.0, 1.0, 1.0),
        position: Any = (0.0, 0.0, 0.0),
        mass: float = 1.0,
        material: str = "default",
        name: str = "",
        restitution: float = 0.3,
        friction: float = 0.5,
    ) -> int:
        """Add a box-shaped rigid body. Returns body_id."""
        sx, sy, sz = size
        he = np.array([sx / 2.0, sy / 2.0, sz / 2.0], dtype=float)
        inertia = box_inertia(float(mass), he)
        body = _Body(
            body_id=self._next_id,
            name=name or f"box_{self._next_id}",
            pos=np.asarray(position, dtype=float),
            quat=np.array([1.0, 0.0, 0.0, 0.0]),
            vel=np.zeros(3),
            omega=np.zeros(3),
            mass=float(mass),
            static=False,
            restitution=float(restitution),
            friction=float(friction),
            shape_type="box",
            shape_params={"half_extents": he},
            material_id=material,
            inertia_local=inertia,
            inertia_inv_local=np.diag(1.0 / np.diag(inertia)),
        )
        self._append_body(body)
        self._next_id += 1
        return body.body_id

    def add_static_box(
        self,
        size: Any = (10.0, 10.0, 0.1),
        position: Any = (0.0, 0.0, 0.0),
        material: str = "ground",
        name: str = "ground",
        restitution: float = 0.0,
        friction: float = 0.8,
        quat: Any = None,
    ) -> int:
        """Add a static (non-moving) box (e.g. a ground plane or robot link)."""
        return self._add_static(
            "box",
            {
                "half_extents": np.array([s / 2 for s in size], dtype=float),
            },
            position,
            material,
            name,
            restitution,
            friction,
            quat=quat,
        )

    def add_sphere(
        self,
        radius: float = 0.5,
        position: Any = (0.0, 0.0, 0.0),
        mass: float = 1.0,
        material: str = "default",
        name: str = "",
        restitution: float = 0.3,
        friction: float = 0.5,
        static: bool = False,
    ) -> int:
        is_static = static or (mass == 0.0)
        m = 0.0 if is_static else float(mass)
        I_sph = sphere_inertia(m, float(radius)) if not is_static else None
        body = _Body(
            body_id=self._next_id,
            name=name or f"sphere_{self._next_id}",
            pos=np.asarray(position, dtype=float),
            quat=np.array([1.0, 0.0, 0.0, 0.0]),
            vel=np.zeros(3),
            omega=np.zeros(3),
            mass=m,
            static=is_static,
            restitution=float(restitution),
            friction=float(friction),
            shape_type="sphere",
            shape_params={"radius": float(radius)},
            material_id=material,
            inertia_local=I_sph,
            inertia_inv_local=np.diag(1.0 / np.diag(I_sph)) if I_sph is not None else None,
        )
        self._append_body(body)
        self._next_id += 1
        return body.body_id

    def add_capsule(
        self,
        radius: float = 0.2,
        half_length: float = 0.5,
        position: Any = (0.0, 0.0, 0.0),
        quat: Any = None,
        mass: float = 1.0,
        material: str = "default",
        name: str = "",
        restitution: float = 0.3,
        friction: float = 0.5,
        static: bool = False,
    ) -> int:
        """Add a capsule (cylinder + hemispherical caps), axis = body z. Returns body_id."""
        is_static = static or (mass == 0.0)
        m = 0.0 if is_static else float(mass)
        r = float(radius)
        half_len = float(half_length)
        q = np.asarray(quat, dtype=float) if quat is not None else np.array([1.0, 0.0, 0.0, 0.0])
        I_cap = capsule_inertia(m, r, half_len) if not is_static else None
        body = _Body(
            body_id=self._next_id,
            name=name or f"capsule_{self._next_id}",
            pos=np.asarray(position, dtype=float),
            quat=q,
            vel=np.zeros(3),
            omega=np.zeros(3),
            mass=m,
            static=is_static,
            restitution=float(restitution),
            friction=float(friction),
            shape_type="capsule",
            shape_params={"radius": r, "half_length": half_len},
            material_id=material,
            inertia_local=I_cap,
            inertia_inv_local=np.diag(1.0 / np.diag(I_cap)) if I_cap is not None else None,
        )
        self._append_body(body)
        self._next_id += 1
        return body.body_id

    def add_convex_mesh(
        self,
        mesh_data: Any,  # forge3d.io.MeshData
        position: Any = (0.0, 0.0, 0.0),
        quat: Any = None,
        mass: float = 1.0,
        material: str = "default",
        name: str = "",
        restitution: float = 0.3,
        friction: float = 0.5,
        static: bool = False,
    ) -> int:
        """Add a convex-hull rigid body from a MeshData object. Returns body_id.

        The MeshData is expected to have ``hull_vertices`` and ``hull_faces``
        computed (done automatically by ``load_obj``).
        """
        m = 0.0 if static else float(mass)
        q = np.asarray(quat, dtype=float) if quat is not None else np.array([1.0, 0.0, 0.0, 0.0])

        hull_verts = np.asarray(mesh_data.hull_vertices, dtype=float)
        hull_faces = (
            np.asarray(mesh_data.hull_faces, dtype=np.int32)
            if len(mesh_data.hull_faces) > 0
            else np.empty((0, 3), dtype=np.int32)
        )
        I_mesh = convex_hull_inertia(m, hull_verts, hull_faces) if not static and m > 0.0 else None

        shape_params: dict[str, Any] = {
            "hull_vertices": hull_verts,
            "hull_faces": hull_faces,
            "mesh_data": mesh_data,  # kept for renderer VAO building (pure data)
        }

        body = _Body(
            body_id=self._next_id,
            name=name or f"mesh_{self._next_id}",
            pos=np.asarray(position, dtype=float),
            quat=q,
            vel=np.zeros(3),
            omega=np.zeros(3),
            mass=m,
            static=static,
            restitution=float(restitution),
            friction=float(friction),
            shape_type="mesh",
            shape_params=shape_params,
            material_id=material,
            inertia_local=I_mesh,
            inertia_inv_local=np.diag(1.0 / np.diag(I_mesh)) if I_mesh is not None else None,
        )
        self._append_body(body)
        self._next_id += 1
        return body.body_id

    def _add_static(
        self,
        shape_type: str,
        shape_params: dict[str, Any],
        position: Any,
        material: str,
        name: str,
        restitution: float = 0.0,
        friction: float = 0.8,
        quat: Any = None,
    ) -> int:
        q = np.asarray(quat, dtype=float) if quat is not None else np.array([1.0, 0.0, 0.0, 0.0])
        body = _Body(
            body_id=self._next_id,
            name=name or f"static_{self._next_id}",
            pos=np.asarray(position, dtype=float),
            quat=q,
            vel=np.zeros(3),
            omega=np.zeros(3),
            mass=0.0,
            static=True,
            restitution=float(restitution),
            friction=float(friction),
            shape_type=shape_type,
            shape_params=shape_params,
            material_id=material,
        )
        self._append_body(body)
        self._next_id += 1
        return body.body_id

    # ── Fast body lookup helpers ───────────────────────────────────────────────

    def _rebuild_index(self) -> None:
        """Rebuild the id→index cache from scratch."""
        self._id_to_idx = {b.body_id: i for i, b in enumerate(self._bodies)}

    def _get_body(self, body_id: int) -> _Body:
        """O(1) body lookup by id. Raises RuntimeError if not found."""
        idx = self._id_to_idx.get(body_id, -1)
        if 0 <= idx < len(self._bodies) and self._bodies[idx].body_id == body_id:
            return self._bodies[idx]
        # Cache stale — rebuild and retry
        self._rebuild_index()
        idx = self._id_to_idx.get(body_id, -1)
        if idx < 0:
            raise RuntimeError(f"Body id={body_id} not found in world")
        return self._bodies[idx]

    def _replace_body(self, body_id: int, new_body: _Body) -> None:
        """Replace body in-place; updates cache."""
        idx = self._id_to_idx.get(body_id, -1)
        if idx < 0:
            self._rebuild_index()
            idx = self._id_to_idx.get(body_id, -1)
        if idx < 0:
            raise RuntimeError(f"Body id={body_id} not found in world")
        self._bodies[idx] = new_body

    def _append_body(self, body: _Body) -> None:
        """Append body and update the index cache."""
        self._id_to_idx[body.body_id] = len(self._bodies)
        self._bodies.append(body)

    # ── Body removal ──────────────────────────────────────────────────────────

    def remove_body(self, body_id: int) -> None:
        """Remove a body by id.  Rebuilds the id→index cache afterward."""
        idx = self._id_to_idx.get(body_id, -1)
        if idx < 0:
            self._rebuild_index()
            idx = self._id_to_idx.get(body_id, -1)
        if idx < 0:
            return  # already gone
        self._bodies.pop(idx)
        self._rebuild_index()

    def update_body_pose(
        self,
        body_id: int,
        pos: Any,
        quat: Any,
        vel: Any = None,
        omega: Any = None,
    ) -> None:
        """Update position, orientation (and optionally velocity) of a body.

        Used by World for FK sync, weld constraints, and teleport.
        Passing vel/omega zeros out velocities to prevent drift in welded objects.
        """
        b = self._get_body(body_id)
        new_vel = np.asarray(vel, dtype=float) if vel is not None else b.vel
        new_omega = np.asarray(omega, dtype=float) if omega is not None else b.omega
        self._replace_body(
            body_id,
            replace(
                b,
                pos=np.asarray(pos, dtype=float),
                quat=np.asarray(quat, dtype=float),
                vel=new_vel,
                omega=new_omega,
            ),
        )

    def apply_impulse(self, body_id: int, impulse: Any) -> None:
        """Apply an instantaneous velocity impulse (Δv = impulse / mass).

        No-op for static bodies.
        """
        J = np.asarray(impulse, dtype=float)
        b = self._get_body(body_id)
        if not b.static and b.mass > 0.0:
            self._replace_body(body_id, replace(b, vel=b.vel + J / b.mass))

    def set_camera(
        self,
        position: Any,
        target: Any,
        up: Any = None,
        fov_deg: float = 45.0,
    ) -> None:
        """Set the default camera for snapshots."""
        if up is None:
            up = [0.0, 0.0, 1.0]
        self._camera = (
            np.asarray(position, dtype=float),
            np.asarray(target, dtype=float),
            np.asarray(up, dtype=float),
            fov_deg,
        )

    # ── Simulation ────────────────────────────────────────────────────────────

    # ── Constraint / joint management ─────────────────────────────────────────

    def add_constraint(self, constraint: Any) -> int:
        """Register a constraint; returns a joint_id for later removal."""
        jid = self._next_joint_id
        self._next_joint_id += 1
        constraint.joint_id = jid
        self._constraints.append(constraint)
        return jid

    def remove_constraint(self, joint_id: int) -> None:
        """Remove a constraint by joint_id."""
        self._constraints = [c for c in self._constraints if c.joint_id != joint_id]

    def step(self, dt: float) -> None:
        """Advance simulation by dt seconds.

        Order (velocity-before-position for correct contact response):
          1. Apply gravity to velocities (and rotation); do NOT move positions yet.
          2. Detect contacts at CURRENT positions (with AABB broad-phase).
          3. Resolve contacts: velocity impulses + Baumgarte position correction.
          4. Solve joint constraints (Sequential Impulse, 4 iterations).
          5. Update positions with POST-CONTACT velocities.
        """
        from forge3d.collision.detection import detect_contacts
        from forge3d.contact.solver import solve_contacts

        # Step 1: velocity-only gravity integration
        self._bodies = [_vel_step_body(b, dt, self._gravity) for b in self._bodies]

        # Step 2: narrow-phase collision detection
        contacts = detect_contacts(
            self._bodies, self._ignored_pairs if self._ignored_pairs else None
        )

        # Heightfield contacts (dynamic bodies only — static bodies skip automatically)
        if self._heightfields:
            from forge3d.collision.heightfield import box_vs_heightfield, sphere_vs_heightfield

            for idx, body in enumerate(self._bodies):
                if body.static:
                    continue
                for hf in self._heightfields:
                    if body.shape_type == "sphere":
                        contacts.extend(sphere_vs_heightfield(body, idx, hf))
                    elif body.shape_type == "box":
                        contacts.extend(box_vs_heightfield(body, idx, hf))

        # Step 3: impulse-based contact resolution
        if contacts:
            self._bodies = solve_contacts(
                self._bodies, contacts, spring_k=self._contact_spring_k, dt=dt
            )

        # Step 4: joint constraint solving (3 iterations per step)
        if self._constraints:
            self._rebuild_index()
            for _ in range(3):
                for constraint in self._constraints:
                    constraint.apply(self._bodies, self._id_to_idx, dt)

        # Step 5: position update with final (post-contact) velocities
        self._bodies = [_pos_step_body(b, dt) for b in self._bodies]

        self._time += dt
        # Keep id→index cache consistent after list replacement
        self._rebuild_index()

        # Cache contacts for reuse by World._dispatch_events (avoids double detection)
        self._last_contacts = contacts

        # Step 6: update sleep counters
        if self._sleeping_enabled:
            self._update_sleep_counters(contacts)

    @property
    def time(self) -> float:
        return self._time

    # ── SceneSnapshot (pure data, no renderer import) ─────────────────────────

    def snapshot(self) -> Any:  # type: ignore[return]
        """Build a SceneSnapshot from the current world state.

        The only import from forge3d.render is the pure-data snapshot module.
        No OpenGL / shader / window code is imported here.
        """
        from forge3d.render.snapshot import (  # late import: pure data only
            BUILTIN_MATERIALS,
            BodySnapshot,
            CameraSnapshot,
            LightSnapshot,
            SceneSnapshot,
            TerrainSnapshot,
            Transform,
        )

        body_snaps = []
        for b in self._bodies:
            R = quat_to_rot(b.quat)
            # Copy numpy arrays; keep non-array objects (e.g. MeshData) by reference
            snap_params = {
                k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in b.shape_params.items()
            }
            body_snaps.append(
                BodySnapshot(
                    name=b.name,
                    transform=Transform(
                        position=b.pos.copy(),
                        rotation=R.copy(),
                    ),
                    shape_type=b.shape_type,
                    shape_params=snap_params,
                    material_id=b.material_id,
                )
            )

        # Camera
        if self._camera is not None:
            pos_c, tgt_c, up_c, fov = self._camera
            cam = CameraSnapshot(
                position=pos_c.copy(),
                target=tgt_c.copy(),
                up=up_c.copy(),
                fov_deg=fov,
            )
        else:
            cam = CameraSnapshot(
                position=np.array([5.0, -8.0, 4.0]),
                target=np.array([0.0, 0.0, 0.0]),
                up=np.array([0.0, 0.0, 1.0]),
                fov_deg=45.0,
            )

        lights = [
            LightSnapshot(
                direction=np.array([-0.4, -0.6, -0.7]) / np.sqrt(0.4**2 + 0.6**2 + 0.7**2),
                color=np.array([1.0, 0.95, 0.85]),
                intensity=1.0,
                cast_shadow=True,
            )
        ]

        # Terrain snapshots (heightfields)
        terrain_snaps = [
            TerrainSnapshot(
                heights=hf.heights.copy(),
                cell_size=float(hf.cell_size),
                origin=hf.origin.copy(),
                material_id=getattr(hf, "material_id", "ground"),
            )
            for hf in self._heightfields
        ]

        return SceneSnapshot(
            bodies=body_snaps,
            terrains=terrain_snaps,
            camera=cam,
            lights=lights,
            materials=dict(BUILTIN_MATERIALS),
            time=self._time,
        )

    # ── Body integration ──────────────────────────────────────────────────────────

    def _update_sleep_counters(self, contacts: list[Any]) -> None:
        """Update sleep counters and mark bodies as sleeping/awake."""
        # Collect body IDs involved in contacts (those should stay awake)
        active_ids: set[int] = set()
        for c in contacts:
            a = self._bodies[c.body_a_idx]
            active_ids.add(a.body_id)
            if c.body_b_idx >= 0:
                b = self._bodies[c.body_b_idx]
                active_ids.add(b.body_id)

        for body in self._bodies:
            if body.static:
                continue
            bid = body.body_id
            v_mag = np.linalg.norm(body.vel)
            w_mag = np.linalg.norm(body.omega)
            is_slow = v_mag < self._sleep_vel_threshold and w_mag < self._sleep_omega_threshold
            is_in_contact = bid in active_ids

            if is_slow and not is_in_contact:
                self._sleep_counters[bid] = self._sleep_counters.get(bid, 0) + 1
            else:
                self._sleep_counters[bid] = 0

    def is_sleeping(self, body_id: int) -> bool:
        """Return True if this body has been below the sleep threshold long enough."""
        return self._sleep_counters.get(body_id, 0) >= self._sleep_frames_required

    def wake_body(self, body_id: int) -> None:
        """Reset sleep counter for a body (force it awake)."""
        self._sleep_counters[body_id] = 0


def _vel_step_body(b: _Body, dt: float, gravity: np.ndarray) -> _Body:
    """Apply gravity to velocity and integrate rotation — do NOT move position."""
    if b.static:
        return b
    vel_new = b.vel + dt * gravity
    omega_q = np.array([0.0, b.omega[0], b.omega[1], b.omega[2]])
    dq = 0.5 * quat_multiply(omega_q, b.quat)
    quat_new = quat_normalize(b.quat + dt * dq)
    return replace(b, vel=vel_new, quat=quat_new)


def _pos_step_body(b: _Body, dt: float) -> _Body:
    """Update position using current (post-contact) velocity."""
    if b.static:
        return b
    return replace(b, pos=b.pos + dt * b.vel)


def _step_body(b: _Body, dt: float, gravity: np.ndarray) -> _Body:
    """Combined velocity+position step (kept for external compatibility)."""
    b2 = _vel_step_body(b, dt, gravity)
    return _pos_step_body(b2, dt)
