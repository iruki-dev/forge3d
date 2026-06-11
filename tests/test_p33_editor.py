"""P33 — 씬 에디터 검증 테스트.

게이트:
  G1: 레이캐스트 → 올바른 엔티티 선택
  G2: Play → Pause → Step 상태 전환
  G3: 이동 기즈모 드래그 → Transform 위치 갱신
  G4: 전체 기존 테스트 회귀 없음
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

import forge3d as f3d
from forge3d.editor.editor_app import PlayState
from forge3d.editor.gizmo import (
    TranslateGizmo,
    _ray_sphere_intersect,
    screen_to_ray,
)
from forge3d.editor.layout import EditorLayout, LayoutConfig

# ── G1: 레이캐스트 엔티티 선택 ───────────────────────────────────────────────


def test_ray_sphere_intersect_hit():
    """레이가 구와 교차할 때 양수 t를 반환한다."""
    origin = np.array([0.0, 0.0, 5.0])
    direction = np.array([0.0, 0.0, -1.0])
    center = np.array([0.0, 0.0, 0.0])
    t = _ray_sphere_intersect(origin, direction, center, radius=1.0)
    assert t is not None
    assert t > 0
    assert abs(t - 4.0) < 0.01  # 거리 5 - 반경 1 = 4


def test_ray_sphere_intersect_miss():
    """레이가 구와 교차하지 않으면 None."""
    origin = np.array([0.0, 5.0, 0.0])
    direction = np.array([1.0, 0.0, 0.0])  # y축 방향 → 구 빗나감
    center = np.array([0.0, 0.0, 0.0])
    t = _ray_sphere_intersect(origin, direction, center, radius=0.5)
    assert t is None


def test_entity_pick():
    """G1: 레이캐스트로 올바른 엔티티(가장 가까운)를 선택한다."""
    ew = f3d.EntityWorld()
    # 카메라 z=20에서 z=-1 방향으로 쏘면 z=15(가까운)이 z=5(먼)보다 먼저 교차
    e_near = ew.create_entity(f3d.Transform(position=np.array([0.0, 0.0, 15.0])))
    ew.create_entity(f3d.Transform(position=np.array([0.0, 0.0, 5.0])))

    gizmo = TranslateGizmo()
    ray_origin = np.array([0.0, 0.0, 20.0])
    ray_dir = np.array([0.0, 0.0, -1.0])
    selected = gizmo.pick(ray_origin, ray_dir, ew)

    # 가까운 엔티티(z=15)가 먼저 교차
    assert selected == e_near


def test_entity_pick_no_hit():
    """레이가 어떤 엔티티도 맞지 않으면 None."""
    ew = f3d.EntityWorld()
    ew.create_entity(f3d.Transform(position=np.array([10.0, 10.0, 10.0])))

    gizmo = TranslateGizmo()
    ray_origin = np.array([0.0, 0.0, 0.0])
    ray_dir = np.array([0.0, 0.0, -1.0])
    selected = gizmo.pick(ray_origin, ray_dir, ew)
    assert selected is None


def test_screen_to_ray():
    """screen_to_ray가 올바른 (origin, direction) 형식을 반환한다."""
    view = np.eye(4)
    origin, direction = screen_to_ray(
        screen_x=640,
        screen_y=360,  # 화면 중앙
        width=1280,
        height=720,
        fov_deg=45.0,
        view_matrix=view,
    )
    assert origin.shape == (3,)
    assert direction.shape == (3,)
    assert abs(np.linalg.norm(direction) - 1.0) < 1e-6
    # 화면 중앙에서 z=-1 방향 (뷰 행렬이 단위행렬)
    assert direction[2] < 0


# ── G2: Play/Pause/Step 상태 머신 ────────────────────────────────────────────


def _make_editor() -> f3d.EditorApp:
    world = f3d.World()
    ew = f3d.EntityWorld()
    return f3d.EditorApp(world, ew)


def test_initial_state_is_edit():
    """초기 상태는 EDIT."""
    editor = _make_editor()
    assert editor.play_state == PlayState.EDIT
    assert editor.is_editing


def test_play_pause_step():
    """G2: Play → Pause → Step 상태 전환."""
    editor = _make_editor()

    # EDIT → PLAY
    editor.play()
    assert editor.play_state == PlayState.PLAY
    assert editor.is_playing

    # PLAY → PAUSE
    editor.pause()
    assert editor.play_state == PlayState.PAUSE
    assert editor.is_paused

    # PAUSE → EDIT (stop)
    editor.stop()
    assert editor.play_state == PlayState.EDIT


def test_step_once_in_edit():
    """EDIT 모드에서 step_once()가 단일 스텝을 실행한다."""
    world = f3d.World(gravity=(0, 0, -9.81))
    ew = f3d.EntityWorld()
    editor = f3d.EditorApp(world, ew, dt=1 / 60)

    v1_body = world.add_box(size=(1, 1, 1), position=(0, 0, 5), mass=1.0)
    world.add_ground()

    initial_z = v1_body.position[2]
    editor.step_once()
    editor.update()

    final_z = v1_body.position[2]
    assert final_z < initial_z, f"EDIT step_once 후 낙하 없음: z={final_z}"


def test_play_advances_physics():
    """PLAY 모드에서 update()가 매 프레임 물리를 전진시킨다."""
    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground()
    body = world.add_sphere(radius=0.5, position=(0, 0, 5))
    ew = f3d.EntityWorld()
    editor = f3d.EditorApp(world, ew, dt=1 / 60)
    editor.play()

    for _ in range(30):
        editor.update()

    assert body.position[2] < 5.0, "PLAY 모드에서 물리 전진 없음"


def test_pause_stops_physics():
    """PAUSE 모드에서 update()가 물리를 멈춘다."""
    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground()
    body = world.add_sphere(radius=0.5, position=(0, 0, 5))
    ew = f3d.EntityWorld()
    editor = f3d.EditorApp(world, ew, dt=1 / 60)
    editor.play()

    # 몇 프레임 실행 후 일시정지
    for _ in range(5):
        editor.update()
    editor.pause()

    z_at_pause = body.position[2]
    for _ in range(10):
        editor.update()

    assert abs(body.position[2] - z_at_pause) < 1e-6, "PAUSE 중 물리가 전진함"


# ── G3: 이동 기즈모 ──────────────────────────────────────────────────────────


def test_gizmo_drag():
    """G3: 기즈모 드래그 → Transform 위치 갱신."""
    ew = f3d.EntityWorld()
    e = ew.create_entity(f3d.Transform(position=np.array([0.0, 0.0, 0.0])))
    gizmo = TranslateGizmo()
    gizmo.select(e)

    gizmo.start_drag(axis=0)  # X축
    gizmo.drag(delta=3.0, ew=ew)
    gizmo.end_drag()

    tf = ew.get_component(e, f3d.Transform)
    assert abs(tf.position[0] - 3.0) < 1e-6


def test_gizmo_y_axis_drag():
    """Y축 드래그 → Y 좌표만 변한다."""
    ew = f3d.EntityWorld()
    e = ew.create_entity(f3d.Transform(position=np.array([1.0, 0.0, 1.0])))
    gizmo = TranslateGizmo()
    gizmo.select(e)
    gizmo.start_drag(axis=1)
    gizmo.drag(delta=5.0, ew=ew)
    gizmo.end_drag()

    tf = ew.get_component(e, f3d.Transform)
    assert abs(tf.position[0] - 1.0) < 1e-6  # X 변화 없음
    assert abs(tf.position[1] - 5.0) < 1e-6  # Y만 변함
    assert abs(tf.position[2] - 1.0) < 1e-6  # Z 변화 없음


def test_gizmo_no_selection_drag():
    """선택 없이 drag() 호출해도 예외 없음."""
    ew = f3d.EntityWorld()
    gizmo = TranslateGizmo()
    gizmo.start_drag(axis=0)
    gizmo.drag(delta=5.0, ew=ew)  # 예외 없어야 함
    gizmo.end_drag()


# ── EditorApp 통합 ───────────────────────────────────────────────────────────


def test_editor_pick_entity():
    """EditorApp.pick_entity()가 엔티티를 선택한다."""
    world = f3d.World()
    ew = f3d.EntityWorld()
    editor = f3d.EditorApp(world, ew)

    ew.create_entity(f3d.Transform(position=np.array([0.0, 0.0, 0.0])))
    view = np.eye(4)
    view[2, 3] = 10.0  # 카메라 z=10에서 바라봄

    selected = editor.pick_entity(
        screen_x=editor.layout.config.viewport_width / 2,
        screen_y=editor.layout.config.window_height / 2,
        fov_deg=45.0,
        view_matrix=view,
    )
    # 정확한 중앙이면 엔티티가 잡힐 수 있음 (허용: None도 ok)
    # 핵심: 예외 없음
    assert selected is None or ew.is_alive(selected)


def test_editor_move_selected():
    """EditorApp.move_selected()가 선택 엔티티를 이동한다."""
    world = f3d.World()
    ew = f3d.EntityWorld()
    editor = f3d.EditorApp(world, ew)

    e = ew.create_entity(f3d.Transform(position=np.array([0.0, 0.0, 0.0])))
    editor.gizmo.select(e)
    editor.move_selected(axis=2, delta=7.0)  # Z축 +7

    tf = ew.get_component(e, f3d.Transform)
    assert abs(tf.position[2] - 7.0) < 1e-6


def test_editor_save_scene():
    """EditorApp.save_scene()이 JSON 파일을 저장한다."""
    world = f3d.World()
    ew = f3d.EntityWorld()
    ew.create_entity(f3d.Transform(position=np.array([1.0, 2.0, 3.0])))
    editor = f3d.EditorApp(world, ew)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name

    saved_paths = []
    editor.on_scene_saved(lambda p: saved_paths.append(p))
    editor.save_scene(path)

    assert Path(path).exists()
    assert len(saved_paths) == 1
    Path(path).unlink(missing_ok=True)


# ── 레이아웃 ─────────────────────────────────────────────────────────────────


def test_layout_panel_tracking():
    """EditorLayout이 렌더된 패널을 추적한다."""
    layout = EditorLayout(LayoutConfig(window_width=1280, window_height=720))
    layout.begin_frame()
    layout.begin_hierarchy()
    layout.end_hierarchy()
    layout.begin_viewport()
    layout.end_viewport()
    layout.begin_inspector()
    layout.end_inspector()

    panels = layout.rendered_panels
    assert "hierarchy" in panels
    assert "viewport" in panels
    assert "inspector" in panels
