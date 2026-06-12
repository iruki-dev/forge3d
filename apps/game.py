"""
╔══════════════════════════════════════════════════════╗
║         BALL RACE — forge3d 미니게임                ║
║                                                      ║
║  목표: 공을 조종해 골인 지점(녹색 존)에 도착하라!    ║
║                                                      ║
║  조작:                                               ║
║   WASD  / 방향키 — 공 굴리기                        ║
║   SPACE         — 점프                              ║
║   R             — 재시작                            ║
║   ESC           — 종료                              ║
╚══════════════════════════════════════════════════════╝
"""

import math
import sys
import time

import numpy as np

import forge3d as f3d

# ─────────────────────────── 게임 상수 ────────────────────────────
BALL_RADIUS   = 0.35
FORCE         = 14.0          # 굴리기 힘 (N)
JUMP_IMPULSE  = 7.5            # 점프 임펄스
MAX_SPEED     = 8.0            # 최대 수평 속도 (m/s)
RESPAWN_POS   = (0.0, 0.0, 2.0)

# ─────────────────────────── 전역 상태 ────────────────────────────
state = {
    "phase"      : "playing",   # "playing" | "win" | "dead"
    "score"      : 0,
    "lives"      : 3,
    "start_time" : time.perf_counter(),
    "best_time"  : None,
    "win_time"   : None,
}
ball      = None
goal_zone = None

# ─────────────────────────── App 설정 ─────────────────────────────
app = f3d.App("⚽ Ball Race — forge3d", width=1100, height=700, fps=60)


