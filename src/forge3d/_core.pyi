"""Type stubs for forge3d._core (Rust PyO3 extension)."""

from __future__ import annotations

import numpy as np

class BvhHandle:
    """불투명 BVH 트리 핸들."""
    ...

def se3_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """(4,4) SE3 행렬 곱: a @ b. float64."""
    ...

def se3_inverse(m: np.ndarray) -> np.ndarray:
    """(4,4) SE3 행렬 역변환. float64."""
    ...

def quat_normalize(q: np.ndarray) -> np.ndarray:
    """(4,) 쿼터니언 [w,x,y,z] 정규화. float64."""
    ...

def quat_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """(4,) 쿼터니언 [w,x,y,z] 곱. float64."""
    ...

def quat_rotate_vec(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """쿼터니언 [w,x,y,z]으로 (3,) 벡터 회전. float64."""
    ...

def bvh_build(aabbs: np.ndarray) -> BvhHandle:
    """(N, 6) AABB 배열 [min_x, min_y, min_z, max_x, max_y, max_z]로 BVH 구축."""
    ...

def bvh_query_pairs(handle: BvhHandle) -> np.ndarray:
    """충돌 후보쌍 인덱스 (K, 2) int32 반환."""
    ...

def gjk_query(
    verts_a: np.ndarray,
    verts_b: np.ndarray,
) -> tuple[bool, np.ndarray, float]:
    """GJK+EPA 충돌 감지. 반환: (충돌여부, 법선(3,), 관입깊이)."""
    ...

def pgs_solve(
    contacts: np.ndarray,
    body_indices: np.ndarray,
    velocities: np.ndarray,
    masses: np.ndarray,
    dt: float,
    iterations: int = 10,
) -> np.ndarray:
    """PGS 접촉 솔버. 갱신된 속도 (N, 6) float64 반환."""
    ...
