"""Iterative impulse-based contact solver (PGS) with angular dynamics.

Algorithm — per step:
  PRE-COMPUTE (before PGS loop):
    v_n_pre = normal relative velocity at contact (at start of step)
    restitution_target = max(0, -e * v_n_pre)  if approaching, else 0

  PGS loop (N_ITER iterations):
    For each contact c:
      1. Compute current v_n at contact (includes ω × r lever arm).
      2. Normal impulse drives v_n → restitution_target; clamp λ_n ≥ 0.
      3. Friction impulse (2 tangential dirs); clamp |λ_t| ≤ μ * λ_n.
      4. Apply impulse changes immediately (sequential / Gauss-Seidel).

  POST-PGS:
    Baumgarte position correction (separate from velocity constraint).
    This avoids the interaction between position bias and restitution.

Effective mass along direction d with lever arms r_a, r_b:
  K = 1/m_a + 1/m_b + (r_a×d)·I_a⁻¹·(r_a×d) + (r_b×d)·I_b⁻¹·(r_b×d)
  Impulse J to change v_n by Δv: J = Δv / K

Bodies with inertia_local=None → point mass (zero rotational contribution).
Static bodies → infinite mass and inertia (no velocity update).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from forge3d.collision.detection import ContactPoint, _cross3, _quat_to_rot_unit

# Reusable zero vector — avoids np.zeros(3) allocation in hot loops
_ZERO3 = np.zeros(3)
_ZERO33 = np.zeros((3, 3))

# ── Tuning parameters ─────────────────────────────────────────────────────────

N_ITER = 6  # PGS iterations per step (6 sufficient for stable resting contact)
RESTITUTION_THRESHOLD = 0.5  # m/s: below this, treat e=0 (Zeno prevention)
BAUMGARTE_BETA = 0.3  # position-correction fraction per step (post-PGS)
PENETRATION_SLOP = 0.001  # m: allowed overlap before correction kicks in
VELOCITY_EPS = 1e-9  # m/s: tangential velocity threshold


# ── Public interface ──────────────────────────────────────────────────────────


def solve_contacts(
    bodies: list[Any],
    contacts: list[ContactPoint],
    spring_k: float = 0.0,
    dt: float = 1.0 / 60.0,
    _use_rust: bool | None = None,
) -> list[Any]:
    """Impulse-based contact solver: sequential PGS with pre-computed batch data.

    Uses Gauss-Seidel ordering (contacts processed sequentially so friction
    converges correctly for coupled constraints like pinch grasps), but all
    per-contact constants are pre-computed as NumPy arrays to avoid repeat
    work.  Inner loop variables are Python scalars / list lookups — the
    bottleneck is Python loop iterations × contacts, bounded by N_ITER × C.
    """
    if not contacts:
        return list(bodies)

    # ── Rust PGS 경로 ──────────────────────────────────────────────────────────
    # 선형 속도만 있는(각 운동량 무시 가능) 단순 씬에서 Rust 가속 사용.
    # spring_k, restitution, angular dynamics 포함 씬은 Python 경로 유지.
    from forge3d.backend import USE_RUST_CORE
    _rust = (_use_rust if _use_rust is not None else USE_RUST_CORE)
    if _rust and spring_k == 0.0 and all(b.inertia_local is None for b in bodies if not b.static):
        return _solve_contacts_rust(bodies, contacts, dt)

    vels:   list[np.ndarray] = [b.vel.copy()   if not b.static else _ZERO3.copy() for b in bodies]
    omegas: list[np.ndarray] = [b.omega.copy() if not b.static else _ZERO3.copy() for b in bodies]
    poss:   list[np.ndarray] = [b.pos.copy() for b in bodies]

    I_inv: list[np.ndarray] = [_inv_inertia_world(b) for b in bodies]

    nc = len(contacts)
    lambda_n  = np.zeros(nc)
    lambda_t1 = np.zeros(nc)
    lambda_t2 = np.zeros(nc)

    tangents: list[tuple[np.ndarray, np.ndarray]] = [_tangent_pair(c.normal) for c in contacts]

    # Restitution targets (pre-step velocities)
    v_n_target = np.zeros(nc)
    for ci, c in enumerate(contacts):
        v_n_pre = _contact_v_n(c, bodies, vels, omegas)
        if v_n_pre < -RESTITUTION_THRESHOLD:
            ia, ib = c.body_a_idx, c.body_b_idx
            b_static = ib < 0 or bodies[ib].static
            e = bodies[ia].restitution if b_static else 0.5 * (bodies[ia].restitution + bodies[ib].restitution)
            v_n_target[ci] = -e * v_n_pre

    # Pre-computed per-contact constants
    c_ia     = [c.body_a_idx for c in contacts]
    c_ib     = [c.body_b_idx for c in contacts]
    c_static = [ib < 0 or bodies[ib].static for ib in c_ib]
    c_inv_ma = [0.0 if bodies[ia].static else 1.0 / bodies[ia].mass for ia in c_ia]
    c_inv_mb = [0.0 if (bs or ib < 0) else 1.0 / bodies[ib].mass for ib, bs in zip(c_ib, c_static)]
    c_I_a    = [I_inv[ia] for ia in c_ia]
    c_I_b    = [I_inv[ib] if not bs and ib >= 0 else _ZERO33 for ib, bs in zip(c_ib, c_static)]
    c_r_a    = [c.pos - bodies[ia].pos for c, ia in zip(contacts, c_ia)]
    c_r_b    = [c.pos - bodies[ib].pos if not bs and ib >= 0 else _ZERO3 for c, ib, bs in zip(contacts, c_ib, c_static)]
    c_K_n    = [_eff_K(ra, rb, c.normal, ima, imb, Ia, Ib)
                for c, ra, rb, ima, imb, Ia, Ib in zip(contacts, c_r_a, c_r_b, c_inv_ma, c_inv_mb, c_I_a, c_I_b)]
    c_K_t    = [(_eff_K(ra, rb, t1, ima, imb, Ia, Ib), _eff_K(ra, rb, t2, ima, imb, Ia, Ib))
                for (t1, t2), ra, rb, ima, imb, Ia, Ib in zip(tangents, c_r_a, c_r_b, c_inv_ma, c_inv_mb, c_I_a, c_I_b)]
    c_mu     = [bodies[ia].friction if bs else 0.5 * (bodies[ia].friction + bodies[ib].friction)
                for ia, ib, bs in zip(c_ia, c_ib, c_static)]

    spring_pairs: set[tuple[int, int]] = set()

    for _iteration in range(N_ITER):
        for ci, c in enumerate(contacts):
            ia = c_ia[ci]; ib = c_ib[ci]; b_static = c_static[ci]
            inv_ma = c_inv_ma[ci]; inv_mb = c_inv_mb[ci]
            I_a = c_I_a[ci]; I_b = c_I_b[ci]
            r_a = c_r_a[ci]; r_b = c_r_b[ci]
            K_n = c_K_n[ci]
            if K_n < 1e-12:
                continue

            v_n = _contact_v_n_fast(c.pos, c.normal, ia, ib, b_static, r_a, r_b, vels, omegas)
            delta_n = (v_n_target[ci] - v_n) / K_n

            if spring_k > 0.0:
                pair = (ia, ib)
                if pair not in spring_pairs:
                    spring_pairs.add(pair)
                    delta_n = max(delta_n, spring_k * c.depth * dt)

            lambda_n_new = max(0.0, lambda_n[ci] + delta_n)
            actual_n = lambda_n_new - lambda_n[ci]
            lambda_n[ci] = lambda_n_new
            if abs(actual_n) > 1e-14:
                _apply_impulse(ia, ib, actual_n * c.normal, r_a, r_b, inv_ma, inv_mb, I_a, I_b, vels, omegas)

            mu = c_mu[ci]
            if mu < 1e-12 or lambda_n[ci] < 1e-12:
                continue

            t1, t2 = tangents[ci]
            K_t1, K_t2 = c_K_t[ci]
            for t_vec, K_t, lt, idx in [(t1, K_t1, lambda_t1, ci), (t2, K_t2, lambda_t2, ci)]:
                if K_t < 1e-12:
                    continue
                v_a_c = vels[ia] + _cross3(omegas[ia], r_a)
                v_b_c = (vels[ib] + _cross3(omegas[ib], r_b) if not b_static and ib >= 0 else _ZERO3)
                v_t = float(np.dot(v_a_c - v_b_c, t_vec))
                lt_max = mu * lambda_n[ci]
                raw = lt[idx] + (-v_t / K_t)
                lt_new = raw if -lt_max <= raw <= lt_max else max(-lt_max, min(lt_max, raw))
                actual_t = lt_new - lt[idx]
                lt[idx] = lt_new
                if abs(actual_t) > 1e-14:
                    _apply_impulse(ia, ib, actual_t * t_vec, r_a, r_b, inv_ma, inv_mb, I_a, I_b, vels, omegas)

    # Baumgarte position correction
    for c in contacts:
        ia = c.body_a_idx; ib = c.body_b_idx
        b_static = ib < 0 or bodies[ib].static
        excess = max(0.0, c.depth - PENETRATION_SLOP)
        if excess < 1e-6:
            continue
        inv_ma = 0.0 if bodies[ia].static else 1.0 / bodies[ia].mass
        inv_mb = 0.0 if b_static or ib < 0 else 1.0 / bodies[ib].mass
        total_inv = inv_ma + inv_mb
        if total_inv < 1e-12:
            continue
        corr = BAUMGARTE_BETA * excess
        poss[ia] += corr * (inv_ma / total_inv) * c.normal
        if not b_static and ib >= 0:
            poss[ib] -= corr * (inv_mb / total_inv) * c.normal

    result: list[Any] = list(bodies)
    for i, b in enumerate(bodies):
        if not b.static:
            result[i] = replace(b, vel=vels[i], omega=omegas[i], pos=poss[i])
    return result


# ── Batch (vectorized) helpers ────────────────────────────────────────────────


def _bcross(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Vectorized cross product for (C, 3) arrays.  Avoids np.cross overhead."""
    return np.stack([
        a[:, 1]*b[:, 2] - a[:, 2]*b[:, 1],
        a[:, 2]*b[:, 0] - a[:, 0]*b[:, 2],
        a[:, 0]*b[:, 1] - a[:, 1]*b[:, 0],
    ], axis=1)


