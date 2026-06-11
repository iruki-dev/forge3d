"""P27 — ECS 검증 테스트.

게이트:
  G1: EntityWorld 생성/쿼리/소멸
  G2: Transform 계층: 부모 이동 → 자식 월드 행렬 갱신
  G3: PhysicsSystem 하에서 중력 낙하
  G4: v1 Body → ECS 브릿지
  G5: ECS 씬 save → load 재현 일치
  G6: examples/05_ecs_scene.py 동작
  G7: v1 API 호환
  G8: 전체 회귀 없음
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

# ── G1: EntityWorld 생명주기 ──────────────────────────────────────────────────


def test_entity_create_and_destroy():
    """G1a: 엔티티 생성/소멸."""
    import forge3d as f3d

    ew = f3d.EntityWorld()
    e = ew.create_entity()
    assert ew.is_alive(e)
    ew.destroy_entity(e)
    assert not ew.is_alive(e)


def test_entity_not_found_error():
    """G1b: 소멸된 엔티티 접근 시 EntityNotFoundError."""
    import forge3d as f3d

    ew = f3d.EntityWorld()
    e = ew.create_entity()
    ew.destroy_entity(e)
    with pytest.raises(f3d.EntityNotFoundError):
        ew.get_component(e, f3d.Transform)


def test_component_crud():
    """G1c: 컴포넌트 추가/조회/삭제."""
    import forge3d as f3d

    ew = f3d.EntityWorld()
    e = ew.create_entity()
    tf = f3d.Transform(position=np.array([1.0, 2.0, 3.0]))
    ew.add_component(e, tf)
    got = ew.get_component(e, f3d.Transform)
    assert np.allclose(got.position, [1.0, 2.0, 3.0])
    ew.remove_component(e, f3d.Transform)
    with pytest.raises(KeyError):
        ew.get_component(e, f3d.Transform)


def test_query_returns_matching_entities():
    """G1d: query()가 두 타입 모두 가진 엔티티만 반환한다."""
    import forge3d as f3d

    ew = f3d.EntityWorld()
    e1 = ew.create_entity(f3d.Transform(), f3d.Rigidbody(mass=1.0))
    e2 = ew.create_entity(f3d.Transform())  # Rigidbody 없음
    _e3 = ew.create_entity(f3d.Rigidbody(mass=2.0))  # Transform 없음

    results = list(ew.query(f3d.Transform, f3d.Rigidbody))
    entities = [r[0] for r in results]
    assert e1 in entities
    assert e2 not in entities


def test_query_empty_on_destroyed():
    """소멸된 엔티티는 query에서 제외된다."""
    import forge3d as f3d

    ew = f3d.EntityWorld()
    e = ew.create_entity(f3d.Transform())
    ew.destroy_entity(e)
    results = list(ew.query(f3d.Transform))
    assert len(results) == 0


# ── G2: Transform 계층 ───────────────────────────────────────────────────────


def test_transform_local_matrix():
    """G2a: 로컬 행렬이 위치를 올바르게 반영한다."""
    import forge3d as f3d

    tf = f3d.Transform(position=np.array([3.0, 0.0, 0.0]))
    M = tf.local_matrix()
    assert M.shape == (4, 4)
    assert np.allclose(M[:3, 3], [3.0, 0.0, 0.0])


def test_transform_hierarchy():
    """G2b: 부모 이동 시 자식 월드 위치가 갱신된다."""
    import forge3d as f3d

    ew = f3d.EntityWorld()

    parent = ew.create_entity(f3d.Transform(position=np.array([10.0, 0.0, 0.0])))
    child_tf = f3d.Transform(position=np.array([1.0, 0.0, 0.0]), parent=parent)
    ew.create_entity(child_tf)

    world_pos = child_tf.world_position(ew)
    assert np.allclose(world_pos, [11.0, 0.0, 0.0]), f"world_pos={world_pos}"


def test_transform_deep_hierarchy():
    """G2c: 3단계 계층 월드 행렬 정확성."""
    import forge3d as f3d

    ew = f3d.EntityWorld()

    root = ew.create_entity(f3d.Transform(position=np.array([1.0, 0.0, 0.0])))
    mid_tf = f3d.Transform(position=np.array([1.0, 0.0, 0.0]), parent=root)
    mid = ew.create_entity(mid_tf)
    leaf_tf = f3d.Transform(position=np.array([1.0, 0.0, 0.0]), parent=mid)
    ew.create_entity(leaf_tf)

    pos = leaf_tf.world_position(ew)
    assert np.allclose(pos, [3.0, 0.0, 0.0]), f"pos={pos}"


def test_transform_cycle_detection():
    """G2d: 순환 부모 감지 시 Forge3dError 발생."""
    import forge3d as f3d
    from forge3d.errors import Forge3dError

    ew = f3d.EntityWorld()

    a_tf = f3d.Transform()
    a = ew.create_entity(a_tf)
    b_tf = f3d.Transform(parent=a)
    b = ew.create_entity(b_tf)
    a_tf.parent = b  # 순환

    with pytest.raises(Forge3dError):
        a_tf.world_matrix(ew)


def test_jax_batch_world_matrix():
    """G2e: jax_batch_world_matrix가 (N,4,4) 반환."""
    import forge3d as f3d
    from forge3d.ecs import jax_batch_world_matrix

    tfs = [f3d.Transform(position=np.array([float(i), 0.0, 0.0])) for i in range(5)]
    mats = jax_batch_world_matrix(tfs)
    assert mats.shape == (5, 4, 4)
    assert np.allclose(mats[3, :3, 3], [3.0, 0.0, 0.0])


# ── G3: PhysicsSystem 낙하 ───────────────────────────────────────────────────


def test_physics_system_gravity():
    """G3: PhysicsSystem 하에서 Rigidbody 엔티티가 낙하한다 (v1 World 연결)."""
    import forge3d as f3d

    v1_world = f3d.World(gravity=(0, 0, -9.81))
    v1_world.add_ground()

    ew = f3d.EntityWorld()
    phys = f3d.PhysicsSystem(world=v1_world)
    ew.add_system(phys)

    # v1 Body 생성 후 ECS로 래핑
    v1_body = v1_world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)
    from forge3d.ecs import body_to_entity

    entity = body_to_entity(v1_world, v1_body, ew)

    initial_z = ew.get_component(entity, f3d.Transform).position[2]

    # 30 스텝
    for _ in range(30):
        ew.step(1 / 60)

    final_z = ew.get_component(entity, f3d.Transform).position[2]
    assert final_z < initial_z, f"낙하 안 함: z {initial_z} → {final_z}"


# ── G4: v1 Body 브릿지 ───────────────────────────────────────────────────────


def test_v1_bridge_position_sync():
    """G4: body_to_entity 후 Transform 위치가 v1 Body와 일치한다."""
    import forge3d as f3d
    from forge3d.ecs import body_to_entity

    world = f3d.World()
    body = world.add_sphere(radius=0.5, position=(1.0, 2.0, 3.0))
    ew = f3d.EntityWorld()
    entity = body_to_entity(world, body, ew)

    tf = ew.get_component(entity, f3d.Transform)
    assert np.allclose(tf.position, [1.0, 2.0, 3.0], atol=0.05)


def test_v1_bridge_rigidbody():
    """G4b: 브릿지로 생성된 엔티티에 Rigidbody가 있다."""
    import forge3d as f3d
    from forge3d.ecs import body_to_entity

    world = f3d.World()
    body = world.add_box(size=(1, 1, 1), position=(0, 0, 1), mass=2.0)
    ew = f3d.EntityWorld()
    entity = body_to_entity(world, body, ew)

    rb = ew.get_component(entity, f3d.Rigidbody)
    assert abs(rb.mass - 2.0) < 1e-9


# ── G5: 직렬화 ───────────────────────────────────────────────────────────────


def test_scene_save_load():
    """G5: save → load 후 엔티티 수와 Transform 위치가 일치한다."""
    import forge3d as f3d
    from forge3d.ecs import load_scene, save_scene

    ew = f3d.EntityWorld()
    ew.create_entity(
        f3d.Transform(position=np.array([1.0, 2.0, 3.0])),
        f3d.Rigidbody(mass=5.0),
    )
    ew.create_entity(
        f3d.Transform(position=np.array([0.0, 0.0, 0.0])),
        f3d.MeshRenderer(mesh_id="box_1x1x1", material_id="red"),
    )

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    save_scene(ew, path)

    # JSON 파일 확인
    data = json.loads(Path(path).read_text())
    assert "entities" in data
    assert len(data["entities"]) == 2

    ew2 = load_scene(path)
    assert len(ew2.all_entities()) == 2

    # Transform 위치 비교
    positions = []
    for _e, tf in ew2.query(f3d.Transform):
        positions.append(tf.position.tolist())  # type: ignore[union-attr]
    assert any(np.allclose(p, [1.0, 2.0, 3.0]) for p in positions)


# ── G6: 예제 파일 ─────────────────────────────────────────────────────────────


def test_example_05_ecs_scene():
    """G6: examples/05_ecs_scene.py가 에러 없이 실행된다."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "examples/05_ecs_scene.py"],
        cwd="/workspaces/2026_python_toy_project_1",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"예제 실패:\n{result.stderr}"
    assert "완료" in result.stdout


# ── G7: v1 API 호환 ──────────────────────────────────────────────────────────


def test_v1_api_unaffected():
    """G7: v1 World/Body/Viewer API가 깨지지 않는다."""
    import forge3d as f3d

    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground()
    box = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)
    for _ in range(10):
        world.step(dt=1 / 60)
    assert box.position[2] < 5.0, "중력 낙하 실패 (v1 World)"


def test_render_system_snapshot():
    """G5b: RenderSystem.last_snapshot에 Body가 포함된다."""
    import forge3d as f3d

    ew = f3d.EntityWorld()
    ew.create_entity(
        f3d.Transform(position=np.array([1.0, 0.0, 0.0])),
        f3d.MeshRenderer(mesh_id="box_1x1x1", material_id="red"),
    )
    rs = f3d.RenderSystem()
    ew.add_system(rs)
    ew.step(0.016)

    assert rs.last_snapshot is not None
    assert len(rs.last_snapshot.bodies) == 1
