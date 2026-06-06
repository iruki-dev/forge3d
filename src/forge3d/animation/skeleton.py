"""Skeleton + Bone — 골격 계층과 순방향 기구학."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Bone:
    """골격 트리의 단일 링크.

    local_matrix: 부모 좌표계에서의 (4,4) 변환 행렬 (바인드 포즈).
    parent_idx: 부모 본 인덱스. 루트는 None.
    """

    name: str
    local_matrix: np.ndarray  # (4, 4) float64
    parent_idx: int | None = None

    def __post_init__(self) -> None:
        self.local_matrix = np.asarray(self.local_matrix, dtype=np.float64)
        if self.local_matrix.shape != (4, 4):
            raise ValueError(f"local_matrix must be (4,4), got {self.local_matrix.shape}")


@dataclass
class Skeleton:
    """본 계층 집합 — 순방향 기구학(FK) 계산."""

    bones: list[Bone]

    def world_matrices(self, local_overrides: dict[str, np.ndarray] | None = None) -> np.ndarray:
        """(N, 4, 4) 월드 행렬 배열을 반환한다.

        Args:
            local_overrides: {bone_name: (4,4) 로컬 행렬} — AnimationClip sample() 결과.
                             None이면 바인드 포즈 사용.
        """
        n = len(self.bones)
        mats = np.empty((n, 4, 4), dtype=np.float64)

        for i, bone in enumerate(self.bones):
            local = (
                local_overrides.get(bone.name, bone.local_matrix)
                if local_overrides
                else bone.local_matrix
            )
            if bone.parent_idx is None:
                mats[i] = local
            else:
                mats[i] = mats[bone.parent_idx] @ local
        return mats

    def joint_positions(self, local_overrides: dict[str, np.ndarray] | None = None) -> np.ndarray:
        """(N, 3) 각 본의 월드 공간 위치."""
        return self.world_matrices(local_overrides)[:, :3, 3]

    @classmethod
    def chain(cls, positions: list[np.ndarray], names: list[str] | None = None) -> Skeleton:
        """단일 체인(링크 1개씩 연결) 골격 생성 헬퍼.

        positions: [(3,)] 각 관절의 월드 위치 리스트
        """
        if names is None:
            names = [f"bone_{i}" for i in range(len(positions))]
        bones: list[Bone] = []
        for i, (pos, name) in enumerate(zip(positions, names, strict=False)):
            M = np.eye(4, dtype=np.float64)
            if i == 0:
                M[:3, 3] = np.asarray(pos)
                parent = None
            else:
                offset = np.asarray(pos) - np.asarray(positions[i - 1])
                M[:3, 3] = offset
                parent = i - 1
            bones.append(Bone(name=name, local_matrix=M, parent_idx=parent))
        return cls(bones=bones)