def _batch_tangent_pairs(
    normals: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Stable tangent frames for all contacts at once.  Returns (t1, t2) each (C, 3)."""
    C = len(normals)
    # Choose reference vector not parallel to n
    ref = np.where(np.abs(normals[:, 0:1]) < 0.9,
                   np.broadcast_to([1., 0., 0.], (C, 3)),
                   np.broadcast_to([0., 1., 0.], (C, 3))).copy()
    t1 = _bcross(normals, ref)
    t1_len = np.linalg.norm(t1, axis=1, keepdims=True)
    t1 /= np.where(t1_len > 1e-10, t1_len, 1.0)
    t2 = _bcross(normals, t1)
    t2 /= np.linalg.norm(t2, axis=1, keepdims=True).clip(1e-10)
    return t1, t2


def _batch_apply(
    ia: np.ndarray,
    ib: np.ndarray,
    is_sb: np.ndarray,
    inv_ma: np.ndarray,
    inv_mb: np.ndarray,
    I_a: np.ndarray,
    I_b: np.ndarray,
    r_a: np.ndarray,
    r_b: np.ndarray,
    J: np.ndarray,
    vels: np.ndarray,
    omegas: np.ndarray,
) -> None:
    """Apply impulse J (C, 3) to all contact body pairs via scatter-add."""
    # Body a
    np.add.at(vels,   ia, inv_ma[:, None] * J)
    np.add.at(omegas, ia, np.einsum("cij,cj->ci", I_a, _bcross(r_a, J)))
    # Body b — dynamic only
    dyn_b = ~is_sb
    if dyn_b.any():
        J_b = -J[dyn_b]
        np.add.at(vels,   ib[dyn_b], inv_mb[dyn_b, None] * J_b)
        np.add.at(omegas, ib[dyn_b], np.einsum("cij,cj->ci", I_b[dyn_b], _bcross(r_b[dyn_b], J_b)))


# ── Internal helpers ──────────────────────────────────────────────────────────


def _inv_inertia_world(body: Any) -> np.ndarray:
    """3×3 inverse inertia in world frame. Zeros for static / point-mass."""
    if body.static or body.inertia_local is None:
        return np.zeros((3, 3))
    R = _quat_to_rot_unit(body.quat)
    # Use pre-computed inverse (inertia_local is constant — never changes).
    # Fall back to np.linalg.inv for bodies created without the cache.
    I_inv = (
        body.inertia_inv_local
        if getattr(body, "inertia_inv_local", None) is not None
        else np.linalg.inv(body.inertia_local)
    )
    return R @ I_inv @ R.T


def _eff_K(
    r_a: np.ndarray,
    r_b: np.ndarray,
    d: np.ndarray,
    inv_ma: float,
    inv_mb: float,
    I_a: np.ndarray,
    I_b: np.ndarray,
) -> float:
    """Scalar constraint coefficient K = 1/m_eff along direction d."""
    rxa = _cross3(r_a, d)
    rxb = _cross3(r_b, d)
    K = inv_ma + inv_mb + float(rxa @ I_a @ rxa) + float(rxb @ I_b @ rxb)
    return K if K > 1e-14 else 0.0


def _apply_impulse(
    ia: int,
    ib: int,
    J: np.ndarray,
    r_a: np.ndarray,
    r_b: np.ndarray,
    inv_ma: float,
    inv_mb: float,
    I_a: np.ndarray,
    I_b: np.ndarray,
    vels: list[np.ndarray],
    omegas: list[np.ndarray],
) -> None:
    """Apply impulse vector J (in-place). Reaction -J to body_b if dynamic."""
    vels[ia] += inv_ma * J
    omegas[ia] += I_a @ _cross3(r_a, J)
    if ib >= 0 and inv_mb > 0.0:
        vels[ib] -= inv_mb * J
        omegas[ib] -= I_b @ _cross3(r_b, J)


def _contact_v_n(
    c: ContactPoint,
    bodies: list[Any],
    vels: list[np.ndarray],
    omegas: list[np.ndarray],
) -> float:
    """Normal relative velocity at contact point (+ve = separating)."""
    ia = c.body_a_idx
    ib = c.body_b_idx
    b_static = ib < 0 or bodies[ib].static
    r_a = c.pos - bodies[ia].pos
    v_a = vels[ia] + _cross3(omegas[ia], r_a)
    if b_static:
        v_rel = v_a
    else:
        r_b = c.pos - bodies[ib].pos
        v_rel = v_a - (vels[ib] + _cross3(omegas[ib], r_b))
    return float(np.dot(v_rel, c.normal))


def _contact_v_n_fast(
    pos: np.ndarray,
    normal: np.ndarray,
    ia: int,
    ib: int,
    b_static: bool,
    r_a: np.ndarray,
    r_b: np.ndarray,
    vels: list[np.ndarray],
    omegas: list[np.ndarray],
) -> float:
    """Normal relative velocity using pre-computed r_a / r_b (no body lookup)."""
    v_a = vels[ia] + _cross3(omegas[ia], r_a)
    if b_static:
        v_rel = v_a
    else:
        v_rel = v_a - (vels[ib] + _cross3(omegas[ib], r_b))
    return float(np.dot(v_rel, normal))


def _tangent_pair(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Two orthonormal vectors in the contact plane."""
    n = np.asarray(normal, dtype=float)
    if abs(n[0]) < 0.9:
        v = np.array([1.0, 0.0, 0.0])
    else:
        v = np.array([0.0, 1.0, 0.0])
    t1 = _cross3(n, v)
    t1 /= np.linalg.norm(t1) + 1e-300
    t2 = _cross3(n, t1)
    t2 /= np.linalg.norm(t2) + 1e-300
    return t1, t2


# ── Rust PGS 가속 경로 ────────────────────────────────────────────────────────


def _solve_contacts_rust(
    bodies: list[Any],
    contacts: list[ContactPoint],
    dt: float,
) -> list[Any]:
    """Rust pgs_solve 경로 — 선형 속도만 있는 단순 씬 전용.

    각 운동량(omega)은 이 경로에서 무시된다.
    복잡한 씬(angular, spring_k, restitution)은 Python 경로가 처리.
    """
    from dataclasses import replace

    from forge3d.backend import rust_core

    core = rust_core()
    nb = len(bodies)
    nc = len(contacts)

    # (N, 6) 속도 배열 — 선형만 사용
    vel_arr = np.zeros((nb, 6), dtype=np.float64)
    mass_arr = np.zeros(nb, dtype=np.float64)
    for i, b in enumerate(bodies):
        if not b.static:
            vel_arr[i, :3] = b.vel
            mass_arr[i] = b.mass
        else:
            mass_arr[i] = 1e30  # 사실상 무한 질량

    # (C, 10) 접촉 배열
    contact_arr = np.zeros((nc, 10), dtype=np.float64)
    body_idx_arr = np.zeros((nc, 2), dtype=np.int32)
    for ci, c in enumerate(contacts):
        contact_arr[ci, :3] = c.pos
        contact_arr[ci, 3:6] = c.normal
        contact_arr[ci, 6] = max(0.0, c.depth)
        ia, ib = c.body_a_idx, c.body_b_idx
        b_static = ib < 0 or bodies[ib].static
        b_fric = bodies[ib].friction if ib >= 0 else 0.0
        mu = bodies[ia].friction if b_static else 0.5 * (bodies[ia].friction + b_fric)
        contact_arr[ci, 7] = mu
        body_idx_arr[ci, 0] = ia
        body_idx_arr[ci, 1] = ib if ib >= 0 else nb  # 경계 밖 인덱스 → Rust에서 정적으로 처리

    new_vel = np.asarray(core.pgs_solve(contact_arr, body_idx_arr, vel_arr, mass_arr, dt, N_ITER))

    # Baumgarte 위치 보정 (Python에서 처리)
    poss = [b.pos.copy() for b in bodies]
    for c in contacts:
        ia, ib = c.body_a_idx, c.body_b_idx
        b_static = ib < 0 or bodies[ib].static
        excess = max(0.0, c.depth - PENETRATION_SLOP)
        if excess < 1e-6:
            continue
        inv_ma = 0.0 if bodies[ia].static else 1.0 / bodies[ia].mass
        inv_mb = 0.0 if b_static or ib < 0 else 1.0 / bodies[ib].mass
        total_inv = inv_ma + inv_mb
        if total_inv < 1e-12:
            continue
        corr = BAUMGARTE_BETA * excess
        poss[ia] += corr * (inv_ma / total_inv) * c.normal
        if not b_static and ib >= 0:
            poss[ib] -= corr * (inv_mb / total_inv) * c.normal

    result: list[Any] = list(bodies)
    for i, b in enumerate(bodies):
        if not b.static:
            result[i] = replace(b, vel=new_vel[i, :3], omega=b.omega, pos=poss[i])
    return result
