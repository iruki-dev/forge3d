"""
=============================================================
  🎮  BALL ROLL MINI-GAME  (forge3d 활용)
=============================================================
  WASD / 방향키  : 공에 힘을 가합니다
  SPACE          : 공을 위로 튀깁니다
  R              : 레벨 재시작
  ESC            : 종료

  목표 : 빨간 공을 초록 목표 구역에 굴려 넣으세요!
         장애물을 피해 30초 안에 3개의 스테이지를 클리어!

설치:
    pip install "pyforge3d[render]"

실행:
    python ball_roll_game.py
=============================================================
"""

import random
import forge3d as f3d

# ─── 게임 상태 ───────────────────────────────────────────
class GameState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.score        = 0
        self.stage        = 1
        self.time_left    = 30.0
        self.goal_reached = False
        self.game_over    = False
        self.win          = False
        self.msg_timer    = 0.0   # 일시적 메시지 표시 타이머
        self.msg          = ""

gs = GameState()

# ─── 스테이지 레이아웃 정의 ──────────────────────────────
STAGES = [
    # stage 1 : 단순 평지, 목표까지 직선
    {
        "ball_pos"   : (0.0, -6.0, 1.0),
        "goal_pos"   : (0.0,  6.0, 0.3),
        "obstacles"  : [
            {"pos": (0.0,  0.0, 0.5), "size": (3.0, 0.4, 1.0)},
            {"pos": (-2.5, 3.0, 0.5), "size": (0.4, 3.0, 1.0)},
            {"pos": ( 2.5, 3.0, 0.5), "size": (0.4, 3.0, 1.0)},
        ],
        "bumpers"    : [],
    },
    # stage 2 : 좁은 통로 + 튀는 범퍼
    {
        "ball_pos"   : (-5.0, -5.0, 1.0),
        "goal_pos"   : ( 5.0,  5.0, 0.3),
        "obstacles"  : [
            {"pos": (0.0, -2.0, 0.5), "size": (6.0, 0.4, 1.0)},
            {"pos": (0.0,  2.0, 0.5), "size": (6.0, 0.4, 1.0)},
            {"pos": (2.0,  0.0, 0.5), "size": (0.4, 6.0, 1.0)},
        ],
        "bumpers"    : [
            {"pos": (-2.0, 1.0, 0.5)},
            {"pos": ( 3.0,-1.0, 0.5)},
        ],
    },
    # stage 3 : 미로형
    {
        "ball_pos"   : (-6.0, -6.0, 1.0),
        "goal_pos"   : ( 6.0,  6.0, 0.3),
        "obstacles"  : [
            {"pos": ( 0.0, -4.0, 0.5), "size": (8.0, 0.4, 1.2)},
            {"pos": (-4.0,  0.0, 0.5), "size": (0.4, 8.0, 1.2)},
            {"pos": ( 4.0,  2.0, 0.5), "size": (0.4, 6.0, 1.2)},
            {"pos": ( 0.0,  4.0, 0.5), "size": (8.0, 0.4, 1.2)},
        ],
        "bumpers"    : [
            {"pos": (-2.0,-2.0, 0.5)},
            {"pos": ( 2.0, 0.0, 0.5)},
            {"pos": (-3.0, 3.0, 0.5)},
        ],
    },
]

# ─── 월드 오브젝트 핸들 ──────────────────────────────────
ball       = None
goal_zone  = None
walls      = []
bumpers_b  = []

# ─── App 생성 ────────────────────────────────────────────
app = f3d.App("🎮 Ball Roll Mini-Game", width=1280, height=720, fps=60)

def build_stage(world: f3d.World, stage_idx: int):
    """현재 스테이지 씬 구성."""
    global ball, goal_zone, walls, bumpers_b

    world.clear(keep_statics=False)
    walls.clear()
    bumpers_b.clear()

    cfg = STAGES[stage_idx]

    # 바닥
    world.add_ground(
        material=f3d.Material(color=(0.15, 0.15, 0.25), roughness=0.9),
        size=(40.0, 40.0, 0.2),
    )

    # 외곽 벽
    for pos, sz in [
        ((0,  8.2, 0.5), (16.4, 0.4, 1.5)),
        ((0, -8.2, 0.5), (16.4, 0.4, 1.5)),
        (( 8.2, 0, 0.5), (0.4, 16.4, 1.5)),
        ((-8.2, 0, 0.5), (0.4, 16.4, 1.5)),
    ]:
        w = world.add_box(
            size=sz, position=pos,
            static=True,
            material=f3d.Material(color=(0.3, 0.3, 0.5), roughness=0.8),
        )
        walls.append(w)

    # 장애물 (static box)
    for obs in cfg["obstacles"]:
        w = world.add_box(
            size=obs["size"],
            position=obs["pos"],
            static=True,
            material=f3d.Material(color=(0.7, 0.4, 0.1), roughness=0.6),
        )
        walls.append(w)

    # 범퍼 (탄성이 높은 구)
    for bmp in cfg["bumpers"]:
        b = world.add_sphere(
            radius=0.5,
            position=bmp["pos"],
            static=True,
            restitution=1.6,
            material=f3d.Material(color=(0.9, 0.1, 0.9), roughness=0.2),
        )
        bumpers_b.append(b)

    # 플레이어 공
    ball = world.add_sphere(
        radius=0.4,
        position=cfg["ball_pos"],
        mass=1.0,
        restitution=0.5,
        friction=0.4,
        material=f3d.Material(color=(0.9, 0.1, 0.1), roughness=0.3),
        name="ball",
    )

    # 목표 트리거 존 (시각화용 static sphere + trigger zone)
    world.add_sphere(
        radius=0.8,
        position=cfg["goal_pos"],
        static=True,
        restitution=0.0,
        friction=1.0,
        material=f3d.Material(color=(0.1, 0.9, 0.1), roughness=0.5, metallic=0.0),
        name="goal_marker",
    )

    goal_zone = world.add_trigger_zone(
        position=cfg["goal_pos"],
        size=(1.8, 1.8, 1.8),
        name="goal",
    )

    @goal_zone.on_enter
    def on_goal(body: f3d.Body):
        if body.name == "ball" and not gs.goal_reached and not gs.game_over:
            gs.goal_reached = True
            gs.score       += 1
            gs.msg          = f"🎉 GOAL!  Score: {gs.score}"
            gs.msg_timer    = 2.5

    # 카메라 위치 설정
    world.set_camera(
        position=(0, -18, 20),
        target=(0, 0, 0),
        fov_deg=55,
    )


