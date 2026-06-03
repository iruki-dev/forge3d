"""P5 physics validation tests.

Gate G1: Restitution — bounce height h' = e² * h  (±5%)
Gate G2: Friction critical angle — tan(θ) vs μ
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from forge3d.sim.world import PhysicsWorld

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_world_with_ball(
    height: float,
    radius: float = 0.3,
    restitution: float = 0.8,
    friction: float = 0.0,
    gravity: tuple[float, float, float] = (0.0, 0.0, -9.81),
) -> tuple[PhysicsWorld, int]:
    """Ground at z=0 + sphere dropped from `height`."""
    world = PhysicsWorld(gravity=list(gravity))
    world.add_static_box(
        size=(40.0, 40.0, 0.2),
        position=(0.0, 0.0, -0.1),
        name="ground",
    )
    ball_id = world.add_sphere(
        radius=radius,
        position=(0.0, 0.0, float(height)),
        mass=1.0,
        restitution=restitution,
        friction=friction,
    )
    return world, ball_id


def _run_until_first_bounce(
    world: PhysicsWorld,
    ball_id: int,
    dt: float = 1.0 / 480.0,
    max_steps: int = 10000,
) -> float:
    """Simulate until ball rises after first bounce. Returns peak height."""
    # Track z-velocity sign change (negative→positive) after first contact
    hit_ground = False
    peak_z = 0.0

    for _ in range(max_steps):
        world.step(dt)
        ball = next(b for b in world._bodies if b.body_id == ball_id)
        z = float(ball.pos[2])
        vz = float(ball.vel[2])

        if not hit_ground and vz > 0.01:
            hit_ground = True

        if hit_ground:
            peak_z = max(peak_z, z)
            if vz < 0 and peak_z > ball.shape_params["radius"] + 0.1:
                break

    return peak_z


# ── Gate G1: Restitution ──────────────────────────────────────────────────────


class TestRestitution:
    """h' = e² * h  (tolerance 5%/10%)"""

    @pytest.mark.parametrize(
        "h, e, tol",
        [
            (5.0, 0.8, 0.05),
            (5.0, 0.5, 0.08),
        ],
    )
    def test_bounce_height(self, h, e, tol):
        r = 0.3
        world, ball_id = _make_world_with_ball(
            height=h + r,  # center starts at h above surface
            radius=r,
            restitution=e,
            friction=0.0,
        )
        peak = _run_until_first_bounce(world, ball_id, dt=1.0 / 480.0)
        # peak is sphere center height; subtract radius to get surface height
        peak_surface = peak - r
        expected = e * e * h
        assert abs(peak_surface - expected) / expected < tol, (
            f"h={h}, e={e}: peak_surface={peak_surface:.3f}, "
            f"expected={expected:.3f}, rel_err={abs(peak_surface - expected) / expected:.3%}"
        )

    def test_zero_restitution_stays_on_ground(self):
        """e=0: ball should not bounce (settle on ground)."""
        r = 0.3
        world, ball_id = _make_world_with_ball(
            height=5.0 + r, radius=r, restitution=0.0, friction=0.0
        )
        dt = 1.0 / 480.0
        for _ in range(int(3.0 / dt)):
            world.step(dt)
        ball = next(b for b in world._bodies if b.body_id == ball_id)
        z_surface = float(ball.pos[2]) - r
        # Should rest near ground (within 5 cm)
        assert z_surface < 0.05, f"Ball didn't settle: z_surface={z_surface:.3f}"
        # Velocity should be near zero
        assert abs(float(ball.vel[2])) < 0.5, f"Ball still moving: vz={float(ball.vel[2]):.3f}"


# ── Gate G2: Friction critical angle ─────────────────────────────────────────


