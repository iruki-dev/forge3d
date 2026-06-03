"""Vectorized software ray tracer (NumPy).

All N = H * W * samples rays are processed simultaneously per primitive.
No recursion (MVP: direct illumination + hard shadows only).

Coordinate system: z-up, right-hand.
"""

from __future__ import annotations

import numpy as np

from forge3d.render.hq.scene import HQPrimitive, HQScene

_EPS = np.float32(1e-4)   # self-intersection offset
_INF = np.float32(1e20)   # "no hit" sentinel


# ── Public entry point ────────────────────────────────────────────────────────


def render_frame(
    scene: HQScene,
    width: int,
    height: int,
    samples: int = 4,
    rng_seed: int = 0,
) -> np.ndarray:
    """Render one frame.

    Returns
    -------
    np.ndarray
        Shape (H, W, 3) uint8.
    """
    rng = np.random.default_rng(rng_seed)

    # Camera basis (z-up, right-hand)
    fwd = scene.camera.target - scene.camera.position
    fwd_len = np.linalg.norm(fwd)
    if fwd_len < 1e-10:
        fwd = np.array([1.0, 0.0, 0.0])
    else:
        fwd = fwd / fwd_len

    right = np.cross(fwd, scene.camera.up)
    right_len = np.linalg.norm(right)
    if right_len < 1e-10:
        right = np.array([1.0, 0.0, 0.0])
    else:
        right = right / right_len

    up_cam = np.cross(right, fwd)
    up_cam = up_cam / (np.linalg.norm(up_cam) + 1e-10)

    aspect = width / height
    tan_fov = np.tan(0.5 * np.radians(scene.camera.fov_deg))

    # Pixel grid
    col_idx = np.arange(width, dtype=np.float32)
    row_idx = np.arange(height, dtype=np.float32)
    II, JJ = np.meshgrid(col_idx, row_idx)  # (H, W) each

    # Accumulate samples (float32: sufficient for rendering, 2× less memory)
    accum = np.zeros((height, width, 3), dtype=np.float32)
    cam_origin = np.asarray(scene.camera.position, dtype=np.float32)
    right_f = right.astype(np.float32)
    up_cam_f = up_cam.astype(np.float32)
    fwd_f = fwd.astype(np.float32)
    for _ in range(samples):
        dx = rng.uniform(-0.5, 0.5, (height, width)).astype(np.float32)
        dy = rng.uniform(-0.5, 0.5, (height, width)).astype(np.float32)

        # NDC in [-1, 1], y flipped (image row 0 = top)
        sx = ((2.0 * (II + 0.5 + dx) / width - 1.0) * aspect * tan_fov).astype(np.float32)
        sy = (-(2.0 * (JJ + 0.5 + dy) / height - 1.0) * tan_fov).astype(np.float32)

        # Ray directions (H, W, 3) — float32
        dirs = (
            sx[..., None] * right_f[None, None, :]
            + sy[..., None] * up_cam_f[None, None, :]
            + fwd_f[None, None, :]
        )
        dirs /= np.linalg.norm(dirs, axis=-1, keepdims=True) + np.float32(1e-10)

        # Flatten → (N, 3)
        N = height * width
        origins = np.broadcast_to(cam_origin[None, :], (N, 3)).copy()
        dirs_flat = dirs.reshape(N, 3)

        # Trace + shade
        sample_rgb = _trace_all(origins, dirs_flat, scene)  # (N, 3)
        accum += sample_rgb.reshape(height, width, 3)

    result = accum / np.float32(samples)  # (H, W, 3)

    # Gamma correction (sRGB ≈ 2.2)
    result = np.clip(result, 0.0, 1.0) ** (1.0 / 2.2)
    return (result * 255.0).clip(0, 255).astype(np.uint8)


# ── Core tracing ──────────────────────────────────────────────────────────────


def _trace_all(origins: np.ndarray, dirs: np.ndarray, scene: HQScene) -> np.ndarray:
    """Trace N rays. Returns (N, 3) float64 color in [0, 1]."""
    N = len(origins)

    # Find closest primitive hit for each ray
    t_best = np.full(N, _INF, dtype=np.float32)
    prim_idx = np.full(N, -1, dtype=np.int32)

    for k, prim in enumerate(scene.primitives):
        t = _intersect(origins, dirs, prim)
        closer = t < t_best
        t_best = np.where(closer, t, t_best)
        prim_idx = np.where(closer, k, prim_idx)

    # Background (sky gradient)
    color = _sky_gradient(dirs, scene)

    hit_mask = prim_idx >= 0
    if not hit_mask.any():
        return color

    hit_pts = origins + t_best[:, None] * dirs  # (N, 3)

    # Shade per primitive
    for k, prim in enumerate(scene.primitives):
        mask = hit_mask & (prim_idx == k)
        if not mask.any():
            continue
        normals = _compute_normal(hit_pts[mask], prim)
        color[mask] = _shade(hit_pts[mask], normals, dirs[mask], prim, scene)

    return color


# ── Intersection ──────────────────────────────────────────────────────────────


def _intersect(origins: np.ndarray, dirs: np.ndarray, prim: HQPrimitive) -> np.ndarray:
    """Return hit distances t (N,). inf = no hit."""
    if prim.ptype == "sphere":
        return _intersect_sphere(origins, dirs, prim.center, prim.radius)
    return _intersect_box(origins, dirs, prim.center, prim.half_extents, prim.R)


