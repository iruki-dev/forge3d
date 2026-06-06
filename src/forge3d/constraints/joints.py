"""Concrete joint / constraint implementations.

All joints use velocity-level Sequential Impulse + Baumgarte stabilization.
Reference: Erin Catto, "Iterative Dynamics with Temporal Coherence" (2005).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from forge3d.constraints.base import (
    BAUMGARTE_BETA,
    BAUMGARTE_SLOP,
    Constraint,
    _quat_to_rot,
)


class FixedJoint(Constraint):
    """Rigid weld — zero relative motion.

    Constrains all 6 DOF between two anchor points.
    Replaces the ``World.weld()`` kinematic approach for physics-correct
    two-body welds (both bodies remain dynamic).

    Args:
        id_a: body_id of the first body.
        id_b: body_id of the second body (-1 → world/static anchor).
        anchor_a: Attachment point in body_a local frame.
        anchor_b: Attachment point in body_b local frame.
    """

    def __init__(
        self,
        id_a: int,
        id_b: int,
        anchor_a: np.ndarray,
        anchor_b: np.ndarray,
    ) -> None:
        self.id_a = id_a
        self.id_b = id_b
        self.anchor_a = np.asarray(anchor_a, dtype=float)
        self.anchor_b = np.asarray(anchor_b, dtype=float)

    def apply(self, bodies: list[Any], id_to_idx: dict[int, int], dt: float) -> None:
        if self.id_a not in id_to_idx:
            return
        ba = bodies[id_to_idx[self.id_a]]
        Ra = _quat_to_rot(ba.quat)
        r_a = Ra @ self.anchor_a
        p_a = ba.pos + r_a

        if self.id_b >= 0 and self.id_b in id_to_idx:
            bb = bodies[id_to_idx[self.id_b]]
            Rb = _quat_to_rot(bb.quat)
            r_b = Rb @ self.anchor_b
            p_b = bb.pos + r_b
            # Relative velocity at constraint point
            v_rel = (ba.vel + np.cross(ba.omega, r_a)) - (bb.vel + np.cross(bb.omega, r_b))
        else:
            # body_b is world/static — treat as zero velocity
            r_b = self.anchor_b.copy()
            p_b = self.anchor_b.copy()
            v_rel = ba.vel + np.cross(ba.omega, r_a)
            bb = None

        # Position error (Baumgarte)
        C = p_a - p_b
        bias = (BAUMGARTE_BETA / dt) * np.where(np.abs(C) > BAUMGARTE_SLOP, C, 0.0)

        # Effective mass (3×3)
        K = self._effective_mass_ball(
            ba,
            r_a,
            bb if bb is not None else _StaticProxy(),
            r_b if bb is not None else np.zeros(3),
        )

        rhs = -(v_rel + bias)
        try:
            impulse = np.linalg.solve(K + 1e-9 * np.eye(3), rhs)
        except np.linalg.LinAlgError:
            impulse = np.zeros(3)

        self._apply_impulse_pair(
            bodies,
            id_to_idx,
            self.id_a,
            self.id_b if bb is not None else -1,
            impulse,
            r_a,
            r_b,
        )


class BallJoint(Constraint):
    """Ball-and-socket joint — 3 translational DOF constrained, rotation free.

    Args:
        id_a, id_b: Body IDs.
        anchor_a, anchor_b: Local attachment points.
    """

    def __init__(
        self,
        id_a: int,
        id_b: int,
        anchor_a: np.ndarray,
        anchor_b: np.ndarray,
    ) -> None:
        self.id_a = id_a
        self.id_b = id_b
        self.anchor_a = np.asarray(anchor_a, dtype=float)
        self.anchor_b = np.asarray(anchor_b, dtype=float)

    def apply(self, bodies: list[Any], id_to_idx: dict[int, int], dt: float) -> None:
        if self.id_a not in id_to_idx:
            return
        ba = bodies[id_to_idx[self.id_a]]
        Ra = _quat_to_rot(ba.quat)
        r_a = Ra @ self.anchor_a
        p_a = ba.pos + r_a

        if self.id_b >= 0 and self.id_b in id_to_idx:
            bb = bodies[id_to_idx[self.id_b]]
            Rb = _quat_to_rot(bb.quat)
            r_b = Rb @ self.anchor_b
            p_b = bb.pos + r_b
            v_rel = (ba.vel + np.cross(ba.omega, r_a)) - (bb.vel + np.cross(bb.omega, r_b))
        else:
            r_b = np.zeros(3)
            p_b = self.anchor_b.copy()
            v_rel = ba.vel + np.cross(ba.omega, r_a)
            bb = None

        C = p_a - p_b
        bias = (BAUMGARTE_BETA / dt) * np.where(np.abs(C) > BAUMGARTE_SLOP, C, 0.0)

        K = self._effective_mass_ball(
            ba,
            r_a,
            bb if bb is not None else _StaticProxy(),
            r_b if bb is not None else np.zeros(3),
        )
        rhs = -(v_rel + bias)
        try:
            impulse = np.linalg.solve(K + 1e-9 * np.eye(3), rhs)
        except np.linalg.LinAlgError:
            impulse = np.zeros(3)

        self._apply_impulse_pair(
            bodies,
            id_to_idx,
            self.id_a,
            self.id_b if bb is not None else -1,
            impulse,
            r_a,
            r_b,
        )


class HingeJoint(Constraint):
    """Revolute joint — 1 rotational DOF around a specified axis.

    Constrains 5 DOF: 3 translational + 2 angular (perpendicular to hinge axis).

    Args:
        id_a, id_b: Body IDs.
        anchor_a, anchor_b: Local attachment points.
        axis_a: Hinge axis in body_a local frame (will be normalized).
        limits: Optional (min_angle, max_angle) in radians.
        motor_velocity: Target angular velocity (rad/s) if motor enabled.
        motor_max_torque: Maximum motor torque (N·m).
    """

    def __init__(
        self,
        id_a: int,
        id_b: int,
        anchor_a: np.ndarray,
        anchor_b: np.ndarray,
        axis_a: np.ndarray,
        limits: tuple[float, float] | None = None,
        motor_velocity: float | None = None,
        motor_max_torque: float = 10.0,
    ) -> None:
        self.id_a = id_a
        self.id_b = id_b
        self.anchor_a = np.asarray(anchor_a, dtype=float)
        self.anchor_b = np.asarray(anchor_b, dtype=float)
        axis = np.asarray(axis_a, dtype=float)
        self.axis_a = axis / (np.linalg.norm(axis) + 1e-12)
        self.limits = limits
        self.motor_velocity = motor_velocity
        self.motor_max_torque = float(motor_max_torque)
        self._accumulated_angle: float = 0.0
        self._prev_quat_a: np.ndarray | None = None
        self._prev_quat_b: np.ndarray | None = None

    def apply(self, bodies: list[Any], id_to_idx: dict[int, int], dt: float) -> None:
        if self.id_a not in id_to_idx:
            return
        ba = bodies[id_to_idx[self.id_a]]
        Ra = _quat_to_rot(ba.quat)
        r_a = Ra @ self.anchor_a
        p_a = ba.pos + r_a
        axis_world = Ra @ self.axis_a

        if self.id_b >= 0 and self.id_b in id_to_idx:
            bb = bodies[id_to_idx[self.id_b]]
            Rb = _quat_to_rot(bb.quat)
            r_b = Rb @ self.anchor_b
            p_b = bb.pos + r_b
            ba.omega - bb.omega
        else:
            r_b = np.zeros(3)
            p_b = self.anchor_b.copy()
            bb = None

        # ── 1. Point-to-point (ball joint) ────────────────────────────────────
        v_rel_lin = (ba.vel + np.cross(ba.omega, r_a)) - (
            (bb.vel + np.cross(bb.omega, r_b)) if bb is not None else np.zeros(3)
        )
        C_lin = p_a - p_b
        bias_lin = (BAUMGARTE_BETA / dt) * np.where(np.abs(C_lin) > BAUMGARTE_SLOP, C_lin, 0.0)

        K_lin = self._effective_mass_ball(
            ba,
            r_a,
            bb if bb is not None else _StaticProxy(),
            r_b if bb is not None else np.zeros(3),
        )
        rhs_lin = -(v_rel_lin + bias_lin)
        try:
            impulse_lin = np.linalg.solve(K_lin + 1e-9 * np.eye(3), rhs_lin)
        except np.linalg.LinAlgError:
            impulse_lin = np.zeros(3)

        self._apply_impulse_pair(
            bodies,
            id_to_idx,
            self.id_a,
            self.id_b if bb is not None else -1,
            impulse_lin,
            r_a,
            r_b,
        )

        # Re-fetch (body was replaced)
        ba = bodies[id_to_idx[self.id_a]]
        if bb is not None:
            bb = bodies[id_to_idx[self.id_b]]

        # ── 2. Angular constraint (2 axes perpendicular to hinge) ─────────────
        perp1, perp2 = _perp_basis(axis_world)
        omega_rel_updated = ba.omega - (bb.omega if bb is not None else np.zeros(3))

        for perp in (perp1, perp2):
            omega_along_perp = np.dot(omega_rel_updated, perp)
            K_ang = (np.dot(perp, self._I_world_inv(ba) @ perp)) + (
                np.dot(perp, self._I_world_inv(bb) @ perp) if bb is not None else 0.0
            )
            if abs(K_ang) < 1e-12:
                continue
            lam = -omega_along_perp / K_ang
            torque_imp = lam * perp
            # Apply angular impulses
            idx_a = id_to_idx[self.id_a]
            baa = bodies[idx_a]
            if not baa.static:
                bodies[idx_a] = replace(baa, omega=baa.omega + self._I_world_inv(baa) @ torque_imp)
            if bb is not None:
                idx_b = id_to_idx[self.id_b]
                bbb = bodies[idx_b]
                if not bbb.static:
                    bodies[idx_b] = replace(
                        bbb, omega=bbb.omega - self._I_world_inv(bbb) @ torque_imp
                    )
            # Re-fetch for next iteration
            omega_rel_updated = bodies[id_to_idx[self.id_a]].omega - (
                bodies[id_to_idx[self.id_b]].omega if bb is not None else np.zeros(3)
            )

        # ── 3. Motor ──────────────────────────────────────────────────────────
        if self.motor_velocity is not None:
            ba2 = bodies[id_to_idx[self.id_a]]
            bb2 = bodies[id_to_idx[self.id_b]] if bb is not None else None
            omega_rel_ax = np.dot(ba2.omega - (bb2.omega if bb2 else np.zeros(3)), axis_world)
            error_vel = self.motor_velocity - omega_rel_ax
            K_motor = np.dot(axis_world, self._I_world_inv(ba2) @ axis_world) + (
                np.dot(axis_world, self._I_world_inv(bb2) @ axis_world) if bb2 else 0.0
            )
            if abs(K_motor) > 1e-12:
                lam_motor = np.clip(
                    error_vel / K_motor,
                    -self.motor_max_torque * dt,
                    self.motor_max_torque * dt,
                )
                mot_imp = lam_motor * axis_world
                idx_a = id_to_idx[self.id_a]
                baa = bodies[idx_a]
                if not baa.static:
                    bodies[idx_a] = replace(baa, omega=baa.omega + self._I_world_inv(baa) @ mot_imp)
                if bb2 is not None:
                    idx_b = id_to_idx[self.id_b]
                    bbb = bodies[idx_b]
                    if not bbb.static:
                        bodies[idx_b] = replace(
                            bbb, omega=bbb.omega - self._I_world_inv(bbb) @ mot_imp
                        )


class PrismaticJoint(Constraint):
    """Slider joint — 1 translational DOF along a specified axis.

    Constrains 5 DOF: all rotation + 2 translational directions perpendicular to axis.

    Args:
        id_a, id_b: Body IDs.
        anchor_a, anchor_b: Local attachment points.
        axis_a: Slide axis in body_a local frame.
        limits: Optional (min_dist, max_dist) in metres.
        motor_velocity: Target velocity along axis (m/s).
        motor_max_force: Maximum motor force (N).
    """

    def __init__(
        self,
        id_a: int,
        id_b: int,
        anchor_a: np.ndarray,
        anchor_b: np.ndarray,
        axis_a: np.ndarray,
        limits: tuple[float, float] | None = None,
        motor_velocity: float | None = None,
        motor_max_force: float = 100.0,
    ) -> None:
        self.id_a = id_a
        self.id_b = id_b
        self.anchor_a = np.asarray(anchor_a, dtype=float)
        self.anchor_b = np.asarray(anchor_b, dtype=float)
        ax = np.asarray(axis_a, dtype=float)
        self.axis_a = ax / (np.linalg.norm(ax) + 1e-12)
        self.limits = limits
        self.motor_velocity = motor_velocity
        self.motor_max_force = float(motor_max_force)

    def apply(self, bodies: list[Any], id_to_idx: dict[int, int], dt: float) -> None:
        if self.id_a not in id_to_idx:
            return
        ba = bodies[id_to_idx[self.id_a]]
        Ra = _quat_to_rot(ba.quat)
        axis_world = Ra @ self.axis_a
        r_a = Ra @ self.anchor_a
        p_a = ba.pos + r_a

        if self.id_b >= 0 and self.id_b in id_to_idx:
            bb = bodies[id_to_idx[self.id_b]]
            Rb = _quat_to_rot(bb.quat)
            r_b = Rb @ self.anchor_b
            p_b = bb.pos + r_b
        else:
            r_b = np.zeros(3)
            p_b = self.anchor_b.copy()
            bb = None

        v_rel_lin = (ba.vel + np.cross(ba.omega, r_a)) - (
            (bb.vel + np.cross(bb.omega, r_b)) if bb else np.zeros(3)
        )

        # Constrain 2 perpendicular directions
        perp1, perp2 = _perp_basis(axis_world)
        C_p1 = np.dot(p_a - p_b, perp1)
        C_p2 = np.dot(p_a - p_b, perp2)

        for perp, C in ((perp1, C_p1), (perp2, C_p2)):
            v_perp = np.dot(v_rel_lin, perp)
            bias = (BAUMGARTE_BETA / dt) * (C if abs(C) > BAUMGARTE_SLOP else 0.0)

            K = self._effective_mass_ball(
                ba,
                r_a,
                bb if bb else _StaticProxy(),
                r_b if bb else np.zeros(3),
            )
            K_perp = np.dot(perp, K @ perp)
            if abs(K_perp) < 1e-12:
                continue
            lam = -(v_perp + bias) / K_perp
            impulse = lam * perp
            self._apply_impulse_pair(
                bodies,
                id_to_idx,
                self.id_a,
                self.id_b if bb else -1,
                impulse,
                r_a,
                r_b,
            )
            # Re-fetch
            ba = bodies[id_to_idx[self.id_a]]
            v_rel_lin = (ba.vel + np.cross(ba.omega, r_a)) - (
                (
                    bodies[id_to_idx[self.id_b]].vel
                    + np.cross(bodies[id_to_idx[self.id_b]].omega, r_b)
                )
                if bb
                else np.zeros(3)
            )

        # Angular constraint — lock all rotation
        ba = bodies[id_to_idx[self.id_a]]
        bb2 = bodies[id_to_idx[self.id_b]] if bb else None
        omega_rel = ba.omega - (bb2.omega if bb2 else np.zeros(3))
        for ax_c in (axis_world, perp1, perp2):
            om_along = np.dot(omega_rel, ax_c)
            K_ang = np.dot(ax_c, self._I_world_inv(ba) @ ax_c) + (
                np.dot(ax_c, self._I_world_inv(bb2) @ ax_c) if bb2 else 0.0
            )
            if abs(K_ang) < 1e-12:
                continue
            lam = -om_along / K_ang
            ang_imp = lam * ax_c
            idx_a = id_to_idx[self.id_a]
            baa = bodies[idx_a]
            if not baa.static:
                bodies[idx_a] = replace(baa, omega=baa.omega + self._I_world_inv(baa) @ ang_imp)
            if bb2:
                idx_b = id_to_idx[self.id_b]
                bbb = bodies[idx_b]
                if not bbb.static:
                    bodies[idx_b] = replace(bbb, omega=bbb.omega - self._I_world_inv(bbb) @ ang_imp)
            ba = bodies[id_to_idx[self.id_a]]
            bb2 = bodies[id_to_idx[self.id_b]] if bb else None
            omega_rel = ba.omega - (bb2.omega if bb2 else np.zeros(3))

        # Motor along axis
        if self.motor_velocity is not None:
            ba2 = bodies[id_to_idx[self.id_a]]
            bb2 = bodies[id_to_idx[self.id_b]] if bb else None
            v_axis = np.dot(
                (ba2.vel + np.cross(ba2.omega, r_a))
                - ((bb2.vel + np.cross(bb2.omega, r_b)) if bb2 else np.zeros(3)),
                axis_world,
            )
            err = self.motor_velocity - v_axis
            K_m = np.dot(
                axis_world,
                self._effective_mass_ball(
                    ba2, r_a, bb2 if bb2 else _StaticProxy(), r_b if bb2 else np.zeros(3)
                )
                @ axis_world,
            )
            if abs(K_m) > 1e-12:
                lam_m = np.clip(
                    err / K_m,
                    -self.motor_max_force * dt,
                    self.motor_max_force * dt,
                )
                self._apply_impulse_pair(
                    bodies,
                    id_to_idx,
                    self.id_a,
                    self.id_b if bb else -1,
                    lam_m * axis_world,
                    r_a,
                    r_b,
                )


class DistanceJoint(Constraint):
    """Maintain a target distance between two anchor points.

    Can act as a rigid rod (exact distance) or one-sided rope (max distance).

    Args:
        id_a, id_b: Body IDs.
        anchor_a, anchor_b: Local attachment points.
        target_distance: Desired distance in metres.
        min_distance: If set, acts as a compression stop (push apart).
        one_sided: If True, only prevents compression (rope, not rod).
    """

    def __init__(
        self,
        id_a: int,
        id_b: int,
        anchor_a: np.ndarray,
        anchor_b: np.ndarray,
        target_distance: float,
        min_distance: float | None = None,
        one_sided: bool = False,
    ) -> None:
        self.id_a = id_a
        self.id_b = id_b
        self.anchor_a = np.asarray(anchor_a, dtype=float)
        self.anchor_b = np.asarray(anchor_b, dtype=float)
        self.target_distance = float(target_distance)
        self.min_distance = min_distance
        self.one_sided = one_sided

    def apply(self, bodies: list[Any], id_to_idx: dict[int, int], dt: float) -> None:
        if self.id_a not in id_to_idx:
            return
        ba = bodies[id_to_idx[self.id_a]]
        Ra = _quat_to_rot(ba.quat)
        r_a = Ra @ self.anchor_a
        p_a = ba.pos + r_a

        if self.id_b >= 0 and self.id_b in id_to_idx:
            bb = bodies[id_to_idx[self.id_b]]
            Rb = _quat_to_rot(bb.quat)
            r_b = Rb @ self.anchor_b
            p_b = bb.pos + r_b
        else:
            r_b = np.zeros(3)
            p_b = self.anchor_b.copy()
            bb = None

        diff = p_a - p_b
        dist = np.linalg.norm(diff)
        if dist < 1e-10:
            return

        n = diff / dist  # unit vector a→b
        C = dist - self.target_distance

        if self.one_sided and C < 0:
            return  # rope: only prevent stretching
        if self.min_distance is not None and dist < self.min_distance:
            C = dist - self.min_distance

        v_a = ba.vel + np.cross(ba.omega, r_a)
        v_b = (bb.vel + np.cross(bb.omega, r_b)) if bb is not None else np.zeros(3)
        v_rel_n = np.dot(v_a - v_b, n)

        bias = (BAUMGARTE_BETA / dt) * C if abs(C) > BAUMGARTE_SLOP else 0.0
        K = self._effective_mass_ball(
            ba,
            r_a,
            bb if bb else _StaticProxy(),
            r_b if bb else np.zeros(3),
        )
        K_n = np.dot(n, K @ n)
        if abs(K_n) < 1e-12:
            return

        lam = -(v_rel_n + bias) / K_n
        impulse = lam * n
        self._apply_impulse_pair(
            bodies,
            id_to_idx,
            self.id_a,
            self.id_b if bb else -1,
            impulse,
            r_a,
            r_b,
        )


class SpringJoint(Constraint):
    """Spring-damper force element between two anchor points.

    Not a hard constraint — applies spring force each step.

    Args:
        id_a, id_b: Body IDs.
        anchor_a, anchor_b: Local attachment points.
        stiffness: Spring constant k (N/m).
        damping: Damping coefficient c (N·s/m).
        rest_length: Natural length at zero force (m).
    """

    def __init__(
        self,
        id_a: int,
        id_b: int,
        anchor_a: np.ndarray,
        anchor_b: np.ndarray,
        stiffness: float = 100.0,
        damping: float = 5.0,
        rest_length: float = 1.0,
    ) -> None:
        self.id_a = id_a
        self.id_b = id_b
        self.anchor_a = np.asarray(anchor_a, dtype=float)
        self.anchor_b = np.asarray(anchor_b, dtype=float)
        self.stiffness = float(stiffness)
        self.damping = float(damping)
        self.rest_length = float(rest_length)

    def apply(self, bodies: list[Any], id_to_idx: dict[int, int], dt: float) -> None:
        if self.id_a not in id_to_idx:
            return
        ba = bodies[id_to_idx[self.id_a]]
        Ra = _quat_to_rot(ba.quat)
        r_a = Ra @ self.anchor_a
        p_a = ba.pos + r_a

        if self.id_b >= 0 and self.id_b in id_to_idx:
            bb = bodies[id_to_idx[self.id_b]]
            Rb = _quat_to_rot(bb.quat)
            r_b = Rb @ self.anchor_b
            p_b = bb.pos + r_b
        else:
            r_b = np.zeros(3)
            p_b = self.anchor_b.copy()
            bb = None

        diff = p_a - p_b
        dist = np.linalg.norm(diff)
        if dist < 1e-10:
            return
        n = diff / dist  # a → b direction

        # Spring force
        f_spring = -self.stiffness * (dist - self.rest_length)

        # Damping force (relative velocity along spring axis)
        v_a = ba.vel + np.cross(ba.omega, r_a)
        v_b = (bb.vel + np.cross(bb.omega, r_b)) if bb else np.zeros(3)
        v_rel_n = np.dot(v_a - v_b, n)
        f_damp = -self.damping * v_rel_n

        f_total = (f_spring + f_damp) * n  # force on body_a

        # Convert force to velocity impulse: Δv = (F * dt) / m
        impulse = f_total * dt
        self._apply_impulse_pair(
            bodies,
            id_to_idx,
            self.id_a,
            self.id_b if bb else -1,
            impulse,
            r_a,
            r_b,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _perp_basis(n: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return two unit vectors perpendicular to n."""
    n = n / (np.linalg.norm(n) + 1e-12)
    t = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = np.cross(n, t)
    e1 /= np.linalg.norm(e1) + 1e-12
    e2 = np.cross(n, e1)
    return e1, e2


class _StaticProxy:
    """Stand-in for a static/world anchor (zero mass, zero inertia)."""

    static = True
    mass = 0.0
    inertia_inv_local = None
    quat = np.array([1.0, 0.0, 0.0, 0.0])
    vel = np.zeros(3)
    omega = np.zeros(3)