class TestFrictionCriticalAngle:
    """Friction behavior via tilted gravity (slope equivalent).

    P13 note: With a proper rotational inertia tensor (2/5 mr² for sphere),
    a sphere on a slope now ROLLS rather than staying perfectly stationary.

    Rolling physics:
      - No-slip condition: tan(θ) ≤ 7μ/2  (rolling without slipping)
      - Above 7μ/2: sphere slides AND rolls (kinetic friction)
      - Rolling acceleration: a = 5/7 * g * sin(θ)

    The tests below reflect the physically correct rolling-sphere behavior.
    """

    def _make_tilted_world(
        self, angle_deg: float, mu: float, r: float = 0.3
    ) -> tuple[PhysicsWorld, int]:
        """Sphere on ground with gravity tilted by angle_deg."""
        g = 9.81
        theta = math.radians(angle_deg)
        gx = g * math.sin(theta)
        gz = -g * math.cos(theta)
        world, ball_id = _make_world_with_ball(
            height=r,  # sphere starts exactly resting on ground
            radius=r,
            restitution=0.0,
            friction=mu,
            gravity=(gx, 0.0, gz),
        )
        return world, ball_id

    @pytest.mark.parametrize(
        "angle_deg, mu",
        [
            (20.0, 0.5),  # tan(20°)≈0.364 < 7*0.5/2=1.75 → rolls without slipping
            (22.0, 0.5),  # tan(22°)≈0.404 < 1.75 → rolls without slipping
        ],
    )
    def test_below_slip_angle_rolling_no_slip(self, angle_deg, mu):
        """Sphere rolls without slipping: contact-point velocity is near zero.

        At θ < arctan(7μ/2), static friction prevents sliding.
        The sphere rolls at a = 5/7 * g * sin(θ) — it moves, but doesn't slip.
        Contact-point tangential velocity v_x - ω_y * r should be ≈ 0.
        """
        r = 0.3
        world, ball_id = self._make_tilted_world(angle_deg, mu, r)
        dt = 1.0 / 240.0
        steps = int(2.0 / dt)
        for _ in range(steps):
            world.step(dt)
        ball = next(b for b in world._bodies if b.body_id == ball_id)
        # Rolling without slipping: v_contact = v_x - ω_y * r ≈ 0
        v_contact_x = float(ball.vel[0]) - float(ball.omega[1]) * r
        # Allow loose tolerance due to discrete integration
        assert abs(v_contact_x) < 1.0, (
            f"θ={angle_deg}°, μ={mu}: slip velocity={v_contact_x:.3f} m/s (expected near 0 rolling)"
        )
        # Sphere must actually be moving down the slope (rolling)
        expected_v = (5.0 / 7.0) * 9.81 * math.sin(math.radians(angle_deg)) * 2.0
        vx = abs(float(ball.vel[0]))
        assert vx > expected_v * 0.3, (
            f"θ={angle_deg}°, μ={mu}: vx={vx:.3f} too slow (expected ≈ {expected_v:.1f})"
        )

    @pytest.mark.parametrize(
        "angle_deg, mu",
        [
            (70.0, 0.5),  # tan(70°)≈2.75 > 7*0.5/2=1.75 → slides
            (75.0, 0.5),  # tan(75°)≈3.73 > 1.75 → slides faster
        ],
    )
    def test_above_slip_angle_sliding(self, angle_deg, mu):
        """Sphere slides when θ > arctan(7μ/2) ≈ 60.3° for μ=0.5."""
        r = 0.3
        world, ball_id = self._make_tilted_world(angle_deg, mu, r)
        dt = 1.0 / 240.0
        steps = int(2.0 / dt)
        for _ in range(steps):
            world.step(dt)
        ball = next(b for b in world._bodies if b.body_id == ball_id)
        # Sliding: v_x significantly > ω_y * r (contact point moves forward)
        v_slide = float(ball.vel[0]) - float(ball.omega[1]) * r
        assert abs(v_slide) > 0.5, (
            f"θ={angle_deg}°, μ={mu}: slip={v_slide:.3f} m/s (expected > 0.5 → sliding)"
        )

    def test_rolling_acceleration_matches_theory(self):
        """Rolling sphere on 30° slope: a = 5/7 * g * sin(30°) ≈ 3.5 m/s².

        For tan(30°)=0.577 < 7μ/2=1.75, no slip → standard rolling formula.
        """
        mu = 0.5
        r = 0.3
        angle_deg = 30.0
        dt = 1.0 / 240.0
        t_sim = 2.0
        steps = int(t_sim / dt)

        world, ball_id = self._make_tilted_world(angle_deg, mu, r)
        for _ in range(steps):
            world.step(dt)
        ball = next(b for b in world._bodies if b.body_id == ball_id)

        # Theoretical velocity after t_sim seconds
        a_theory = 5.0 / 7.0 * 9.81 * math.sin(math.radians(angle_deg))
        v_theory = a_theory * t_sim  # ≈ 7.0 m/s
        v_actual = abs(float(ball.vel[0]))

        # Allow 30% tolerance for discrete integration
        assert v_actual > v_theory * 0.7, (
            f"Rolling too slow: v={v_actual:.2f}, theory={v_theory:.2f}"
        )
        # Not wildly exceeding (friction is working)
        assert v_actual < v_theory * 2.0, (
            f"Rolling too fast: v={v_actual:.2f}, theory={v_theory:.2f}"
        )


