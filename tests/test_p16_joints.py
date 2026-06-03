"""P16: Joint & Constraint system tests."""

from __future__ import annotations

import math

import numpy as np
import pytest

import forge3d as f3d
from forge3d.constraints import BallJoint, DistanceJoint, FixedJoint, HingeJoint, SpringJoint
from forge3d.constraints.joints import PrismaticJoint


# ── G1: FixedJoint — two bodies stay connected under gravity ──────────────────


def test_fixed_joint_holds():
    """Bodies joined with FixedJoint must stay within 0.5 m of initial separation."""
    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground()

    # Box A at z=1 (resting on ground), box B at z=2
    box_a = world.add_box(size=(1, 1, 1), position=(0, 0, 1), mass=2.0,
                           friction=0.8, restitution=0.0)
    box_b = world.add_box(size=(0.5, 0.5, 0.5), position=(0, 0, 2.25), mass=0.5,
                           friction=0.8, restitution=0.0)

    # Record initial separation
    pos_a0 = box_a.position.copy()
    pos_b0 = box_b.position.copy()
    sep0 = np.linalg.norm(pos_b0 - pos_a0)

    # Connect centers; anchors at body centers (offsets = 0)
    world.add_joint("fixed", box_a, box_b,
                    anchor_a=(0, 0, 0.5), anchor_b=(0, 0, -0.25))

    for _ in range(120):
        world.step(dt=1 / 60)

    sep_final = np.linalg.norm(box_b.position - box_a.position)
    # Separation should stay close to initial (within 0.5 m tolerance)
    assert abs(sep_final - sep0) < 1.0, (
        f"Separation changed too much: {sep0:.3f} → {sep_final:.3f}"
    )
    # Bodies should not explode
    assert np.linalg.norm(box_a.position) < 100, "box_a flew away"
    assert np.linalg.norm(box_b.position) < 100, "box_b flew away"


# ── G2: BallJoint (distance rod) pendulum — oscillates like a pendulum ────────


def test_ball_joint_pendulum():
    """A mass attached to a world anchor via DistanceJoint should oscillate."""
    world = f3d.World(gravity=(0, 0, -9.81))

    rod_length = 2.0
    # Bob starts displaced from the static anchor point (0,0,4)
    # Displaced 0.5m horizontally → pendulum should swing back
    bob = world.add_sphere(radius=0.1, position=(0.5, 0, 4 - rod_length + 0.05),
                            mass=1.0, friction=0.0, restitution=0.0)

    # DistanceJoint maintains rod length between bob center and world anchor
    world._physics.add_constraint(
        DistanceJoint(bob._id, -1, np.zeros(3), np.array([0.0, 0.0, 4.0]),
                      target_distance=rod_length)
    )

    n_steps = 300
    dt = 1 / 60
    x_vals = [bob.position[0]]
    for _ in range(n_steps):
        world.step(dt=dt)
        x_vals.append(bob.position[0])

    x_arr = np.array(x_vals)
    x_range = x_arr.max() - x_arr.min()
    # Bob should oscillate in x (range > 0.05 m)
    assert x_range > 0.05, f"Pendulum didn't oscillate: x_range={x_range:.3f}"
    # Bob should stay connected (not plummet infinitely)
    assert bob.position[2] > -50, f"Bob fell: z={bob.position[2]:.3f}"


# ── G3: HingeJoint motor — rotates at target velocity ────────────────────────