# ─────────────────────────── 월드 빌드 ────────────────────────────
def build_level(world: f3d.World) -> None:
    global ball, goal_zone

    world.clear()

    # ── 바닥 ──────────────────────────────────────────────────────
    world.add_ground(
        material=f3d.Material(color=(0.20, 0.22, 0.28), roughness=0.9),
        size=(80.0, 80.0, 0.2),
    )

    # ── 코스 플랫폼 (직선 복도 + 점프 구간) ──────────────────────
    platforms = [
        # (x_center, y_center, z_bottom, sx, sy, sz)
        (  0.0,  0.0, 0.5,   6.0, 3.0, 1.0),   # 출발 플랫폼
        (  0.0,  5.5, 0.5,   3.0, 8.0, 1.0),   # 긴 복도
        (  0.0, 12.0, 0.5,   6.0, 3.0, 1.0),   # 교차점
        ( -5.0, 14.5, 0.5,   6.0, 2.0, 1.0),   # 왼쪽 분기
        (  5.0, 14.5, 0.5,   6.0, 2.0, 1.0),   # 오른쪽 분기 (막힘)
        (  0.0, 18.5, 1.5,   4.0, 2.0, 1.0),   # 높은 플랫폼 (점프!)
        (  0.0, 23.0, 2.5,   4.0, 2.0, 1.0),   # 더 높은 곳
        (  0.0, 28.0, 3.5,   6.0, 4.0, 1.0),   # 최종 구역
    ]
    colors = [
        (0.30, 0.35, 0.55),
        (0.28, 0.40, 0.50),
        (0.25, 0.45, 0.50),
        (0.22, 0.48, 0.48),
        (0.55, 0.25, 0.25),  # 막힌 분기 — 붉은색
        (0.28, 0.52, 0.42),
        (0.30, 0.55, 0.38),
        (0.20, 0.60, 0.30),
    ]
    for (cx, cy, cz, sx, sy, sz), col in zip(platforms, colors):
        world.add_static_box(
            size=(sx, sy, sz),
            position=(cx, cy, cz + sz * 0.5),
            material=f3d.Material(color=col, roughness=0.6),
        )

    # ── 원기둥 기둥: 복도에 지그재그 장애물 ────────────────────────
    for xp, yp in [(-0.65, 4.0), (0.65, 7.5), (-0.65, 10.0)]:
        world.add_cylinder(
            radius=0.22, half_length=0.85,
            position=(xp, yp, 2.35),   # 복도 바닥 z=1.5, 기둥 중심 z=2.35
            static=True,
            material=f3d.Material(color=(0.50, 0.60, 0.85), roughness=0.4),
        )

    # ── 원뿔 경고 표지: 오른쪽 막힘 분기 입구 ──────────────────────
    for cx in (-1.8, 0.0, 1.8):
        world.add_cone(
            radius=0.18, height=0.55,
            position=(cx + 5.0, 13.8, 1.775),   # 분기 바닥 z=1.5, 원뿔 중심 z=1.775
            static=True,
            material=f3d.Material(color=(1.0, 0.35, 0.0), roughness=0.4),
        )

    # ── 오른쪽 분기 끝 막힘 벽 ────────────────────────────────────
    world.add_static_box(
        size=(6.0, 0.3, 3.0),
        position=(5.0, 15.7, 2.0),
        material=f3d.Material(color=(0.9, 0.2, 0.2), roughness=0.6),
        name="dead_wall",
    )

    # ── 경계 벽 (복도 양쪽) ───────────────────────────────────────
    for side in [-1, 1]:
        world.add_static_box(
            size=(0.3, 14.0, 2.0),
            position=(side * 1.7, 6.5, 1.5),
            material=f3d.Material(color=(0.40, 0.40, 0.55), roughness=0.5),
        )

    # ── 회전 장애물 (허들) ────────────────────────────────────────
    for i, y_pos in enumerate([3.5, 7.0, 10.5]):
        world.add_static_box(
            size=(2.5, 0.3, 0.6),
            position=(0.0, y_pos, 1.3),
            material=f3d.Material(color=(0.9, 0.6, 0.1), roughness=0.4),
            name=f"hurdle_{i}",
        )

    # ── 움직이는 플랫폼 (스프링 공 함정) ─────────────────────────
    for xi, x_off in enumerate([-1.8, 0.0, 1.8]):
        world.add_box(
            size=(1.0, 1.0, 0.25),
            position=(x_off, 12.0, 2.0),
            mass=3.0,
            restitution=0.6,
            material=f3d.Material(color=(0.8, 0.3, 0.7), roughness=0.3),
            name=f"bumper_{xi}",
        )
    # 스프링으로 천장에 연결
    ceiling_anchor = world.add_static_box(
        size=(6.0, 2.0, 0.2), position=(0.0, 12.0, 5.0)
    )
    for name in ["bumper_0", "bumper_1", "bumper_2"]:
        bumper = world.get_body(name)
        world.add_joint(
            "spring", bumper, ceiling_anchor,
            stiffness=60.0, damping=4.0, rest_length=3.2,
        )

    # ── 낙하 함정 구역 (바닥 없는 구간) ──────────────────────────
    # y=15.5 ~ 17.5 사이는 바닥이 없다 (점프 구간)

    # ── 경사면(wedge) 점프대: 높은 플랫폼 위에서 더 위로 ─────────
    # 높은 플랫폼 상면 z=2.5; wedge 아랫면 z=2.5, 윗면(+y 방향) z=3.2
    world.add_wedge(
        size=(2.5, 2.0, 0.7),
        position=(0.0, 20.0, 2.85),
        static=True,
        material=f3d.Material(color=(0.25, 0.75, 0.55), roughness=0.45),
    )

    # ── 볼록 바위: 최종 구역에서 굴러다니는 장애물 ───────────────
    _rng = np.random.default_rng(42)
    _pts = _rng.standard_normal((18, 3))
    _pts /= np.linalg.norm(_pts, axis=1, keepdims=True)
    world.add_convex(
        _pts * np.array([0.38, 0.38, 0.32]),
        position=(1.5, 27.0, 5.5),
        mass=2.5,
        friction=0.65,
        material=f3d.Material(color=(0.55, 0.45, 0.35), roughness=0.9),
    )

    # ── 골인 트리거 존 ────────────────────────────────────────────
    goal_zone = world.add_trigger_zone(
        position=(0.0, 28.0, 5.5),
        size=(5.0, 3.0, 3.0),
        name="goal",
    )

    @goal_zone.on_enter
    def on_goal(body: f3d.Body) -> None:
        if body is ball and state["phase"] == "playing":
            elapsed = time.perf_counter() - state["start_time"]
            state["phase"]    = "win"
            state["win_time"] = elapsed
            state["score"]   += max(0, int(3000 - elapsed * 40))
            if state["best_time"] is None or elapsed < state["best_time"]:
                state["best_time"] = elapsed

    # ── 시각적 골인 마커 (발광하는 녹색 구) ─────────────────────
    world.add_sphere(
        radius=0.8,
        position=(0.0, 28.0, 6.5),
        mass=1.0,
        static=True,
        material=f3d.Material(color=(0.1, 1.0, 0.3), roughness=0.1, emissive=1.2),
        name="goal_marker",
    )

    # ── 플레이어 공 ───────────────────────────────────────────────
    ball = world.add_sphere(
        radius=BALL_RADIUS,
        position=RESPAWN_POS,
        mass=1.5,
        restitution=0.25,
        friction=0.8,
        material=f3d.Material(color=(1.0, 0.85, 0.1), roughness=0.3, metallic=0.5),
        name="player_ball",
    )
    ball.linear_damping  = 0.35
    ball.angular_damping = 0.6

    # ── 카메라 초기 위치 ─────────────────────────────────────────
    world.set_camera(position=(0, -8, 10), target=(0, 5, 2), fov_deg=55)

    # ── 시작 시간 리셋 ────────────────────────────────────────────
    state["phase"]      = "playing"
    state["start_time"] = time.perf_counter()
    state["win_time"]   = None


