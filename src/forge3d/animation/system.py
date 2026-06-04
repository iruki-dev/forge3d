"""AnimationSystem — ECS 시스템, 본 행렬 일괄 업데이트."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from forge3d.animation.ik_fabrik import FABRIKSolver
from forge3d.animation.player import AnimationPlayer, IKTarget
from forge3d.ecs.system import System
from forge3d.ecs.transform import Transform

if TYPE_CHECKING:
    from forge3d.ecs.entity import EntityWorld

_fabrik = FABRIKSolver()


class AnimationSystem(System):
    """AnimationPlayer 컴포넌트를 매 프레임 전진시키고 Transform을 동기화한다."""

    def update(self, ew: "EntityWorld", dt: float) -> None:
        # ── 클립/블렌드 트리 재생 ──────────────────────────────────────────
        for _e, player in ew.query(AnimationPlayer):
            anim: AnimationPlayer = player  # type: ignore[assignment]
            anim.advance(dt)

        # ── FABRIK IK ─────────────────────────────────────────────────────
        for e, tf, ik in ew.query(Transform, IKTarget):
            transform: Transform = tf  # type: ignore[assignment]
            ik_target: IKTarget = ik  # type: ignore[assignment]

            # AnimationPlayer가 있으면 체인 위치 읽기
            try:
                player = ew.get_component(e, AnimationPlayer)  # type: ignore[assignment]
            except KeyError:
                continue

            anim_player: AnimationPlayer = player
            joint_positions = anim_player.skeleton.joint_positions()
            if len(joint_positions) < 2:
                continue

            chain = [joint_positions[i] for i in range(len(joint_positions))]
            solved = _fabrik.solve(
                chain,
                ik_target.target_position,
                max_iterations=ik_target.max_iterations,
                tolerance=ik_target.tolerance,
            )
            # Transform 위치를 IK 끝단으로 업데이트
            transform.position = np.asarray(solved[-1], dtype=np.float64)