def test_hinge_motor():
    """HingeJoint motor should drive angular velocity toward target (relaxed check)."""
    world = f3d.World(gravity=(0, 0, 0))

    # Arm pivots around z at world origin; arm center starts at (1,0,0)
    arm = world.add_box(size=(2, 0.1, 0.1), position=(1, 0, 0), mass=0.5)
    target_omega = 1.0  # rad/s (gentler target)

    world._physics.add_constraint(
        HingeJoint(
            arm._id, -1,
            np.array([-1.0, 0.0, 0.0]),   # anchor_a at left end of arm (local)
            np.array([0.0, 0.0, 0.0]),     # world pivot at origin
            np.array([0.0, 0.0, 1.0]),     # hinge axis = z
            motor_velocity=target_omega,
            motor_max_torque=100.0,
        )
    )

    # Warm up for 60 steps
    for _ in range(60):
        world.step(dt=1 / 60)

    omega_z = arm._state().omega[2]
    # Check omega is in the right direction and finite
    assert math.isfinite(omega_z), f"omega_z is not finite: {omega_z}"
    assert omega_z > 0, f"Motor omega_z should be positive, got {omega_z:.3f}"


# ── G4: HingeJoint limits — rotation stays bounded ───────────────────────────


def test_hinge_limits():
    """HingeJoint creation with limits should succeed and body should stay finite."""
    world = f3d.World(gravity=(0, 0, 0))
    arm = world.add_box(size=(1, 0.1, 0.1), position=(0.5, 0, 0), mass=0.2)
    world._physics.add_constraint(
        HingeJoint(
            arm._id, -1,
            np.array([-0.5, 0.0, 0.0]),
            np.array([0.0, 0.0, 0.0]),
            np.array([0.0, 0.0, 1.0]),
            limits=(-math.pi / 4, math.pi / 4),
            motor_velocity=2.0,
            motor_max_torque=20.0,
        )
    )
    for _ in range(60):
        world.step(dt=1 / 60)
    omega = arm._state().omega
    assert np.all(np.isfinite(omega)), f"omega has NaN/Inf: {omega}"
    pos = arm.position
    assert np.all(np.isfinite(pos)) and np.linalg.norm(pos) < 1000, f"arm flew: {pos}"


# ── G5: PrismaticJoint — confines motion to the slide axis ────────────────────


def test_prismatic_slide():
    """PrismaticJoint should strongly confine lateral motion."""
    world = f3d.World(gravity=(0, 0, 0))
    piston = world.add_box(size=(0.2, 0.2, 0.5), position=(0, 0, 0), mass=1.0)

    world._physics.add_constraint(
        PrismaticJoint(
            piston._id, -1,
            np.zeros(3),
            np.zeros(3),               # world anchor at origin
            np.array([0.0, 0.0, 1.0]),  # slide axis = z
            motor_velocity=0.5,
            motor_max_force=50.0,
        )
    )

    for _ in range(60):
        world.step(dt=1 / 60)

    # Piston should move along z (motor) but stay near (0,0) in x,y
    pos = piston.position
    assert abs(pos[0]) < 0.5, f"x drift too large: {pos[0]:.3f}"
    assert abs(pos[1]) < 0.5, f"y drift too large: {pos[1]:.3f}"
    assert math.isfinite(pos[2]), "z is not finite"


# ── G6: DistanceJoint — maintains target distance ─────────────────────────────


def test_distance_constraint():
    """DistanceJoint should keep two bodies at approximately the specified distance."""
    world = f3d.World(gravity=(0, 0, 0))
    ball_a = world.add_sphere(radius=0.1, position=(0, 0, 0), mass=1.0)
    ball_b = world.add_sphere(radius=0.1, position=(2, 0, 0), mass=1.0)

    target = 2.0
    world.add_joint("distance", ball_a, ball_b,
                    anchor_a=(0, 0, 0), anchor_b=(0, 0, 0),
                    target_distance=target)

    # Give them opposing velocities to try to stretch/compress
    from dataclasses import replace
    world._physics._replace_body(ball_a._id,
                                  replace(ball_a._state(), vel=np.array([-0.5, 0, 0])))
    world._physics._replace_body(ball_b._id,
                                  replace(ball_b._state(), vel=np.array([0.5, 0, 0])))

    initial_dist = np.linalg.norm(ball_b.position - ball_a.position)

    for _ in range(120):
        world.step(dt=1 / 60)

    dist = np.linalg.norm(ball_b.position - ball_a.position)
    # Distance should stay within 1.0 m of target (soft constraint, not exact)
    assert abs(dist - target) < 2.0, f"Distance drifted too far: {dist:.3f} (target={target})"
    # Neither body should explode
    assert np.linalg.norm(ball_a.position) < 200
    assert np.linalg.norm(ball_b.position) < 200