# ─────────────────────────── on_start ─────────────────────────────
@app.on_start
def setup(world: f3d.World) -> None:
    build_level(world)


# ─────────────────────────── on_update ────────────────────────────
@app.on_update
def update(world: f3d.World, dt: float, inp: f3d.Input) -> None:
    global ball

    # R: 재시작
    if inp.key_pressed(f3d.Key.R):
        build_level(world)
        return

    # ESC: 종료
    if inp.key_pressed(f3d.Key.ESCAPE):
        sys.exit(0)

    if state["phase"] == "win":
        return   # 이긴 상태 — 입력 무시

    bpos = ball.position

    # 낙하 감지 (z < -3)
    if bpos[2] < -3.0 and state["phase"] == "playing":
        state["lives"] -= 1
        if state["lives"] <= 0:
            state["phase"] = "dead"
        else:
            # 리스폰
            world.teleport(ball, RESPAWN_POS)
            ball.set_velocity((0.0, 0.0, 0.0))
            ball.set_angular_velocity((0.0, 0.0, 0.0))
        return

    if state["phase"] == "dead":
        return

    # ── 공 조작 ─────────────────────────────────────────────────
    vx, vy = ball.velocity[0], ball.velocity[1]
    speed_h = math.hypot(vx, vy)

    # 가속 방향
    fx, fy = 0.0, 0.0
    if inp.key_held(f3d.Key.W) or inp.key_held(f3d.Key.UP):
        fy += FORCE * dt
    if inp.key_held(f3d.Key.S) or inp.key_held(f3d.Key.DOWN):
        fy -= FORCE * dt
    if inp.key_held(f3d.Key.A) or inp.key_held(f3d.Key.LEFT):
        fx -= FORCE * dt
    if inp.key_held(f3d.Key.D) or inp.key_held(f3d.Key.RIGHT):
        fx += FORCE * dt

    # 최대 속도 제한
    if speed_h > MAX_SPEED and (fx * vx + fy * vy) > 0:
        ratio = MAX_SPEED / (speed_h + 1e-9)
        fx *= ratio
        fy *= ratio

    if fx != 0.0 or fy != 0.0:
        world.apply_impulse(ball, (fx, fy, 0.0))

    # 점프 (지면 근처일 때만)
    is_near_ground = bpos[2] < (BALL_RADIUS + 0.8)
    if inp.key_pressed(f3d.Key.SPACE) and is_near_ground:
        world.apply_impulse(ball, (0.0, 0.0, JUMP_IMPULSE))

    # ── 카메라 — 공 추적 ────────────────────────────────────────
    cx   = bpos[0] * 0.4
    cy   = bpos[1] - 9.0
    cz   = bpos[2] + 8.0
    world.set_camera(
        position=(cx, cy, cz),
        target=(bpos[0], bpos[1] + 2.0, bpos[2]),
        fov_deg=55,
    )


