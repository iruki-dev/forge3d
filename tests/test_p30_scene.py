"""P30 — 씬 관리 검증 테스트.

게이트:
  G1: 부모 이동 → 자식 월드 위치 갱신
  G2: Prefab save/load/instantiate 재현
  G3: load_scene 후 이전 씬 엔티티 0개
  G4: 전체 기존 테스트 회귀 없음
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

import forge3d as f3d


def _make_ew() -> f3d.EntityWorld:
    return f3d.EntityWorld()


# ── G1: SceneNode 계층 ───────────────────────────────────────────────────────

def test_scene_node_world_position():
    """G1a: SceneNode.world_position()이 올바른 값을 반환한다."""
    ew = _make_ew()
    parent_e = ew.create_entity(f3d.Transform(position=np.array([5., 0., 0.])))
    parent_node = f3d.SceneNode("parent", parent_e, ew)

    child_e = ew.create_entity(f3d.Transform(position=np.array([1., 0., 0.])))
    child_node = f3d.SceneNode("child", child_e, ew)
    parent_node.add_child(child_node)

    world_pos = child_node.world_position()
    assert np.allclose(world_pos, [6., 0., 0.]), f"world_pos={world_pos}"


def test_parent_move_updates_child():
    """G1b: 부모 위치 변경 → 자식 월드 위치 갱신."""
    ew = _make_ew()
    parent_e = ew.create_entity(f3d.Transform(position=np.array([0., 0., 0.])))
    parent_node = f3d.SceneNode("parent", parent_e, ew)

    child_e = ew.create_entity(f3d.Transform(position=np.array([1., 0., 0.])))
    child_node = f3d.SceneNode("child", child_e, ew)
    parent_node.add_child(child_node)

    # 부모 이동
    parent_node.local_position = np.array([10., 0., 0.])
    new_world = child_node.world_position()
    assert np.allclose(new_world, [11., 0., 0.]), f"new_world={new_world}"


def test_dirty_flag_caches_matrix():
    """T2: dirty flag — 변경 없으면 캐시를 재사용한다."""
    ew = _make_ew()
    e = ew.create_entity(f3d.Transform(position=np.array([1., 2., 3.])))
    node = f3d.SceneNode("root", e, ew)

    m1 = node.world_matrix()
    m2 = node.world_matrix()
    assert m1 is m2, "변경 없으면 동일 객체를 반환해야 함"


def test_dirty_flag_invalidated_on_move():
    """T2: 위치 변경 시 캐시가 무효화된다."""
    ew = _make_ew()
    e = ew.create_entity(f3d.Transform(position=np.array([0., 0., 0.])))
    node = f3d.SceneNode("root", e, ew)

    m1 = node.world_matrix()
    node.local_position = np.array([5., 0., 0.])
    m2 = node.world_matrix()
    assert not np.allclose(m1[:3, 3], m2[:3, 3]), "이동 후 행렬이 갱신되어야 함"


def test_remove_child():
    """자식 제거 후 부모 이동이 영향 없음."""
    ew = _make_ew()
    parent_e = ew.create_entity(f3d.Transform(position=np.array([3., 0., 0.])))
    parent_node = f3d.SceneNode("parent", parent_e, ew)
    child_e = ew.create_entity(f3d.Transform(position=np.array([1., 0., 0.])))
    child_node = f3d.SceneNode("child", child_e, ew)
    parent_node.add_child(child_node)
    parent_node.remove_child(child_node)

    parent_node.local_position = np.array([100., 0., 0.])
    child_pos = child_node.world_position()
    # 자식이 독립: 부모 좌표계에서 분리됨 (Transform.parent=None이므로 로컬=월드)
    assert np.allclose(child_pos, [1., 0., 0.]), f"child_pos={child_pos}"


def test_find_node():
    """SceneNode.find()로 이름 검색."""
    ew = _make_ew()
    root_e = ew.create_entity(f3d.Transform())
    root = f3d.SceneNode("root", root_e, ew)
    child_e = ew.create_entity(f3d.Transform())
    child = f3d.SceneNode("weapon", child_e, ew)
    root.add_child(child)

    found = root.find("weapon")
    assert found is child
    assert root.find("nonexistent") is None


# ── G2: Prefab ───────────────────────────────────────────────────────────────

def test_prefab_save_load_instantiate():
    """G2: Prefab save → load → instantiate 위치 일치."""
    ew = _make_ew()
    entity = ew.create_entity(
        f3d.Transform(position=np.array([7., 8., 9.])),
        f3d.MeshRenderer(mesh_id="box_1x1x1", material_id="red"),
        f3d.Rigidbody(mass=2.0),
    )
    node = f3d.SceneNode("hero", entity, ew)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    # 저장
    f3d.Prefab.save(node, path)
    data = json.loads(Path(path).read_text())
    assert data["name"] == "hero"
    assert len(data["components"]) >= 1

    # 로드 + 인스턴스화
    prefab = f3d.Prefab.load(path)
    ew2 = _make_ew()
    new_pos = np.array([1., 2., 3.])
    new_node = prefab.instantiate(ew2, position=new_pos)

    tf = ew2.get_component(new_node.entity, f3d.Transform)
    assert np.allclose(tf.position, new_pos, atol=1e-6)
    Path(path).unlink(missing_ok=True)


def test_prefab_with_children():
    """Prefab 저장 시 자식 노드도 포함된다."""
    ew = _make_ew()
    parent_e = ew.create_entity(f3d.Transform(position=np.array([0., 0., 0.])))
    parent_node = f3d.SceneNode("parent", parent_e, ew)
    child_e = ew.create_entity(f3d.Transform(position=np.array([1., 0., 0.])))
    child_node = f3d.SceneNode("child", child_e, ew)
    parent_node.add_child(child_node)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    f3d.Prefab.save(parent_node, path)
    data = json.loads(Path(path).read_text())
    assert len(data["children"]) == 1
    assert data["children"][0]["name"] == "child"

    prefab = f3d.Prefab.load(path)
    ew2 = _make_ew()
    new_node = prefab.instantiate(ew2)
    assert len(new_node.children) == 1
    Path(path).unlink(missing_ok=True)


# ── G3: SceneManager 로드/언로드 ─────────────────────────────────────────────

def test_scene_manager_load_unload():
    """G3: load_scene 후 이전 씬 엔티티가 소멸된다."""
    ew = _make_ew()
    mgr = f3d.SceneManager(ew)

    # 씬 1 저장
    temp_ew1 = _make_ew()
    temp_ew1.create_entity(f3d.Transform(position=np.array([0., 0., 0.])))
    temp_ew1.create_entity(f3d.Transform(position=np.array([1., 0., 0.])))
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        scene1_path = f.name
    from forge3d.ecs.serialization import save_scene
    save_scene(temp_ew1, scene1_path)

    # 씬 2 저장
    temp_ew2 = _make_ew()
    temp_ew2.create_entity(f3d.Transform(position=np.array([99., 0., 0.])))
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        scene2_path = f.name
    save_scene(temp_ew2, scene2_path)

    mgr.load_scene(scene1_path)
    assert mgr.entity_count == 2

    mgr.load_scene(scene2_path)
    # 씬1 엔티티 소멸, 씬2 엔티티 1개만 있어야 함
    assert mgr.entity_count == 1

    Path(scene1_path).unlink(missing_ok=True)
    Path(scene2_path).unlink(missing_ok=True)


def test_scene_manager_additive():
    """add_scene()은 기존 씬을 유지하며 추가 로드한다."""
    ew = _make_ew()
    mgr = f3d.SceneManager(ew)

    temp_ew = _make_ew()
    temp_ew.create_entity(f3d.Transform())
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    from forge3d.ecs.serialization import save_scene
    save_scene(temp_ew, path)

    mgr.load_scene(path)  # 1 엔티티
    mgr.add_scene(path)   # 1 더 추가 → 2 엔티티
    assert mgr.entity_count == 2
    Path(path).unlink(missing_ok=True)


def test_scene_manager_on_loaded_callback():
    """on_scene_loaded 콜백이 씬 로드 후 호출된다."""
    ew = _make_ew()
    mgr = f3d.SceneManager(ew)
    call_count = [0]

    mgr.on_scene_loaded(lambda: call_count.__setitem__(0, call_count[0] + 1))

    temp_ew = _make_ew()
    temp_ew.create_entity(f3d.Transform())
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    from forge3d.ecs.serialization import save_scene
    save_scene(temp_ew, path)

    mgr.load_scene(path)
    mgr.load_scene(path)
    assert call_count[0] == 2
    Path(path).unlink(missing_ok=True)
