"""CharacterController — kinematic capsule-based player controller.

Provides ground detection, velocity-based movement, jump, and glide
so game code doesn't need to re-implement these from scratch each time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from forge3d.facade import Body, World


class CharacterController:
    """Kinematic character controller backed by a capsule rigid body.

    Returned by :meth:`forge3d.World.add_character`.

    Typical game loop::

        cc = world.add_character(position=(0, 0, 2), height=1.8, radius=0.3)

        while viewer.is_open:
            inp = viewer.input
            dx = inp.axis("right") - inp.axis("left")   # -1 … 1
            dy = inp.axis("up")    - inp.axis("down")
            cc.move(direction=(dx, dy, 0), speed=5.5, dt=viewer.dt)
            if inp.just_pressed("space"):
                cc.jump(impulse=6.4)
            world.step(viewer.dt)

    Attributes
    ----------
    body        : The underlying :class:`Body` (capsule).
    is_grounded : True when the character is standing on solid ground.
    is_airborne : True when the character is not grounded.
    velocity    : Current linear velocity (3,).
    """

    # Ground detection ray length (slightly longer than capsule half-height)
    _GROUND_RAY_EXTRA = 0.15

    def __init__(
        self,
        world: World,
        body: Body,
        height: float,
        radius: float,
        ground_layer_mask: int = 0xFFFF,
        ground_check_hz: float = 60.0,
    ) -> None:
        self._world = world
        self.body = body
        self._height = float(height)
        self._radius = float(radius)
        self._ground_layer_mask = ground_layer_mask
        self._grounded = False
        self._vertical_vel = 0.0

        # Throttle ground-detection raycast. At 10 Hz (bots) this cuts the
        # per-move cost from ~1 ms to ~0.017 ms with no gameplay difference.
        self._ground_check_interval = 1.0 / max(1.0, float(ground_check_hz))
        self._ground_check_timer = 0.0

        # Jump cooldown prevents infinite jumping when the capsule is still
        # close to the ground in the frame right after a jump.
        self._jump_cooldown: float = 0.0

        # Platform riding: track which body we're standing on and its last position
        # so we can apply its displacement to ourselves each frame.
        self._ground_body_id: int | None = None  # None → terrain / nothing
        self._ground_body_last_pos: Any | None = None  # np.ndarray

    # ── State queries ─────────────────────────────────────────────────────────

    @property
    def is_grounded(self) -> bool:
        """True if the character is touching the ground."""
        return self._grounded

    @property
    def is_airborne(self) -> bool:
        """True if the character is in the air."""
        return not self._grounded

    @property
    def velocity(self) -> np.ndarray:
        """Current linear velocity (3,) in m/s."""
        return self.body.velocity

    @property
    def position(self) -> np.ndarray:
        """Current world position (3,)."""
        return self.body.position

    # ── Movement API ──────────────────────────────────────────────────────────

    def move(
        self,
        direction: Any,
        speed: float,
        dt: float,
    ) -> None:
        """Apply horizontal movement toward *direction* at *speed* m/s.

        Also carries the character on moving platforms automatically — no
        manual delta-passing needed.

        Parameters
        ----------
        direction : (3,) movement vector (only x/y components used unless z != 0).
                    Does **not** need to be normalised.
        speed     : Maximum movement speed in m/s.
        dt        : Frame delta-time in seconds.
        """
        self._update_ground(dt)

        d = np.asarray(direction, dtype=float)
        norm = np.linalg.norm(d[:2])
        if norm > 1e-9:
            d_xz = d.copy()
            d_xz[2] = 0.0
            d_xz[:2] /= norm
            target_vel = d_xz * float(speed)
            cur = self.body.velocity.copy()
            cur[:2] = target_vel[:2]
            self.body.set_velocity(cur)

    def jump(self, impulse: float = 5.0) -> None:
        """Apply an upward velocity impulse if grounded.

        Parameters
        ----------
        impulse : Upward speed added in m/s (think: initial jump velocity).
        """
        if self._grounded and self._jump_cooldown <= 0.0:
            vel = self.body.velocity.copy()
            vel[2] = float(impulse)
            self.body.set_velocity(vel)
            self._grounded = False
            self._jump_cooldown = 0.40  # 400 ms before the next jump is allowed

    def move_camera_relative(
        self,
        inp: Any,
        cam: Any,
        speed: float,
        dt: float,
        *,
        forward_key: str = "w",
        back_key: str = "s",
        left_key: str = "a",
        right_key: str = "d",
    ) -> np.ndarray:
        """Move relative to the camera's facing direction.

        Eliminates the boilerplate yaw-angle → forward/right vector pattern that
        every third-person game repeats.  Returns the world-space move vector
        (useful for updating a ``facing`` direction)::

            move = cc.move_camera_relative(inp, cam, speed=7.2, dt=dt)

        Parameters
        ----------
        inp         : :class:`~forge3d.input.Input` or
                      :class:`~forge3d.input.ScriptedInput`.
        cam         : :class:`~forge3d.camera.OrbitCamera` — only its
                      ``forward_azimuth`` property is used.
        speed       : Horizontal movement speed in m/s.
        dt          : Frame delta-time in seconds.
        forward_key : Key for forward movement (default ``'w'``).
        back_key    : Key for backward movement (default ``'s'``).
        left_key    : Key for left movement (default ``'a'``).
        right_key   : Key for right movement (default ``'d'``).

        Returns
        -------
        np.ndarray
            The (3,) world-space move vector (zero if no input).
        """
        import math

        yaw = math.radians(float(cam.forward_azimuth))
        fwd = np.array([math.cos(yaw), math.sin(yaw), 0.0])
        right = np.array([math.sin(yaw), -math.cos(yaw), 0.0])
        mx = inp.axis(left_key, right_key)
        my = inp.axis(back_key, forward_key)
        move = fwd * my + right * mx
        self.move(direction=tuple(move), speed=speed, dt=dt)
        return move

    def glide(self, target_fall_speed: float = -1.5, dt: float = 1 / 60) -> None:
        """Reduce falling speed to *target_fall_speed* for a glide effect.

        Call each frame while glide input is held.

        Parameters
        ----------
        target_fall_speed : Target downward z-velocity (negative = downward).
        dt                : Frame delta-time (used to smooth the transition).
        """
        vel = self.body.velocity.copy()
        if vel[2] < target_fall_speed:
            vel[2] = max(vel[2] + 20.0 * dt, target_fall_speed)
            self.body.set_velocity(vel)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _update_ground(self, dt: float) -> None:
        """Update is_grounded via downward raycast (throttled + jump-cooldown aware).

        Also applies platform displacement: if the body we were standing on
        has moved since the last check, we teleport ourselves by the same delta.
        """
        # Decrement jump cooldown unconditionally every call
        if self._jump_cooldown > 0.0:
            self._jump_cooldown = max(0.0, self._jump_cooldown - dt)
            self._grounded = False
            self._ground_body_id = None
            self._ground_body_last_pos = None
            return

        self._ground_check_timer += dt
        if self._ground_check_timer < self._ground_check_interval:
            # Apply stored platform delta even between checks
            self._apply_platform_delta()
            return
        self._ground_check_timer = 0.0

        # Apply platform delta from last frame before updating ground state
        self._apply_platform_delta()

        pos = self.body.position
        ray_len = self._height / 2.0 + self._radius + self._GROUND_RAY_EXTRA
        hit = self._world.raycast(
            origin=pos,
            direction=(0.0, 0.0, -1.0),
            max_dist=ray_len,
            layer_mask=self._ground_layer_mask,
        )
        self._grounded = hit is not None

        # Track which body (or terrain) we're on for platform riding
        if hit is not None and hit.body is not None:
            self._ground_body_id = hit.body._id
            self._ground_body_last_pos = hit.body.position.copy()
        else:
            # Terrain hit (body is None) or no hit
            self._ground_body_id = None
            self._ground_body_last_pos = None

    def _apply_platform_delta(self) -> None:
        """If standing on a moving body, carry ourselves with it."""
        if self._ground_body_id is None or self._ground_body_last_pos is None:
            return
        body = self._world._bodies.get(self._ground_body_id)
        if body is None:
            self._ground_body_id = None
            self._ground_body_last_pos = None
            return
        try:
            current_pos = body.position
            delta = current_pos - self._ground_body_last_pos
            if np.linalg.norm(delta) > 1e-6:
                self.body.set_position(self.body.position + delta)
            self._ground_body_last_pos = current_pos.copy()
        except Exception:
            self._ground_body_id = None
            self._ground_body_last_pos = None

    def __repr__(self) -> str:
        pos = self.position
        g = "grounded" if self._grounded else "airborne"
        return f"CharacterController({g}, pos=({pos[0]:.1f},{pos[1]:.1f},{pos[2]:.1f}))"
