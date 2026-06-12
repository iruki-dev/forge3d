"""Primitive mesh data for the realtime renderer.

Vertex layout: [px, py, pz,  nx, ny, nz,  u, v]  — 8 floats per vertex (float32).
Returns (vertices, indices) as float32 / uint32 numpy arrays.
"""

from __future__ import annotations

from typing import Any

import numpy as np

# ── Unit primitives ───────────────────────────────────────────────────────────


def _make_face(positions: list[tuple], normal: tuple, uvs: list[tuple]) -> np.ndarray:
    """4-vertex quad face → (4, 8) float32 [pos, normal, uv]."""
    n = np.array(normal, dtype=np.float32)
    rows = []
    for pos, uv in zip(positions, uvs, strict=True):
        rows.append(np.array([*pos, *n, *uv], dtype=np.float32))
    return np.stack(rows)


def unit_box() -> tuple[np.ndarray, np.ndarray]:
    """Unit cube [-.5,.5]^3 with UV mapping.

    Returns
    -------
    verts : (24, 8) float32  — 4 verts per face × 6 faces [pos,normal,uv]
    idx   : (36,)  uint32
    """
    quad_uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

    faces_def = [
        # (+X)
        (
            [(+0.5, -0.5, -0.5), (+0.5, +0.5, -0.5), (+0.5, +0.5, +0.5), (+0.5, -0.5, +0.5)],
            (+1, 0, 0),
        ),
        # (-X)
        (
            [(-0.5, +0.5, -0.5), (-0.5, -0.5, -0.5), (-0.5, -0.5, +0.5), (-0.5, +0.5, +0.5)],
            (-1, 0, 0),
        ),
        # (+Y)
        (
            [(+0.5, +0.5, -0.5), (-0.5, +0.5, -0.5), (-0.5, +0.5, +0.5), (+0.5, +0.5, +0.5)],
            (0, +1, 0),
        ),
        # (-Y)
        (
            [(-0.5, -0.5, -0.5), (+0.5, -0.5, -0.5), (+0.5, -0.5, +0.5), (-0.5, -0.5, +0.5)],
            (0, -1, 0),
        ),
        # (+Z)
        (
            [(-0.5, -0.5, +0.5), (+0.5, -0.5, +0.5), (+0.5, +0.5, +0.5), (-0.5, +0.5, +0.5)],
            (0, 0, +1),
        ),
        # (-Z)
        (
            [(+0.5, -0.5, -0.5), (-0.5, -0.5, -0.5), (-0.5, +0.5, -0.5), (+0.5, +0.5, -0.5)],
            (0, 0, -1),
        ),
    ]

    all_verts = []
    all_idx = []
    base = 0
    for corners, normal in faces_def:
        all_verts.append(_make_face(corners, normal, quad_uvs))
        all_idx.extend([base, base + 1, base + 2, base, base + 2, base + 3])
        base += 4

    verts = np.concatenate(all_verts, axis=0).astype(np.float32)
    idx = np.array(all_idx, dtype=np.uint32)
    return verts, idx


def unit_sphere(slices: int = 24, stacks: int = 18) -> tuple[np.ndarray, np.ndarray]:
    """UV sphere of radius 1 with UV coordinates.

    Returns
    -------
    verts : (N, 8) float32  [pos, normal, uv]
    idx   : (M,)   uint32
    """
    verts = []
    idx = []

    for j in range(stacks + 1):
        phi = np.pi * j / stacks  # 0 → π (north to south)
        # V=0 at south pole (low z), V=1 at north pole (high z) — matches box convention
        # (flipud on texture maps V=0→bottom of image, V=1→top of image)
        v_coord = 1.0 - float(j) / stacks
        sin_phi = np.sin(phi)
        cos_phi = np.cos(phi)
        for i in range(slices + 1):
            theta = 2.0 * np.pi * i / slices
            u_coord = float(i) / slices
            x = sin_phi * np.cos(theta)
            y = sin_phi * np.sin(theta)
            z = cos_phi
            verts.append([x, y, z, x, y, z, u_coord, v_coord])

    for j in range(stacks):
        for i in range(slices):
            a = j * (slices + 1) + i
            b = a + 1
            c = a + (slices + 1)
            d = c + 1
            idx.extend([a, c, b, b, c, d])

    return np.array(verts, dtype=np.float32), np.array(idx, dtype=np.uint32)