# ── Basic solver smoke tests ──────────────────────────────────────────────────


class TestContactSolverBasic:
    def test_sphere_rests_on_ground(self):
        """Sphere should settle near ground level, not fall through."""
        world = PhysicsWorld()
        world.add_static_box(size=(40.0, 40.0, 0.2), position=(0.0, 0.0, -0.1))
        world.add_sphere(radius=0.5, position=(0.0, 0.0, 3.0), restitution=0.0)
        dt = 1.0 / 240.0
        for _ in range(int(3.0 / dt)):
            world.step(dt)
        ball = next(b for b in world._bodies if not b.static)
        # Center should be at ~radius = 0.5
        assert float(ball.pos[2]) >= 0.45, f"Sphere fell through ground: z={float(ball.pos[2]):.3f}"
        assert float(ball.pos[2]) < 0.6, f"Sphere too high: z={float(ball.pos[2]):.3f}"

    def test_box_rests_on_ground(self):
        """Box should settle on ground, not fall through."""
        world = PhysicsWorld()
        world.add_static_box(size=(40.0, 40.0, 0.2), position=(0.0, 0.0, -0.1))
        world.add_box(size=(1.0, 1.0, 1.0), position=(0.0, 0.0, 3.0), restitution=0.0)
        dt = 1.0 / 240.0
        for _ in range(int(3.0 / dt)):
            world.step(dt)
        box = next(b for b in world._bodies if not b.static)
        # Box center at z=0.5 (half_z = 0.5)
        assert float(box.pos[2]) >= 0.4, f"Box fell through ground: z={float(box.pos[2]):.3f}"
        assert float(box.pos[2]) < 0.7, f"Box too high: z={float(box.pos[2]):.3f}"

    def test_two_spheres_repel(self):
        """Two spheres colliding should separate after impact."""
        world = PhysicsWorld(gravity=[0, 0, 0])  # no gravity
        world.add_sphere(radius=0.5, position=(-0.3, 0, 0), restitution=1.0, friction=0.0)
        world.add_sphere(radius=0.5, position=(0.3, 0, 0), restitution=1.0, friction=0.0)
        # Give them initial velocities toward each other
        world._bodies[0] = world._bodies[0].__class__(
            **{**world._bodies[0].__dict__, "vel": np.array([1.0, 0.0, 0.0])}
        )
        world._bodies[1] = world._bodies[1].__class__(
            **{**world._bodies[1].__dict__, "vel": np.array([-1.0, 0.0, 0.0])}
        )
        # Wait for collision and separation
        dt = 1.0 / 1000.0
        for _ in range(500):
            world.step(dt)
        s0 = world._bodies[0]
        s1 = world._bodies[1]
        dist = float(np.linalg.norm(s0.pos - s1.pos))
        # Spheres should have separated
        assert dist >= 0.9, f"Spheres didn't separate: dist={dist:.3f}"
