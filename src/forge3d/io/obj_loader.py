"""OBJ file loader — pure Python, no external mesh library.

Parses Wavefront OBJ format and returns a MeshData.

Supported features:
  - v  (vertex positions)
  - vn (vertex normals)
  - vt (texture UV coordinates)
  - f  (triangles and quads; supports v, v/vt, v//vn, v/vt/vn)
  - mtllib / usemtl (material assignment groups)
  - o / g (object / group name — ignored for physics, tracked for groups)

Missing / unsupported: curves, NURBS, smoothing groups (s).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from forge3d.io.mesh_data import MeshData, _compute_convex_hull


def load_obj(path: str | Path) -> MeshData:
    """Load a Wavefront OBJ file and return a MeshData.

    Parameters
    ----------
    path : str or Path — path to the .obj file.

    Returns
    -------
    MeshData with positions, normals, UVs, indices, hull, and material groups.
    Normals are recomputed per-face if missing from the file.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"OBJ file not found: {path}")

    raw_pos: list[list[float]] = []
    raw_uv: list[list[float]] = []
    raw_nrm: list[list[float]] = []
    face_groups: list[tuple[str, list[tuple[int, int, int]]]] = []  # [(material, [faces])]
    current_mat = "default"
    current_faces: list[tuple[int, int, int]] = []

    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            tok = parts[0]

            if tok == "v":
                raw_pos.append([float(x) for x in parts[1:4]])
            elif tok == "vt":
                raw_uv.append([float(x) for x in parts[1:3]])
            elif tok == "vn":
                raw_nrm.append([float(x) for x in parts[1:4]])
            elif tok in ("usemtl", "g", "o"):
                if tok == "usemtl" and parts[1:]:
                    new_mat = parts[1]
                    if current_faces:
                        face_groups.append((current_mat, current_faces))
                        current_faces = []
                    current_mat = new_mat
            elif tok == "f":
                tris = _parse_face(parts[1:])
                current_faces.extend(tris)

    if current_faces:
        face_groups.append((current_mat, current_faces))

    if not raw_pos:
        raise ValueError(f"OBJ file has no vertices: {path}")

    return _build_mesh(raw_pos, raw_uv, raw_nrm, face_groups)


def _parse_face(
    tokens: list[str],
) -> list[tuple[int, int, int]]:
    """Parse face tokens into (v_idx, vt_idx, vn_idx) 0-based tuples.

    Triangulates quads and n-gons by fan triangulation.
    """
    verts: list[tuple[int, int, int]] = []
    for tok in tokens:
        parts = tok.split("/")
        v_idx = int(parts[0]) - 1
        vt_idx = (int(parts[1]) - 1) if len(parts) > 1 and parts[1] else -1
        vn_idx = (int(parts[2]) - 1) if len(parts) > 2 and parts[2] else -1
        verts.append((v_idx, vt_idx, vn_idx))

    # Fan triangulation: (0,1,2), (0,2,3), ...
    tris: list[tuple[int, int, int]] = []
    for i in range(1, len(verts) - 1):
        # Each "tri" is 3 vertex tuples
        tris.append((verts[0], verts[i], verts[i + 1]))  # type: ignore[arg-type]
    return tris  # type: ignore[return-value]


def _build_mesh(
    raw_pos: list[list[float]],
    raw_uv: list[list[float]],
    raw_nrm: list[list[float]],
    face_groups: list[tuple[str, list[Any]]],
) -> MeshData:
    """Flatten OBJ face data into GPU-ready vertex arrays."""
    has_uv = len(raw_uv) > 0
    has_nrm = len(raw_nrm) > 0

    pos_arr = np.array(raw_pos, dtype=np.float32)
    uv_arr = np.array(raw_uv, dtype=np.float32) if has_uv else None
    nrm_arr = np.array(raw_nrm, dtype=np.float32) if has_nrm else None

    # Deduplicate by (v_idx, vt_idx, vn_idx) → linear vertex index
    vertex_map: dict[tuple[int, int, int], int] = {}
    out_pos: list[np.ndarray] = []
    out_uv: list[np.ndarray] = []
    out_nrm: list[np.ndarray] = []
    out_idx: list[int] = []
    mat_groups: list[tuple[str, int, int]] = []

    tri_cursor = 0
    for mat_name, face_tris in face_groups:
        group_start = tri_cursor
        for tri in face_tris:
            # tri is ((v,vt,vn), (v,vt,vn), (v,vt,vn)) — three vertex tuples
            for v_idx, vt_idx, vn_idx in tri:
                key = (v_idx, vt_idx, vn_idx)
                if key not in vertex_map:
                    new_idx = len(out_pos)
                    vertex_map[key] = new_idx
                    out_pos.append(pos_arr[v_idx])
                    out_uv.append(
                        uv_arr[vt_idx]  # type: ignore[index]
                        if (has_uv and vt_idx >= 0)
                        else np.zeros(2, dtype=np.float32)
                    )
                    out_nrm.append(
                        nrm_arr[vn_idx]  # type: ignore[index]
                        if (has_nrm and vn_idx >= 0)
                        else np.zeros(3, dtype=np.float32)
                    )
                out_idx.append(vertex_map[key])
            tri_cursor += 1
        group_n = tri_cursor - group_start
        if group_n > 0:
            mat_groups.append((mat_name, group_start * 3, group_n * 3))

    positions = np.array(out_pos, dtype=np.float32)
    uvs = np.array(out_uv, dtype=np.float32)
    normals = np.array(out_nrm, dtype=np.float32)
    indices = np.array(out_idx, dtype=np.uint32)

    # Compute or fix normals
    if not has_nrm or np.allclose(normals, 0.0):
        normals = _compute_vertex_normals(positions, indices)
    else:
        # Normalise and fill any zero normals with face normals
        lens = np.linalg.norm(normals, axis=1, keepdims=True)
        zero_mask = (lens < 1e-8).ravel()
        if zero_mask.any():
            face_normals = _compute_vertex_normals(positions, indices)
            normals[zero_mask] = face_normals[zero_mask]
        normals = normals / (np.linalg.norm(normals, axis=1, keepdims=True) + 1e-12)

    hull_verts, hull_faces = _compute_convex_hull(positions.astype(np.float64))

    return MeshData(
        vertices=positions,
        normals=normals,
        uvs=uvs,
        indices=indices,
        hull_vertices=hull_verts,
        hull_faces=hull_faces,
        material_groups=mat_groups,
    )


def _compute_vertex_normals(positions: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """Compute smooth vertex normals by averaging adjacent face normals."""
    n_verts = len(positions)
    normals = np.zeros((n_verts, 3), dtype=np.float32)
    tris = indices.reshape(-1, 3)

    v0 = positions[tris[:, 0]]
    v1 = positions[tris[:, 1]]
    v2 = positions[tris[:, 2]]
    face_normals = np.cross(v1 - v0, v2 - v0)  # (F, 3)

    for i, tri in enumerate(tris):
        normals[tri[0]] += face_normals[i]
        normals[tri[1]] += face_normals[i]
        normals[tri[2]] += face_normals[i]

    lens = np.linalg.norm(normals, axis=1, keepdims=True)
    lens = np.where(lens < 1e-10, 1.0, lens)
    return (normals / lens).astype(np.float32)