def unit_capsule(
    radius: float = 0.5,
    half_length: float = 0.5,
    slices: int = 16,
    stacks: int = 10,
) -> tuple[np.ndarray, np.ndarray]:
    """Capsule mesh: cylinder body + two hemispherical caps, aligned along +Z.

    Returns
    -------
    verts : (N, 8) float32  — interleaved [pos, normal, uv]
    idx   : (M,)   uint32
    """
    verts_list: list[list[float]] = []
    idx_list: list[int] = []

    half_stacks = stacks // 2

    def _add_cap(z_center: float, sign: float, v_base: float, v_range: float) -> None:
        base = len(verts_list)
        for j in range(half_stacks + 1):
            t = j / half_stacks  # 0..1
            phi = (np.pi / 2.0) * t * sign
            for i in range(slices + 1):
                theta = 2.0 * np.pi * i / slices
                x = radius * np.cos(phi) * np.cos(theta)
                y = radius * np.cos(phi) * np.sin(theta)
                z = radius * np.sin(phi)
                nx, ny, nz = x / radius, y / radius, z / radius
                u = float(i) / slices
                # Invert V so V=0 at bottom (south), V=1 at top (north) — matches box
                v = 1.0 - (v_base + t * v_range * sign)
                verts_list.append([x, y, z_center + z, nx, ny, nz, u, v])
        rows = half_stacks + 1
        for j in range(rows - 1):
            for i in range(slices):
                a = base + j * (slices + 1) + i
                b = a + 1
                c = a + (slices + 1)
                d = c + 1
                if sign > 0:
                    idx_list.extend([a, c, b, b, c, d])
                else:
                    idx_list.extend([a, b, c, b, d, c])

    total_len = 2.0 * (radius + half_length)
    v_cap = radius / total_len  # fraction of V for one cap

    # Top cap
    _add_cap(+half_length, +1.0, v_cap, v_cap)
    # Bottom cap
    _add_cap(-half_length, -1.0, 1.0 - v_cap, v_cap)

    # Cylinder body — V=1-v_cap at top (j=0), V=v_cap at bottom (j=1), matching caps
    base = len(verts_list)
    for j in range(2):
        z = half_length * (1.0 - 2.0 * j)
        v_coord = 1.0 - v_cap if j == 0 else v_cap
        for i in range(slices + 1):
            theta = 2.0 * np.pi * i / slices
            x = radius * np.cos(theta)
            y = radius * np.sin(theta)
            nx, ny = x / radius, y / radius
            u = float(i) / slices
            verts_list.append([x, y, z, nx, ny, 0.0, u, v_coord])
    for i in range(slices):
        a = base + i
        b = a + 1
        c = base + slices + 1 + i
        d = c + 1
        idx_list.extend([a, c, b, b, c, d])

    return np.array(verts_list, dtype=np.float32), np.array(idx_list, dtype=np.uint32)


