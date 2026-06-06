"""AnimationPlayer + BlendTree — ECS 컴포넌트."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from forge3d.ecs.component import Component

if TYPE_CHECKING:
    from forge3d.animation.clip import AnimationClip
    from forge3d.animation.skeleton import Skeleton


@dataclass
class BlendTree:
    """1D 파라미터 기반 두 클립 가중 블렌딩.

    parameter in [0.0, 1.0]: 0→clip_a, 1→clip_b
    """

    clip_a: AnimationClip
    clip_b: AnimationClip
    parameter: float = 0.0  # 블렌딩 가중치

    def sample(self, t: float) -> dict[str, np.ndarray]:
        """시각 t에서 두 클립 간 가중 보간 결과를 반환한다."""
        sa = self.clip_a.sample(t)
        sb = self.clip_b.sample(t)
        result: dict[str, np.ndarray] = {}
        alpha = float(np.clip(self.parameter, 0.0, 1.0))
        all_bones = set(sa.keys()) | set(sb.keys())
        for bone in all_bones:
            ma = sa.get(bone, np.eye(4))
            mb = sb.get(bone, np.eye(4))
            # 행렬의 선형 보간 (단순 lerp — 엄밀하지 않지만 실용적)
            result[bone] = (1.0 - alpha) * ma + alpha * mb
        return result


@dataclass
class AnimationPlayer(Component):
    """골격 애니메이션 재생기 ECS 컴포넌트."""

    skeleton: Skeleton
    clip: AnimationClip | None = None
    blend_tree: BlendTree | None = None
    speed: float = 1.0
    loop: bool = True
    _time: float = field(default=0.0, repr=False)

    def advance(self, dt: float) -> dict[str, np.ndarray]:
        """시간을 dt 만큼 전진시키고 현재 포즈(본 로컬 행렬 딕셔너리)를 반환한다."""
        self._time += dt * self.speed

        if self.blend_tree is not None:
            t = self._time % self.blend_tree.clip_a.duration
            return self.blend_tree.sample(t)

        if self.clip is not None:
            if self.loop:
                t = self._time % self.clip.duration if self.clip.duration > 0 else 0.0
            else:
                t = min(self._time, self.clip.duration)
            return self.clip.sample(t)

        return {}

    @property
    def current_time(self) -> float:
        return self._time

    @property
    def world_matrices(self) -> np.ndarray:
        """현재 _time 기준 (N, 4, 4) 월드 행렬. advance()를 호출해야 갱신된다."""
        pose = self.advance(0.0)
        return self.skeleton.world_matrices(pose)


@dataclass
class IKTarget(Component):
    """FABRIK IK의 목표 위치를 나타내는 ECS 컴포넌트."""

    chain_root: str  # IK 체인 루트 본 이름
    chain_tip: str  # IK 체인 끝 본 이름
    target_position: np.ndarray = field(default_factory=lambda: np.zeros(3))
    max_iterations: int = 20
    tolerance: float = 1e-4
