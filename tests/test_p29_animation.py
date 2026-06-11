"""P29 — 애니메이션 시스템 검증 테스트.

게이트:
  G1: 골격 FK 월드 행렬 정확성
  G2: FABRIK 수렴: 3링크 체인 오차 < 1e-4m
  G3: BlendTree 중간 파라미터 보간 행렬
  G4: 전체 기존 테스트 회귀 없음
"""
from __future__ import annotations

import numpy as np

import forge3d as f3d


# ── G1: 골격 FK ───────────────────────────────────────────────────────────────

def test_skeleton_single_bone():
    """루트 본 하나의 월드 행렬 == 로컬 행렬."""
    M = np.eye(4)
    M[:3, 3] = [1.0, 2.0, 3.0]
    skel = f3d.Skeleton([f3d.Bone("root", M, parent_idx=None)])
    mats = skel.world_matrices()
    assert mats.shape == (1, 4, 4)
    assert np.allclose(mats[0], M)


def test_skeleton_chain_fk():
    """G1: 2본 체인 FK — 자식 월드 위치 = 부모 위치 + 오프셋."""
    root_M = np.eye(4)
    root_M[:3, 3] = [1.0, 0.0, 0.0]

    child_M = np.eye(4)
    child_M[:3, 3] = [0.0, 2.0, 0.0]  # 부모 좌표계에서 y=2 오프셋

    skel = f3d.Skeleton([
        f3d.Bone("root", root_M, parent_idx=None),
        f3d.Bone("child", child_M, parent_idx=0),
    ])
    mats = skel.world_matrices()
    # 자식 월드 위치: [1+0, 0+2, 0] = [1, 2, 0]
    assert np.allclose(mats[1, :3, 3], [1.0, 2.0, 0.0])


def test_skeleton_three_level_hierarchy():
    """3단계 체인의 FK."""
    bones = []
    for i in range(3):
        M = np.eye(4)
        M[:3, 3] = [1.0, 0.0, 0.0]  # 각 본이 x 방향으로 1m
        bones.append(f3d.Bone(f"b{i}", M, parent_idx=i - 1 if i > 0 else None))
    skel = f3d.Skeleton(bones)
    mats = skel.world_matrices()
    # 세 번째 본 월드 x = 3
    assert np.allclose(mats[2, :3, 3], [3.0, 0.0, 0.0])


def test_skeleton_chain_helper():
    """Skeleton.chain() 헬퍼로 생성된 체인 FK 정확성."""
    positions = [np.array([0., 0., 0.]), np.array([1., 0., 0.]), np.array([2., 0., 0.])]
    skel = f3d.Skeleton.chain(positions)
    world_pos = skel.joint_positions()
    assert np.allclose(world_pos[0], [0., 0., 0.])
    assert np.allclose(world_pos[2], [2., 0., 0.])


def test_skeleton_with_override():
    """local_overrides로 FK 오버라이드."""
    root_M = np.eye(4); root_M[:3, 3] = [0., 0., 0.]
    child_M = np.eye(4); child_M[:3, 3] = [1., 0., 0.]
    skel = f3d.Skeleton([
        f3d.Bone("root", root_M, parent_idx=None),
        f3d.Bone("child", child_M, parent_idx=0),
    ])
    # 오버라이드: child가 y방향 1m
    override_M = np.eye(4); override_M[:3, 3] = [0., 1., 0.]
    mats = skel.world_matrices({"child": override_M})
    assert np.allclose(mats[1, :3, 3], [0., 1., 0.])


# ── AnimationClip ─────────────────────────────────────────────────────────────

def test_clip_constant_sample():
    """상수 클립 sample()이 항상 같은 행렬을 반환한다."""
    pos = np.array([1., 2., 3.])
    quat = np.array([1., 0., 0., 0.])
    scale = np.ones(3)
    clip = f3d.AnimationClip.constant("test", duration=1.0, poses={"bone0": (pos, quat, scale)})
    m0 = clip.sample(0.0)["bone0"]
    m_half = clip.sample(0.5)["bone0"]
    assert np.allclose(m0[:3, 3], pos)
    assert np.allclose(m_half[:3, 3], pos)


def test_clip_lerp_position():
    """키프레임 간 위치 선형 보간."""
    kf = np.zeros((2, 11))
    kf[0] = [0.0, 0., 0., 0., 1., 0., 0., 0., 1., 1., 1.]
    kf[1] = [1.0, 2., 0., 0., 1., 0., 0., 0., 1., 1., 1.]
    clip = f3d.AnimationClip(name="lerp", duration=1.0, fps=24.0, keyframes={"b": kf})
    m = clip.sample(0.5)["b"]
    assert np.allclose(m[:3, 3], [1., 0., 0.], atol=1e-6)


def test_clip_slerp_quaternion():
    """G1b: 쿼터니언 SLERP 보간 오차 < 1e-6."""
    from forge3d.animation.clip import _quat_slerp
    q0 = np.array([1., 0., 0., 0.])  # 항등
    q1 = np.array([0., 0., 0., 1.])  # 180° z 회전
    q_half = _quat_slerp(q0, q1, 0.5)
    # 정규화 확인
    assert abs(np.linalg.norm(q_half) - 1.0) < 1e-6
    # 90° 회전 — q_half[0] ≈ cos(45°)
    assert abs(abs(q_half[0]) - np.cos(np.pi / 4)) < 1e-6


# ── AnimationPlayer + BlendTree ───────────────────────────────────────────────