def unit_cylinder(
    radius: float = 0.5,
    half_length: float = 0.5,
    slices: int = 24,
) -> tuple[np.ndarray, np.ndarray]:
    """Cylinder mesh aligned along +Z with flat end caps.

    Returns
    -------
    verts : (N, 8) float32  — interleaved [pos, normal, uv]
    idx   : (M,)   uint32
    """
    verts: list[list[float]] = []
    idx: list[int] = []

    # Top cap (normal +Z)
    top_c = len(verts)
    verts.append([0.0, 0.0, half_length, 0.0, 0.0, 1.0, 0.5, 0.5])
    top_rim = len(verts)
    for i in range(slices):
        theta = 2.0 * np.pi * i / slices
        c, s = float(np.cos(theta)), float(np.sin(theta))
        verts.append(
            [radius * c, radius * s, half_length, 0.0, 0.0, 1.0, 0.5 + 0.5 * c, 0.5 + 0.5 * s]
        )
    for i in range(slices):
        idx.extend([top_c, top_rim + i, top_rim + (i + 1) % slices])

    # Bottom cap (normal -Z)
    bot_c = len(verts)
    verts.append([0.0, 0.0, -half_length, 0.0, 0.0, -1.0, 0.5, 0.5])
    bot_rim = len(verts)
    for i in range(slices):
        theta = 2.0 * np.pi * i / slices
        c, s = float(np.cos(theta)), float(np.sin(theta))
        verts.append(
            [radius * c, radius * s, -half_length, 0.0, 0.0, -1.0, 0.5 + 0.5 * c, 0.5 + 0.5 * s]
        )
    for i in range(slices):
        idx.extend([bot_c, bot_rim + (i + 1) % slices, bot_rim + i])

    # Side wall — duplicate rim verts with outward normals
    side_start = len(verts)
    for i in range(slices + 1):
        theta = 2.0 * np.pi * i / slices
        nx, ny = float(np.cos(theta)), float(np.sin(theta))
        x, y = radius * nx, radius * ny
        u = float(i) / slices
        verts.append([x, y, half_length, nx, ny, 0.0, u, 1.0])
        verts.append([x, y, -half_length, nx, ny, 0.0, u, 0.0])
    for i in range(slices):
        a = side_start + i * 2
        b, c_, d = a + 1, a + 2, a + 3
        idx.extend([a, b, c_, b, d, c_])

    return np.array(verts, dtype=np.float32), np.array(idx, dtype=np.uint32)


def unit_cone(
    radius: float = 0.5,
    height: float = 1.0,
    slices: int = 24,
) -> tuple[np.ndarray, np.ndarray]:
    """Cone mesh: circular base at z=−height/2, apex at z=+height/2.

    Returns
    -------
    verts : (N, 8) float32  — interleaved [pos, normal, uv]
    idx   : (M,)   uint32
    """
    verts: list[list[float]] = []
    idx: list[int] = []
    half_h = height / 2.0
    slant = float(np.sqrt(radius * radius + height * height))
    nz = radius / slant  # outward normal z component on lateral face
    nr = height / slant  # outward normal horizontal magnitude

    # Base cap (normal −Z)
    base_c = len(verts)
    verts.append([0.0, 0.0, -half_h, 0.0, 0.0, -1.0, 0.5, 0.5])
    base_rim = len(verts)
    for i in range(slices):
        theta = 2.0 * np.pi * i / slices
        c, s = float(np.cos(theta)), float(np.sin(theta))
        verts.append(
            [radius * c, radius * s, -half_h, 0.0, 0.0, -1.0, 0.5 + 0.5 * c, 0.5 + 0.5 * s]
        )
    for i in range(slices):
        idx.extend([base_c, base_rim + (i + 1) % slices, base_rim + i])

    # Lateral faces — one triangle per slice (apex + two rim vertices)
    for i in range(slices):
        theta0 = 2.0 * np.pi * i / slices
        theta1 = 2.0 * np.pi * (i + 1) / slices
        theta_mid = (theta0 + theta1) / 2.0
        base = len(verts)
        # Apex (normal averaged at mid-angle)
        verts.append(
            [
                0.0,
                0.0,
                half_h,
                nr * float(np.cos(theta_mid)),
                nr * float(np.sin(theta_mid)),
                nz,
                0.5,
                1.0,
            ]
        )
        c0, s0 = float(np.cos(theta0)), float(np.sin(theta0))
        verts.append(
            [radius * c0, radius * s0, -half_h, nr * c0, nr * s0, nz, float(i) / slices, 0.0]
        )
        c1, s1 = float(np.cos(theta1)), float(np.sin(theta1))
        verts.append(
            [radius * c1, radius * s1, -half_h, nr * c1, nr * s1, nz, float(i + 1) / slices, 0.0]
        )
        idx.extend([base, base + 1, base + 2])

    return np.array(verts, dtype=np.float32), np.array(idx, dtype=np.uint32)


