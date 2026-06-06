"""FABRIK IK 솔버 — Forward And Backward Reaching Inverse Kinematics.

참고: Aristidou & Lasenby (2011), "FABRIK: A fast, iterative solver for the Inverse Kinematics problem"
"""

from __future__ import annotations

import numpy as np


class FABRIKSolver:
    """N링크 체인 FABRIK IK.

    체인은 [(3,)] 링크 위치 리스트로 표현된다.
    링크 길이는 초기 체인에서 자동으로 계산된다.
    """

    def solve(
        self,
        chain: list[np.ndarray],
        target: np.ndarray,
        max_iterations: int = 20,
        tolerance: float = 1e-4,
    ) -> list[np.ndarray]:
        """수렴된 링크 위치 리스트를 반환한다.

        Args:
            chain:  [(3,)] 관절 위치. chain[0]이 루트(고정), chain[-1]이 끝단.
            target: (3,) 목표 위치.
            max_iterations: 최대 반복 횟수.
            tolerance: 끝단과 목표 간 허용 오차 (m).

        Returns:
            수렴된 관절 위치 리스트 (chain과 같은 길이).
        """
        n = len(chain)
        if n < 2:
            return [np.asarray(p, dtype=np.float64) for p in chain]

        positions = [np.asarray(p, dtype=np.float64) for p in chain]
        root = positions[0].copy()

        # 링크 길이 계산
        lengths = [float(np.linalg.norm(positions[i + 1] - positions[i])) for i in range(n - 1)]
        total_length = sum(lengths)

        # 목표가 도달 불가능한 거리인지 확인
        dist_to_target = float(np.linalg.norm(np.asarray(target) - root))
        if dist_to_target >= total_length:
            # 체인을 목표 방향으로 완전히 뻗음
            direction = (np.asarray(target) - root) / (dist_to_target + 1e-15)
            for i in range(1, n):
                positions[i] = positions[i - 1] + direction * lengths[i - 1]
            return positions

        target = np.asarray(target, dtype=np.float64)

        for _ in range(max_iterations):
            # ── Forward reaching (끝단 → 루트) ──
            positions[-1] = target.copy()
            for i in range(n - 2, -1, -1):
                direction = positions[i] - positions[i + 1]
                dist = float(np.linalg.norm(direction))
                if dist > 1e-12:
                    direction /= dist
                positions[i] = positions[i + 1] + direction * lengths[i]

            # ── Backward reaching (루트 → 끝단) ──
            positions[0] = root.copy()
            for i in range(1, n):
                direction = positions[i] - positions[i - 1]
                dist = float(np.linalg.norm(direction))
                if dist > 1e-12:
                    direction /= dist
                positions[i] = positions[i - 1] + direction * lengths[i - 1]

            # 수렴 확인
            if float(np.linalg.norm(positions[-1] - target)) < tolerance:
                break

        return positions


def chain_from_ur5_joints(joint_angles: np.ndarray) -> list[np.ndarray]:
    """UR5 관절각 → FK → 관절 위치 체인 (단순 평면 근사).

    실제 DH 파라미터 기반 FK (P7 robot.py와 연동 가능).
    여기서는 단위 링크 체인을 근사로 사용한다.
    """
    # UR5 링크 길이 (m) — d1, a2, a3, d4, d5, d6 근사
    link_lengths = [0.089159, 0.425, 0.39225, 0.109, 0.095, 0.082]
    n = min(len(joint_angles) + 1, len(link_lengths) + 1)

    positions: list[np.ndarray] = [np.zeros(3)]
    cumulative = np.zeros(3)
    cumulative[2] = link_lengths[0]  # 첫 링크는 z축

    for i in range(1, n):
        angle = joint_angles[i - 1] if i - 1 < len(joint_angles) else 0.0
        length = link_lengths[i] if i < len(link_lengths) else 0.1
        # 단순 2D 평면 근사 (y-z 평면)
        direction = np.array([0.0, np.sin(angle), np.cos(angle)]) * length
        cumulative = cumulative + direction
        positions.append(cumulative.copy())

    return positions