@app.on_start
def setup(world: f3d.World):
    gs.reset()
    build_stage(world, gs.stage - 1)


@app.on_update
def update(world: f3d.World, dt: float, inp: f3d.Input):
    global ball

    if gs.game_over or gs.win:
        # R 키로 완전 재시작
        if inp.key_pressed(f3d.Key.R):
            gs.reset()
            build_stage(world, gs.stage - 1)
        return

    # ── 타이머 ──────────────────────────────
    gs.time_left -= dt
    if gs.msg_timer > 0:
        gs.msg_timer -= dt

    if gs.time_left <= 0:
        gs.time_left = 0
        gs.game_over = True
        gs.msg       = "💀 TIME OVER!  Press R to restart"
        return

    # ── 골 도달 → 다음 스테이지 전환 ────────
    if gs.goal_reached:
        gs.goal_reached = False
        if gs.stage >= len(STAGES):
            gs.win = True
            gs.msg = "🏆 YOU WIN!  ALL STAGES CLEARED!  Press R"
        else:
            gs.stage     += 1
            gs.time_left  = 30.0
            build_stage(world, gs.stage - 1)
        return

    # ── 공 입력 ─────────────────────────────
    FORCE = 18.0
    fx, fy = 0.0, 0.0

    if inp.key_held(f3d.Key.W) or inp.key_held(f3d.Key.UP):
        fy =  FORCE
    if inp.key_held(f3d.Key.S) or inp.key_held(f3d.Key.DOWN):
        fy = -FORCE
    if inp.key_held(f3d.Key.A) or inp.key_held(f3d.Key.LEFT):
        fx = -FORCE
    if inp.key_held(f3d.Key.D) or inp.key_held(f3d.Key.RIGHT):
        fx =  FORCE

    if fx != 0 or fy != 0:
        world.apply_impulse(ball, (fx * dt, fy * dt, 0.0))

    if inp.key_pressed(f3d.Key.SPACE):
        world.apply_impulse(ball, (0.0, 0.0, 6.0))

    # R 키로 현재 스테이지 재시작
    if inp.key_pressed(f3d.Key.R):
        gs.time_left = 30.0
        build_stage(world, gs.stage - 1)

    # 공이 맵 밖으로 떨어지면 리셋
    if ball.position[2] < -3.0:
        gs.time_left = max(0, gs.time_left - 5.0)
        gs.msg       = "😵 Out of bounds! -5s"
        gs.msg_timer = 1.5
        build_stage(world, gs.stage - 1)


@app.on_render
def render(world: f3d.World, viewer: f3d.Viewer):
    # HUD
    stage_txt  = f"Stage {gs.stage} / {len(STAGES)}"
    time_color = (1.0, 0.2, 0.2) if gs.time_left < 10 else (1.0, 1.0, 1.0)
    time_txt   = f"Time : {gs.time_left:05.1f}s"
    score_txt  = f"Score: {gs.score}"

    viewer.draw_text(stage_txt,  x=20,  y=20,  size=22, color=(0.6, 1.0, 0.6))
    viewer.draw_text(time_txt,   x=20,  y=50,  size=22, color=time_color)
    viewer.draw_text(score_txt,  x=20,  y=80,  size=22, color=(1.0, 0.9, 0.3))

    ctrl_hint = "WASD/↑↓←→: Move   SPACE: Jump   R: Restart"
    viewer.draw_text(ctrl_hint, x=20, y=-1, size=16, color=(0.7, 0.7, 0.7),
                     anchor="bottom_left")

    if gs.msg_timer > 0 or gs.game_over or gs.win:
        viewer.draw_text(gs.msg, x=0, y=0, size=28,
                         color=(1.0, 1.0, 0.2), anchor="center")


if __name__ == "__main__":
    app.run()