# ─────────────────────────── on_render ────────────────────────────
@app.on_render
def render(world: f3d.World, viewer) -> None:
    W, H = 1100, 700

    # ── 상태 오버레이 ────────────────────────────────────────────
    elapsed = time.perf_counter() - state["start_time"]

    if state["phase"] == "playing":
        viewer.draw_text(
            f"⏱  {elapsed:.1f}s",
            x=20, y=18, size=22, color=(1.0, 1.0, 0.5),
        )
        viewer.draw_text(
            f"❤  Lives: {state['lives']}",
            x=20, y=46, size=20, color=(1.0, 0.4, 0.4),
        )
        viewer.draw_text(
            f"⭐ Score: {state['score']}",
            x=20, y=72, size=20, color=(0.5, 1.0, 0.6),
        )

        # 조작 힌트 (하단)
        viewer.draw_text(
            "WASD / 방향키 — 이동  │  SPACE — 점프  │  R — 재시작",
            x=W // 2, y=H - 30, size=16,
            color=(0.8, 0.8, 0.8), anchor="midbottom",
        )

        # 골인 지점 안내
        bpos  = ball.position
        dist  = math.hypot(bpos[0], bpos[1] - 28.0)
        viewer.draw_text(
            f"🏁 Goal: {dist:.0f}m",
            x=W - 20, y=18, size=19,
            color=(0.4, 1.0, 0.5), anchor="topright",
        )
        if state["best_time"] is not None:
            viewer.draw_text(
                f"🥇 Best: {state['best_time']:.1f}s",
                x=W - 20, y=45, size=17,
                color=(1.0, 0.85, 0.2), anchor="topright",
            )

    elif state["phase"] == "win":
        # 승리 화면
        viewer.draw_text(
            "🎉 GOAL!  클리어! 🎉",
            x=W // 2, y=H // 2 - 85, size=40,
            color=(0.2, 1.0, 0.4), anchor="midtop",
        )
        viewer.draw_text(
            f"클리어 시간: {state['win_time']:.2f}초",
            x=W // 2, y=H // 2 - 25, size=26,
            color=(1.0, 1.0, 0.5), anchor="midtop",
        )
        viewer.draw_text(
            f"획득 점수: {state['score']}점",
            x=W // 2, y=H // 2 + 15, size=26,
            color=(0.5, 1.0, 0.8), anchor="midtop",
        )
        viewer.draw_text(
            "[ R ] 재도전  │  [ ESC ] 종료",
            x=W // 2, y=H // 2 + 60, size=20,
            color=(0.8, 0.8, 0.8), anchor="midtop",
        )

    elif state["phase"] == "dead":
        # 게임오버 화면
        viewer.draw_text(
            "💀 GAME OVER",
            x=W // 2, y=H // 2 - 80, size=40,
            color=(1.0, 0.25, 0.2), anchor="midtop",
        )
        viewer.draw_text(
            f"최종 점수: {state['score']}점",
            x=W // 2, y=H // 2 - 20, size=26,
            color=(1.0, 0.8, 0.3), anchor="midtop",
        )
        viewer.draw_text(
            "[ R ] 재시작  │  [ ESC ] 종료",
            x=W // 2, y=H // 2 + 30, size=20,
            color=(0.8, 0.8, 0.8), anchor="midtop",
        )


# ─────────────────────────── 실행 ─────────────────────────────────
if __name__ == "__main__":
    print(__doc__)
    app.run()