def test_animation_player_advance():
    """AnimationPlayer.advance(dt)가 _time을 증가시킨다."""
    pos = np.zeros(3); quat = np.array([1., 0., 0., 0.]); scale = np.ones(3)
    clip = f3d.AnimationClip.constant("c", 2.0, {"b": (pos, quat, scale)})
    skel = f3d.Skeleton.chain([np.zeros(3), np.array([1., 0., 0.])])
    player = f3d.AnimationPlayer(skeleton=skel, clip=clip, loop=True)
    player.advance(0.5)
    assert abs(player.current_time - 0.5) < 1e-9


def test_blend_tree_parameter():
    """G3: BlendTree parameter=0.5에서 두 클립 중간값 반환."""
    pos_a = np.array([0., 0., 0.]); pos_b = np.array([2., 0., 0.])
    q = np.array([1., 0., 0., 0.]); s = np.ones(3)
    clip_a = f3d.AnimationClip.constant("a", 1.0, {"bone": (pos_a, q, s)})
    clip_b = f3d.AnimationClip.constant("b", 1.0, {"bone": (pos_b, q, s)})
    tree = f3d.BlendTree(clip_a=clip_a, clip_b=clip_b, parameter=0.5)
    result = tree.sample(0.0)
    # 위치 = (0+2)/2 = 1
    pos = result["bone"][:3, 3]
    assert np.allclose(pos, [1., 0., 0.], atol=1e-6)


def test_blend_tree_extremes():
    """BlendTree parameter=0: clip_a, parameter=1: clip_b."""
    pos_a = np.array([0., 0., 0.]); pos_b = np.array([4., 0., 0.])
    q = np.array([1., 0., 0., 0.]); s = np.ones(3)
    clip_a = f3d.AnimationClip.constant("a", 1.0, {"b": (pos_a, q, s)})
    clip_b = f3d.AnimationClip.constant("b", 1.0, {"b": (pos_b, q, s)})

    tree0 = f3d.BlendTree(clip_a=clip_a, clip_b=clip_b, parameter=0.0)
    assert np.allclose(tree0.sample(0.0)["b"][:3, 3], [0., 0., 0.], atol=1e-6)

    tree1 = f3d.BlendTree(clip_a=clip_a, clip_b=clip_b, parameter=1.0)
    assert np.allclose(tree1.sample(0.0)["b"][:3, 3], [4., 0., 0.], atol=1e-6)


# ── G2: FABRIK IK ────────────────────────────────────────────────────────────

def test_fabrik_3link_convergence():
    """G2: 3링크 체인 FABRIK 수렴 — 끝단 오차 < 1e-4m."""
    solver = f3d.FABRIKSolver()
    chain = [
        np.array([0., 0., 0.]),
        np.array([1., 0., 0.]),
        np.array([2., 0., 0.]),
    ]
    target = np.array([1.5, 1.0, 0.])

    solved = solver.solve(chain, target, max_iterations=20, tolerance=1e-4)
    error = float(np.linalg.norm(solved[-1] - target))
    assert error < 1e-4, f"FABRIK 수렴 실패: error={error:.6f}m"
    assert len(solved) == 3


def test_fabrik_straight_target():
    """목표가 일직선 방향이면 체인이 펴진다."""
    solver = f3d.FABRIKSolver()
    chain = [np.array([0., 0., 0.]), np.array([1., 0., 0.]), np.array([2., 0., 0.])]
    target = np.array([2., 0., 0.])
    solved = solver.solve(chain, target, max_iterations=10)
    assert np.linalg.norm(solved[-1] - target) < 1e-4


def test_fabrik_unreachable_target():
    """도달 불가능한 목표 — 체인이 목표 방향으로 최대한 뻗는다."""
    solver = f3d.FABRIKSolver()
    chain = [np.array([0., 0., 0.]), np.array([1., 0., 0.])]
    target = np.array([100., 0., 0.])
    solved = solver.solve(chain, target)
    # 끝단이 목표 방향으로 최대한 뻗어야 함
    assert solved[-1][0] > 0.9


def test_fabrik_2d_reachability():
    """2D 평면에서 도달 가능한 임의 목표 테스트."""
    solver = f3d.FABRIKSolver()
    rng = np.random.default_rng(42)
    for _ in range(5):
        pos = rng.uniform(-1.5, 1.5, 3)
        pos[2] = 0.0
        chain = [np.zeros(3), np.array([0., 1., 0.]), np.array([0., 2., 0.])]
        solved = solver.solve(chain, pos, max_iterations=50, tolerance=1e-3)
        err = np.linalg.norm(solved[-1] - pos)
        # 총 링크 길이 2 이내 목표면 수렴해야 함
        if np.linalg.norm(pos) <= 2.0:
            assert err < 1e-2, f"err={err}"


# ── AnimationSystem ECS ───────────────────────────────────────────────────────

def test_animation_system_update():
    """AnimationSystem.update()가 예외 없이 실행된다."""
    skel = f3d.Skeleton.chain([np.zeros(3), np.array([1., 0., 0.])])
    q = np.array([1., 0., 0., 0.]); s = np.ones(3)
    clip = f3d.AnimationClip.constant("c", 1.0, {"bone_0": (np.zeros(3), q, s)})
    player = f3d.AnimationPlayer(skeleton=skel, clip=clip)

    ew = f3d.EntityWorld()
    ew.create_entity(player)

    sys = f3d.AnimationSystem()
    ew.add_system(sys)
    ew.step(0.016)  # 예외 없음 확인
