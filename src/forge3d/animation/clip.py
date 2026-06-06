"""AnimationClip — 키프레임 저장 + LERP/SLERP 보간."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# ── 쿼터니언 헬퍼 ─────────────────────────────────────────────────────────────


def _quat_slerp(q0: np.ndarray, q1: np.ndarray, t: float) -> np.ndarray:
    """구면선형 보간 (SLERP). q0, q1은 [w,x,y,z] float64."""
    q0 = q0 / (np.linalg.norm(q0) + 1e-15)
    q1 = q1 / (np.linalg.norm(q1) + 1e-15)
    dot = float(np.clip(np.dot(q0, q1), -1.0, 1.0))
    # 방향이 반대면 q1 플립
    if dot < 0.0:
        q1 = -q1
        dot = -dot
    if dot > 0.9995:
        return q0 + t * (q1 - q0)
    theta0 = np.arccos(dot)
    theta = theta0 * t
    sin_theta = np.sin(theta)
    sin_theta0 = np.sin(theta0)
    s0 = np.cos(theta) - dot * sin_theta / sin_theta0
    s1 = sin_theta / sin_theta0
    return s0 * q0 + s1 * q1


def _quat_to_mat4(q: np.ndarray, pos: np.ndarray, scale: np.ndarray) -> np.ndarray:
    """[w,x,y,z] + 위치 + 스케일 → (4,4) 변환 행렬."""
    w, x, y, z = q / (np.linalg.norm(q) + 1e-15)
    R = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )
    M = np.eye(4, dtype=np.float64)
    M[:3, :3] = R * scale[None, :]
    M[:3, 3] = pos
    return M


# ── AnimationClip ─────────────────────────────────────────────────────────────


@dataclass
class AnimationClip:
    """키프레임 기반 애니메이션 클립.

    keyframes: {bone_name: (T, 10) float64}
      각 행: [time, pos_x, pos_y, pos_z, quat_w, quat_x, quat_y, quat_z, scale_x, scale_y, scale_z]
    """

    name: str
    duration: float
    fps: float
    keyframes: dict[str, np.ndarray] = field(default_factory=dict)

    def sample(self, t: float) -> dict[str, np.ndarray]:
        """시각 t에서 각 본의 (4,4) 로컬 행렬을 반환한다."""
        t = t % self.duration if self.duration > 0 else 0.0
        result: dict[str, np.ndarray] = {}
        for bone_name, kf in self.keyframes.items():
            result[bone_name] = _interp_keyframe(kf, t)
        return result

    @classmethod
    def constant(
        cls,
        name: str,
        duration: float,
        poses: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    ) -> AnimationClip:
        """단일 정적 포즈를 상수 클립으로 생성 (테스트용).

        poses: {bone_name: (pos(3), quat(4), scale(3))}
        """
        keyframes: dict[str, np.ndarray] = {}
        for bone, (pos, quat, scale) in poses.items():
            kf = np.zeros((2, 11), dtype=np.float64)
            kf[0, 0] = 0.0
            kf[1, 0] = duration
            for row in range(2):
                kf[row, 1:4] = np.asarray(pos)
                kf[row, 4:8] = np.asarray(quat)
                kf[row, 8:11] = np.asarray(scale)
            keyframes[bone] = kf
        return cls(name=name, duration=duration, fps=24.0, keyframes=keyframes)


def _interp_keyframe(kf: np.ndarray, t: float) -> np.ndarray:
    """(T, 10) 키프레임 배열에서 시각 t의 (4,4) 행렬을 선형/SLERP 보간."""
    times = kf[:, 0]
    if t <= times[0]:
        row = kf[0]
        return _quat_to_mat4(row[4:8], row[1:4], row[8:11])
    if t >= times[-1]:
        row = kf[-1]
        return _quat_to_mat4(row[4:8], row[1:4], row[8:11])

    # 이진 탐색으로 구간 찾기
    idx = int(np.searchsorted(times, t, side="right")) - 1
    idx = max(0, min(idx, len(times) - 2))
    t0, t1 = times[idx], times[idx + 1]
    alpha = (t - t0) / (t1 - t0 + 1e-15)

    r0, r1 = kf[idx], kf[idx + 1]
    pos = r0[1:4] + alpha * (r1[1:4] - r0[1:4])
    quat = _quat_slerp(r0[4:8], r1[4:8], alpha)
    scale = r0[8:11] + alpha * (r1[8:11] - r0[8:11])
    return _quat_to_mat4(quat, pos, scale)
