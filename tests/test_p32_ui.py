"""P32 — UI 시스템 검증 테스트.

게이트:
  G1: DebugPanel.render() 예외 없음 (null 백엔드)
  G2: InspectorPanel 편집 → ECS 컴포넌트 값 반영
  G3: Canvas.text() 좌표 범위 벗어나면 clip (예외 없음)
  G4: 전체 기존 테스트 회귀 없음
"""
from __future__ import annotations

import numpy as np
import pytest

import forge3d as f3d
from forge3d.ui.backend import NullImGui


# ── G1: DebugPanel ────────────────────────────────────────────────────────────

def test_debug_panel_no_exception():
    """G1: null 백엔드에서 DebugPanel.render()가 예외 없이 실행된다."""
    panel = f3d.DebugPanel(title="Test Debug")
    panel.render(fps=60.0, body_count=10, step_ms=2.5)


def test_debug_panel_state_update():
    """DebugPanel.state에 렌더된 값이 기록된다."""
    panel = f3d.DebugPanel()
    panel.render(fps=30.0, body_count=5, step_ms=1.0)
    assert abs(panel.state.fps - 30.0) < 1e-6
    assert panel.state.body_count == 5
    assert abs(panel.state.step_ms - 1.0) < 1e-6
    assert panel.state.frame_count == 1


def test_debug_panel_frame_count():
    """render() 호출 횟수만큼 frame_count가 증가한다."""
    panel = f3d.DebugPanel()
    for _ in range(5):
        panel.render(fps=60.0)
    assert panel.state.frame_count == 5


def test_null_imgui_call_recording():
    """NullImGui가 호출 기록을 남긴다."""
    null = NullImGui()
    null.text("hello")
    null.text("world")
    assert null.call_count == 2
    null.clear()
    assert null.call_count == 0


# ── G2: InspectorPanel ───────────────────────────────────────────────────────

def test_inspector_panel_no_exception():
    """G2a: 엔티티 없어도 예외 없음."""
    panel = f3d.InspectorPanel()
    ew = f3d.EntityWorld()
    panel.render(ew=ew, selected=None)


def test_inspector_panel_renders_entity():
    """G2b: 엔티티가 있을 때 예외 없이 렌더한다."""
    panel = f3d.InspectorPanel()
    ew = f3d.EntityWorld()
    e = ew.create_entity(f3d.Transform(position=np.array([1., 2., 3.])))
    panel.render(ew=ew, selected=e)


def test_inspector_panel_field_edit():
    """G2c: set_field + render → ECS Transform 위치 업데이트."""
    panel = f3d.InspectorPanel()
    ew = f3d.EntityWorld()
    e = ew.create_entity(f3d.Transform(position=np.array([0., 0., 0.])))

    # 편집 트리거
    panel.select(e)
    panel.set_field("position", [5., 6., 7.])
    panel.render(ew=ew)

    tf = ew.get_component(e, f3d.Transform)
    assert np.allclose(tf.position, [5., 6., 7.])


def test_inspector_ignores_destroyed_entity():
    """소멸된 엔티티 선택 시 예외 없음."""
    panel = f3d.InspectorPanel()
    ew = f3d.EntityWorld()
    e = ew.create_entity(f3d.Transform())
    ew.destroy_entity(e)
    panel.render(ew=ew, selected=e)  # 예외 없어야 함


# ── HierarchyPanel ────────────────────────────────────────────────────────────

def test_hierarchy_panel_entity_list():
    """HierarchyPanel.render() 후 entity_count가 갱신된다."""
    panel = f3d.HierarchyPanel()
    ew = f3d.EntityWorld()
    ew.create_entity(f3d.Transform())
    ew.create_entity(f3d.Transform())
    panel.render(ew=ew)
    assert panel.entity_count == 2


# ── G3: Canvas 클리핑 ─────────────────────────────────────────────────────────

def test_canvas_text_in_bounds():
    """G3a: 화면 안 좌표 텍스트는 커맨드 버퍼에 기록된다."""
    canvas = f3d.Canvas(width=800, height=600)
    canvas.text((100, 200), "Hello")
    assert canvas.command_count == 1


def test_canvas_text_out_of_bounds():
    """G3b: 화면 밖 좌표는 clip — 예외 없고 커맨드 버퍼에 기록 안 됨."""
    canvas = f3d.Canvas(width=800, height=600)
    canvas.text((-100, -200), "Out")       # 완전 밖
    canvas.text((900, 700), "Also out")    # 완전 밖
    assert canvas.command_count == 0


def test_canvas_rect_clipping():
    """G3c: 직사각형이 완전히 화면 밖이면 clip."""
    canvas = f3d.Canvas(width=800, height=600)
    canvas.rect((-200, -200), (50, 50), (1., 0., 0., 1.))  # 화면 밖
    assert canvas.command_count == 0
    canvas.rect((100, 100), (50, 50), (0., 1., 0., 1.))    # 화면 안
    assert canvas.command_count == 1


def test_canvas_clear():
    """Canvas.clear() 후 커맨드 버퍼가 비워진다."""
    canvas = f3d.Canvas()
    canvas.text((10, 10), "A")
    canvas.text((20, 20), "B")
    assert canvas.command_count == 2
    canvas.clear()
    assert canvas.command_count == 0


def test_canvas_to_numpy():
    """Canvas.to_numpy()가 rect 명령을 픽셀로 래스터화한다."""
    canvas = f3d.Canvas(width=100, height=100)
    canvas.rect((10, 10), (20, 20), (1., 0., 0., 1.))
    buf = canvas.to_numpy()
    assert buf.shape == (100, 100, 4)
    # 직사각형 내부가 빨강
    assert buf[15, 15, 0] == 255  # R
    assert buf[15, 15, 1] == 0    # G


# ── UISystem ─────────────────────────────────────────────────────────────────

def test_ui_system_update():
    """UISystem.update()가 등록된 패널을 호출한다."""
    ew = f3d.EntityWorld()
    sys = f3d.UISystem()
    debug = f3d.DebugPanel()
    sys.add_panel(debug)
    sys.set_debug_info(fps=60.0, body_count=3, step_ms=1.5)
    sys.update(ew, dt=0.016)
    assert debug.state.fps == 60.0
    assert debug.state.body_count == 3


def test_ui_system_ecs_integration():
    """UISystem이 ECS에 등록되면 step()에서 자동 호출된다."""
    ew = f3d.EntityWorld()
    ui_sys = f3d.UISystem()
    debug = f3d.DebugPanel()
    ui_sys.add_panel(debug)
    ew.add_system(ui_sys)

    for _ in range(3):
        ew.step(0.016)

    assert debug.state.frame_count == 3