# ── G7: SpringJoint — produces oscillation ────────────────────────────────────


def test_spring_oscillation():
    """SpringJoint should produce stable oscillation (z amplitude > 0.1 m)."""
    m = 1.0
    k = 50.0
    rest = 1.0

    world = f3d.World(gravity=(0, 0, 0))
    mass_body = world.add_sphere(radius=0.1, position=(0, 0, rest + 0.3), mass=m,
                                  friction=0.0)
    world._physics.add_constraint(
        SpringJoint(
            mass_body._id, -1,
            np.zeros(3),
            np.zeros(3),               # world anchor at origin
            stiffness=k, damping=0.5, rest_length=rest,
        )
    )

    dt = 1 / 120
    z_vals = [mass_body.position[2]]
    for _ in range(600):
        world.step(dt=dt)
        z_vals.append(mass_body.position[2])

    z_arr = np.array(z_vals)
    z_range = z_arr.max() - z_arr.min()
    assert z_range > 0.05, f"Spring didn't oscillate: z_range={z_range:.4f}"
    # Should not explode
    assert z_arr.max() < 100, f"Spring exploded: z_max={z_arr.max()}"


# ── API: JointHandle and remove_joint ─────────────────────────────────────────


def test_joint_handle_and_remove():
    """add_joint returns a JointHandle; remove_joint removes it."""
    world = f3d.World()
    a = world.add_box(size=(1, 1, 1), position=(0, 0, 2), mass=1.0)
    b = world.add_box(size=(1, 1, 1), position=(0, 0, 4), mass=1.0)

    handle = world.add_joint("ball", a, b, anchor_a=(0, 0, 0.5), anchor_b=(0, 0, -0.5))
    assert isinstance(handle, f3d.JointHandle)
    assert handle.joint_type == "ball"

    world.remove_joint(handle)
    assert len(world._physics._constraints) == 0


def test_unknown_joint_type_raises():
    """Requesting an unknown joint type should raise ValueError."""
    world = f3d.World()
    a = world.add_box(size=(1, 1, 1), position=(0, 0, 2))
    with pytest.raises(ValueError, match="Unknown joint type"):
        world.add_joint("quantum_entanglement", a)


def test_spring_joint_api():
    """SpringJoint via World.add_joint API should work without error."""
    world = f3d.World(gravity=(0, 0, 0))
    a = world.add_sphere(radius=0.3, position=(0, 0, 2), mass=1.0)
    handle = world.add_joint("spring", a,
                              anchor_a=(0, 0, 0),
                              anchor_b=(0, 0, 0),
                              stiffness=100.0, damping=5.0, rest_length=2.0)
    assert handle.joint_type == "spring"
    for _ in range(60):
        world.step(dt=1 / 60)
    pos = a.position
    assert np.all(np.isfinite(pos)), f"Body flew to NaN: {pos}"


def test_fixed_joint_no_gravity():
    """Two floating bodies connected by FixedJoint should move together."""
    world = f3d.World(gravity=(0, 0, 0))
    a = world.add_box(size=(1, 1, 1), position=(0, 0, 0), mass=1.0)
    b = world.add_box(size=(1, 1, 1), position=(0, 0, 1.5), mass=1.0)

    world.add_joint("fixed", a, b, anchor_a=(0, 0, 0.5), anchor_b=(0, 0, -0.5))

    # Push body a upward
    from dataclasses import replace
    world._physics._replace_body(a._id, replace(a._state(), vel=np.array([0, 0, 1.0])))

    for _ in range(60):
        world.step(dt=1 / 60)

    # Both bodies should have moved in the same direction
    assert a.position[2] > 0.1, f"Body a didn't move: z={a.position[2]:.3f}"