def _intersect_sphere(
    o: np.ndarray,
    d: np.ndarray,
    center: np.ndarray,
    radius: float,
) -> np.ndarray:
    """Analytic sphere intersection (N rays, vectorized)."""
    oc = o - center  # (N, 3)
    b = np.einsum("ij,ij->i", d, oc)  # (N,)
    c = np.einsum("ij,ij->i", oc, oc) - radius * radius  # (N,)
    disc = b * b - c  # (N,)

    t = np.full(len(o), _INF, dtype=np.float32)
    hit = disc >= 0.0
    if not hit.any():
        return t

    sqrt_disc = np.sqrt(np.maximum(disc[hit], 0.0))
    t1 = -b[hit] - sqrt_disc
    t2 = -b[hit] + sqrt_disc
    t1 = np.where(t1 > _EPS, t1, _INF)
    t2 = np.where(t2 > _EPS, t2, _INF)
    t[hit] = np.minimum(t1, t2)
    return t


def _intersect_box(
    o: np.ndarray,
    d: np.ndarray,
    center: np.ndarray,
    half_extents: np.ndarray,
    R: np.ndarray,
) -> np.ndarray:
    """OBB intersection using slab method (N rays, vectorized).

    R: body-to-world rotation.  Transform rays to local frame via R.T.
    Local-frame multiplication: v_local = v_world @ R  (since R.T @ v = v @ R for rows).
    """
    oc = o - center  # (N, 3)
    o_local = oc @ R  # (N, 3) — world → body frame
    d_local = d @ R  # (N, 3)

    he = half_extents  # (3,)

    # Avoid divide-by-zero: use a signed tiny value so slab ordering is correct
    d_eps = np.where(d_local >= 0, 1e-12, -1e-12)
    d_safe = np.where(np.abs(d_local) > 1e-12, d_local, d_eps)
    inv_d = 1.0 / d_safe  # (N, 3)

    t1 = (-he - o_local) * inv_d  # (N, 3)
    t2 = (he - o_local) * inv_d  # (N, 3)

    t_enter = np.minimum(t1, t2).max(axis=-1)  # (N,)
    t_exit = np.maximum(t1, t2).min(axis=-1)  # (N,)

    hit = (t_exit >= t_enter) & (t_exit > _EPS)
    t_hit = np.where(t_enter > _EPS, t_enter, t_exit)
    t_hit = np.where(t_hit > _EPS, t_hit, _INF)
    return np.where(hit, t_hit, _INF)


# ── Normal computation ────────────────────────────────────────────────────────


def _compute_normal(hit_pts: np.ndarray, prim: HQPrimitive) -> np.ndarray:
    """Surface normal at hit points (M, 3), unit vectors outward."""
    if prim.ptype == "sphere":
        n = hit_pts - prim.center
        return n / (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-10)

    # OBB: identify which face was hit
    local = (hit_pts - prim.center) @ prim.R  # world → body
    local_norm = local / (prim.half_extents + 1e-10)  # (M, 3)
    axis = np.argmax(np.abs(local_norm), axis=-1)  # (M,)
    sign = np.sign(local_norm[np.arange(len(local)), axis])  # (M,)
    n_local = np.zeros_like(local)
    n_local[np.arange(len(local)), axis] = sign
    # body → world: v_world = v_body @ R.T
    return n_local @ prim.R.T  # (M, 3)


# ── Shading ───────────────────────────────────────────────────────────────────


def _shade(
    pts: np.ndarray,
    normals: np.ndarray,
    ray_dirs: np.ndarray,
    prim: HQPrimitive,
    scene: HQScene,
) -> np.ndarray:
    """Blinn-Phong shading + hard shadows. Returns (M, 3) color in [0, 1]."""
    M = len(pts)
    mat_color = prim.color  # (3,)

    # Ambient term (small, prevents pure black)
    ambient_strength = 0.06
    color = np.full((M, 3), ambient_strength) * mat_color

    for light in scene.lights:
        L = light.toward_light  # (3,) unit — toward light source

        # Diffuse (Lambertian)
        ndotl = np.maximum(0.0, normals @ L)  # (M,)

        # Blinn-Phong specular
        view = -ray_dirs  # toward viewer (M, 3)
        halfway = view + L[None, :]
        halfway = halfway / (np.linalg.norm(halfway, axis=-1, keepdims=True) + 1e-10)
        shininess = max(4.0, 64.0 * (1.0 - prim.roughness))
        ndoth = np.maximum(0.0, np.einsum("ij,ij->i", normals, halfway))
        spec = ndoth**shininess  # (M,)

        # Shadow test: offset origin along normal to avoid acne
        shadow_o = pts + _EPS * normals
        L_batch = np.broadcast_to(L[None, :], (M, 3))
        in_shadow = _any_occlusion(shadow_o, L_batch, scene.primitives)

        lit = ~in_shadow  # (M,) bool
        light_rgb = light.color * light.intensity  # (3,)

        color[lit] += (
            ndotl[lit, None] * mat_color[None, :] * light_rgb[None, :]
            + spec[lit, None] * light_rgb[None, :] * 0.25
        )

    return np.clip(color, 0.0, 1.0)


def _any_occlusion(
    origins: np.ndarray,
    dirs: np.ndarray,
    primitives: list[HQPrimitive],
) -> np.ndarray:
    """Return bool (M,): True if any primitive blocks the shadow ray."""
    in_shadow = np.zeros(len(origins), dtype=bool)
    for prim in primitives:
        t = _intersect(origins, dirs, prim)
        in_shadow |= t < _INF
    return in_shadow


# ── Background ────────────────────────────────────────────────────────────────


def _sky_gradient(dirs: np.ndarray, scene: HQScene) -> np.ndarray:
    """Simple vertical sky gradient (N, 3)."""
    t = np.clip(0.5 * (dirs[:, 2] + 1.0), 0.0, 1.0)[:, None]
    return t * scene.background_top + (1.0 - t) * scene.background_bot