def unit_wedge(
    sx: float = 1.0,
    sy: float = 1.0,
    sz: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Right-angle triangular-prism ramp/wedge.

    The ramp slopes from the front-bottom edge (y=−sy/2, z=−sz/2) up to the
    back-top edge (y=+sy/2, z=+sz/2).  Use ``quat`` on the body to orient it.

    Returns
    -------
    verts : (N, 8) float32  — interleaved [pos, normal, uv]
    idx   : (M,)   uint32
    """
    hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0

    # 6 raw vertex positions
    p: list[tuple[float, float, float]] = [
        (-hx, -hy, -hz),  # 0 front-bottom-left
        (hx, -hy, -hz),  # 1 front-bottom-right
        (hx, hy, -hz),  # 2 back-bottom-right
        (-hx, hy, -hz),  # 3 back-bottom-left
        (-hx, hy, hz),  # 4 back-top-left
        (hx, hy, hz),  # 5 back-top-right
    ]

    # Slant face (front-bottom → back-top) outward normal
    slant = float(np.sqrt(hy * hy + hz * hz))
    sny, snz = -hz / slant, hy / slant

    verts: list[list[float]] = []
    idx: list[int] = []

    def _quad(
        corners: list[int], n: tuple[float, float, float], uvs: list[tuple[float, float]]
    ) -> None:
        base = len(verts)
        nx, ny, nz_ = n
        for ci, uv in zip(corners, uvs, strict=True):
            pos = p[ci]
            verts.append([pos[0], pos[1], pos[2], nx, ny, nz_, uv[0], uv[1]])
        idx.extend([base, base + 1, base + 2, base, base + 2, base + 3])

    def _tri(
        corners: list[int], n: tuple[float, float, float], uvs: list[tuple[float, float]]
    ) -> None:
        base = len(verts)
        nx, ny, nz_ = n
        for ci, uv in zip(corners, uvs, strict=True):
            pos = p[ci]
            verts.append([pos[0], pos[1], pos[2], nx, ny, nz_, uv[0], uv[1]])
        idx.extend([base, base + 1, base + 2])

    # Bottom face (z = −hz, normal −Z): CCW from below → [0,3,2,1]
    _quad([0, 3, 2, 1], (0.0, 0.0, -1.0), [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)])
    # Back vertical face (y = +hy, normal +Y): [3,4,5,2]
    _quad([3, 4, 5, 2], (0.0, 1.0, 0.0), [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)])
    # Left end triangle (x = −hx, normal −X): [0,4,3]
    _tri([0, 4, 3], (-1.0, 0.0, 0.0), [(1.0, 0.0), (0.0, 1.0), (0.0, 0.0)])
    # Right end triangle (x = +hx, normal +X): [1,2,5]
    _tri([1, 2, 5], (1.0, 0.0, 0.0), [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)])
    # Slant face (ramp, outward normal has −Y and +Z): [0,1,5,4]
    _quad([0, 1, 5, 4], (0.0, sny, snz), [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])

    return np.array(verts, dtype=np.float32), np.array(idx, dtype=np.uint32)


def mesh_from_data(mesh_data: Any) -> tuple[np.ndarray, np.ndarray]:
    """Convert MeshData to renderer vertex/index arrays (8-float layout).

    Returns
    -------
    verts : (N, 8) float32  — interleaved [pos, normal, uv]
    idx   : (M,)   uint32
    """
    return mesh_data.interleaved(), np.asarray(mesh_data.indices, dtype=np.uint32)


# ── Heightfield terrain mesh ──────────────────────────────────────────────────


def heightfield_mesh(
    heights: np.ndarray,
    cell_size: float,
    origin: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert a heightfield to a triangle mesh with smooth normals.

    Parameters
    ----------
    heights  : (rows, cols) float32 height values.
    cell_size: World-space size of each grid cell (m).
    origin   : (3,) world-space position of the (0, 0) grid corner.

    Returns
    -------
    verts : (rows*cols, 8) float32  — [px, py, pz, nx, ny, nz, u, v]
    idx   : (2*(rows-1)*(cols-1)*3,) uint32  — triangle indices
    """
    rows, cols = heights.shape
    verts = np.zeros((rows * cols, 8), dtype=np.float32)

    ox, oy, oz = float(origin[0]), float(origin[1]), float(origin[2])

    for r in range(rows):
        for c in range(cols):
            x = ox + c * cell_size
            y = oy + r * cell_size
            z = oz + float(heights[r, c])
            # UV: 0..1 over the whole terrain
            u = c / (cols - 1) if cols > 1 else 0.0
            v = r / (rows - 1) if rows > 1 else 0.0
            verts[r * cols + c, :3] = [x, y, z]
            verts[r * cols + c, 6:8] = [u, v]

    # Compute normals by finite difference
    # Central difference for interior, forward/backward at edges
    for r in range(rows):
        for c in range(cols):
            # dz/dx (along col axis)
            if c == 0:
                dzdc = float(heights[r, 1] - heights[r, 0]) / cell_size
            elif c == cols - 1:
                dzdc = float(heights[r, cols - 1] - heights[r, cols - 2]) / cell_size
            else:
                dzdc = float(heights[r, c + 1] - heights[r, c - 1]) / (2 * cell_size)
            # dz/dy (along row axis)
            if r == 0:
                dzdr = float(heights[1, c] - heights[0, c]) / cell_size
            elif r == rows - 1:
                dzdr = float(heights[rows - 1, c] - heights[rows - 2, c]) / cell_size
            else:
                dzdr = float(heights[r + 1, c] - heights[r - 1, c]) / (2 * cell_size)
            # Normal = (-dz/dx, -dz/dy, 1) normalised
            nx, ny, nz = -dzdc, -dzdr, 1.0
            n = (nx * nx + ny * ny + nz * nz) ** 0.5
            verts[r * cols + c, 3:6] = [nx / n, ny / n, nz / n]

    # Build triangle indices (two triangles per quad)
    idx_list = []
    for r in range(rows - 1):
        for c in range(cols - 1):
            a = r * cols + c
            b = a + 1
            c_ = a + cols
            d = c_ + 1
            # Lower-left triangle
            idx_list.extend([a, b, c_])
            # Upper-right triangle
            idx_list.extend([b, d, c_])

    return verts, np.array(idx_list, dtype=np.uint32)


# ── Grid / axes helpers ───────────────────────────────────────────────────────


def grid_lines(
    half_size: float = 10.0,
    step: float = 1.0,
) -> np.ndarray:
    """Axis-aligned grid on the z=0 plane.

    Returns
    -------
    verts : (N, 3) float32  — line endpoints (GL_LINES)
    """
    lines = []
    n = int(half_size / step)
    for i in range(-n, n + 1):
        coord = i * step
        lines.append([-half_size, coord, 0.0])
        lines.append([+half_size, coord, 0.0])
        lines.append([coord, -half_size, 0.0])
        lines.append([coord, +half_size, 0.0])
    return np.array(lines, dtype=np.float32)


def axes_lines(length: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """World-axis arrows starting at origin.

    Returns
    -------
    verts  : (6, 3) float32  — pairs: origin, tip
    colors : (6, 4) float32  — per-vertex RGBA
    """
    verts = np.array(
        [
            [0, 0, 0],
            [length, 0, 0],  # X
            [0, 0, 0],
            [0, length, 0],  # Y
            [0, 0, 0],
            [0, 0, length],  # Z
        ],
        dtype=np.float32,
    )
    red = [0.9, 0.15, 0.10, 1.0]
    green = [0.10, 0.75, 0.20, 1.0]
    blue = [0.15, 0.35, 0.95, 1.0]
    colors = np.array(
        [red, red, green, green, blue, blue],
        dtype=np.float32,
    )
    return verts, colors
