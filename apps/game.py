"""
🎮 DODGE BLITZ — forge3d 미니게임
======================================
• WASD / 방향키로 플레이어(파란 캡슐) 이동
• 하늘에서 날아오는 빨간 볼을 피하세요
• 골드 존(노란 박스)에 들어가면 +10점, 보너스 볼이 사라짐
• 볼에 맞으면 게임 오버

forge3d API 사용:
  - App (on_start / on_update / on_render 게임 루프)
  - CharacterController (move / jump / is_grounded)
  - add_trigger_zone (on_enter 이벤트)
  - on_collision_begin (충돌 감지)
  - overlap_sphere (폭발 범위 쿼리)
  - add_sphere / add_box / add_static_box (오브젝트)
  - Material (색상 지정)
  - viewer.draw_text (HUD 텍스트)
  - world.teleport (리스폰)
  - world.remove (다이나믹 오브젝트 제거)
"""

import contextlib
import math
import random

import forge3d as f3d

# ─── 게임 상태 ────────────────────────────────────────────────
state = {
    "score": 0,
    "lives": 3,
    "alive": True,
    "spawn_timer": 0.0,
    "spawn_interval": 2.5,  # 초마다 볼 하나 소환
    "balls": [],  # 날아오는 볼 목록
    "gold_zones": [],  # 활성 골드 존 목록
    "gold_timer": 0.0,
    "gold_interval": 5.0,  # 5초마다 골드 존 갱신
    "difficulty": 1.0,
    "wave": 1,
    "wave_timer": 0.0,
    "wave_interval": 15.0,  # 15초마다 난이도 상승
    "hit_flash": 0.0,  # 피격 시 화면 플래시
}

ARENA_HALF = 8.0  # 경기장 반지름 (m)

app = f3d.App("🎮 Dodge Blitz — forge3d", width=1280, height=720, fps=60)
cc = None  # CharacterController


def random_spawn_pos():
    """경기장 위 랜덤 위치에서 소환."""
    angle = random.uniform(0, 2 * math.pi)
    r = random.uniform(ARENA_HALF * 0.3, ARENA_HALF * 0.9)
    x = math.cos(angle) * r
    y = math.sin(angle) * r
    z = random.uniform(10.0, 18.0)
    return (x, y, z)


def random_arena_pos(height=0.5):
    """경기장 바닥 위 랜덤 위치."""
    x = random.uniform(-ARENA_HALF * 0.7, ARENA_HALF * 0.7)
    y = random.uniform(-ARENA_HALF * 0.7, ARENA_HALF * 0.7)
    return (x, y, height)


# ─── on_start ──────────────────────────────────────────────────
@app.on_start
def setup(world: f3d.World) -> None:
    global cc

    # 바닥
    world.add_ground(
        material=f3d.Material(color=(0.18, 0.22, 0.28), roughness=0.9),
        size=(ARENA_HALF * 2 + 4, ARENA_HALF * 2 + 4, 0.3),
    )

    # 경기장 벽 (4면)
    wall_mat = f3d.Material(color=(0.3, 0.35, 0.45), roughness=0.7)
    hw = ARENA_HALF
    th = 0.5
    world.add_static_box(
        size=(hw * 2, th, 3), position=(0, hw, 1.5), material=wall_mat, name="wall_n"
    )
    world.add_static_box(
        size=(hw * 2, th, 3), position=(0, -hw, 1.5), material=wall_mat, name="wall_s"
    )
    world.add_static_box(
        size=(th, hw * 2, 3), position=(hw, 0, 1.5), material=wall_mat, name="wall_e"
    )
    world.add_static_box(
        size=(th, hw * 2, 3), position=(-hw, 0, 1.5), material=wall_mat, name="wall_w"
    )

    # 장애물 박스 4개
    obs_mat = f3d.Material(color=(0.4, 0.25, 0.1), roughness=0.8)
    for pos in [(3, 3, 0.75), (-3, 3, 0.75), (3, -3, 0.75), (-3, -3, 0.75)]:
        world.add_static_box(size=(1.5, 1.5, 1.5), position=pos, material=obs_mat, name="obstacle")

    # 캐릭터 컨트롤러
    cc = world.add_character(
        position=(0, 0, 2),
        height=1.6,
        radius=0.35,
        mass=70.0,
        name="player",
    )

    # 카메라 (내려보는 쿼터뷰)
    world.set_camera(
        position=(0, -20, 22),
        target=(0, 0, 0),
        fov_deg=55,
    )

    # 첫 골드 존 생성
    _spawn_gold_zones(world)

    # 충돌 이벤트: 볼이 플레이어에 닿으면
    @world.on_collision_begin
    def on_hit(event: f3d.CollisionEvent):
        a, b = event.body_a.name, event.body_b.name
        if ("enemy_ball" in (a, b)) and ("player" in (a, b)):
            _take_hit(world, event)


def _spawn_gold_zones(world: f3d.World):
    """골드 존(트리거) 1~2개 랜덤 생성."""
    # 기존 골드 존 제거
    for gz in state["gold_zones"]:
        try:
            gz["zone"].enabled = False
            world.remove(gz["body"])
        except Exception:
            pass
    state["gold_zones"].clear()

    count = random.randint(1, 2)
    for _ in range(count):
        pos = random_arena_pos(0.3)
        # 시각적 표시용 얇은 박스
        body = world.add_static_box(
            size=(1.8, 1.8, 0.15),
            position=pos,
            material=f3d.Material(color=(1.0, 0.85, 0.1), roughness=0.3),
            name="gold_zone_body",
        )
        # 트리거 존
        zone = world.add_trigger_zone(
            position=pos,
            size=(1.8, 1.8, 1.5),
            name="gold_trigger",
        )

        gz_ref = {"body": body, "zone": zone, "collected": False}
        state["gold_zones"].append(gz_ref)

        @zone.on_enter
        def on_gold(entering_body: f3d.Body, _gz=gz_ref):
            if entering_body.name == "player" and not _gz["collected"]:
                _gz["collected"] = True
                state["score"] += 10
                # 화면에 있는 볼 1개 제거 (보너스)
                if state["balls"]:
                    old = state["balls"].pop(0)
                    with contextlib.suppress(Exception):
                        world.remove(old)


def _take_hit(world: f3d.World, event):
    """플레이어 피격 처리."""
    if not state["alive"]:
        return
    state["lives"] -= 1
    state["hit_flash"] = 0.4
    if state["lives"] <= 0:
        state["alive"] = False
    else:
        # 중앙으로 텔레포트
        world.teleport(cc.body, (0, 0, 2))


# ─── on_update ─────────────────────────────────────────────────
@app.on_update
def update(world: f3d.World, dt: float, inp: f3d.Input) -> None:
    if not state["alive"]:
        if inp.key_pressed(f3d.Key.ENTER):
            _restart(world)
        return

    # ── 플레이어 이동 ──
    dx, dy = 0.0, 0.0
    if inp.any_key_held(f3d.Key.W, f3d.Key.UP):
        dy = 1.0
    if inp.any_key_held(f3d.Key.S, f3d.Key.DOWN):
        dy = -1.0
    if inp.any_key_held(f3d.Key.A, f3d.Key.LEFT):
        dx = -1.0
    if inp.any_key_held(f3d.Key.D, f3d.Key.RIGHT):
        dx = 1.0

    speed = 6.0
    cc.move(direction=(dx, dy, 0), speed=speed, dt=dt)

    if inp.key_pressed(f3d.Key.SPACE) and cc.is_grounded:
        cc.jump(impulse=7.0)

    # ── 볼 소환 타이머 ──
    state["spawn_timer"] += dt
    interval = state["spawn_interval"] / state["difficulty"]
    if state["spawn_timer"] >= interval:
        state["spawn_timer"] = 0.0
        _spawn_ball(world)

    # ── 볼 유도 (플레이어를 향해 힘을 가함) ──
    px, py, pz = cc.body.position
    dead_balls = []
    for ball in state["balls"]:
        try:
            bx, by, bz = ball.position
            # 바닥 아래로 떨어진 볼 제거
            if bz < -2.0:
                dead_balls.append(ball)
                continue
            # 플레이어 쪽으로 약한 추적력
            tx = px - bx
            ty = py - by
            dist = math.sqrt(tx**2 + ty**2) + 0.001
            strength = 6.0 * state["difficulty"]
            world.apply_impulse(ball, (tx / dist * strength * dt, ty / dist * strength * dt, 0))
        except Exception:
            dead_balls.append(ball)

    for b in dead_balls:
        state["balls"].remove(b)
        with contextlib.suppress(Exception):
            world.remove(b)

    # ── 골드 존 갱신 타이머 ──
    state["gold_timer"] += dt
    if state["gold_timer"] >= state["gold_interval"]:
        state["gold_timer"] = 0.0
        _spawn_gold_zones(world)

    # ── 파동(웨이브) 타이머 ──
    state["wave_timer"] += dt
    if state["wave_timer"] >= state["wave_interval"]:
        state["wave_timer"] = 0.0
        state["wave"] += 1
        state["difficulty"] = 1.0 + (state["wave"] - 1) * 0.4
        state["spawn_interval"] = max(0.6, 2.5 - (state["wave"] - 1) * 0.25)

    # ── 생존 점수 ──
    state["score"] += dt * 2 * state["difficulty"]

    # ── 플래시 감소 ──
    if state["hit_flash"] > 0:
        state["hit_flash"] = max(0, state["hit_flash"] - dt)


def _spawn_ball(world: f3d.World):
    """적 볼 소환."""
    pos = random_spawn_pos()
    # 웨이브마다 볼 크기 약간 변화
    radius = random.uniform(0.3, 0.5 + state["wave"] * 0.05)
    radius = min(radius, 0.8)
    ball = world.add_sphere(
        radius=radius,
        position=pos,
        mass=2.0,
        restitution=0.4,
        friction=0.3,
        material=f3d.Material(color=(1.0, 0.15, 0.1), roughness=0.4),
        name="enemy_ball",
    )
    # 초기 속도: 플레이어 방향으로
    px, py, _ = cc.body.position
    tx = px - pos[0]
    ty = py - pos[1]
    tz = -pos[2] * 0.6
    dist = math.sqrt(tx**2 + ty**2 + tz**2) + 0.001
    speed = random.uniform(5.0, 8.0) * state["difficulty"]
    world.apply_impulse(ball, (tx / dist * speed * 2, ty / dist * speed * 2, tz / dist * speed * 2))
    state["balls"].append(ball)


def _restart(world: f3d.World):
    """게임 재시작."""
    # 볼 모두 제거
    for b in state["balls"]:
        with contextlib.suppress(Exception):
            world.remove(b)
    state["balls"].clear()

    # 상태 초기화
    state["score"] = 0
    state["lives"] = 3
    state["alive"] = True
    state["spawn_timer"] = 0.0
    state["spawn_interval"] = 2.5
    state["difficulty"] = 1.0
    state["wave"] = 1
    state["wave_timer"] = 0.0
    state["hit_flash"] = 0.0
    state["gold_timer"] = 0.0

    world.teleport(cc.body, (0, 0, 2))
    _spawn_gold_zones(world)


# ─── on_render (HUD) ───────────────────────────────────────────
@app.on_render
def render(world: f3d.World, viewer: f3d.Viewer) -> None:
    # 피격 플래시 오버레이
    if state["hit_flash"] > 0:
        viewer.draw_text(
            "⚡ HIT! ⚡",
            x=640,
            y=250,
            size=36,
            color=(1.0, 0.2, 0.2),
            anchor="center",
        )

    if not state["alive"]:
        # 게임 오버 화면
        viewer.draw_text(
            "💀  GAME OVER  💀",
            x=640,
            y=300,
            size=48,
            color=(1.0, 0.31, 0.31),
            anchor="center",
        )
        viewer.draw_text(
            f"최종 점수:  {int(state['score'])}",
            x=640,
            y=370,
            size=32,
            color=(1.0, 0.86, 0.39),
            anchor="center",
        )
        viewer.draw_text(
            "[ ENTER ] 다시 시작",
            x=640,
            y=430,
            size=24,
            color=(0.78, 0.78, 1.0),
            anchor="center",
        )
        return

    # 점수 & 목숨
    hearts = "❤️ " * state["lives"] + "🖤 " * (3 - state["lives"])
    viewer.draw_text(
        f"점수  {int(state['score'])}",
        x=20,
        y=20,
        size=28,
        color=(1.0, 0.9, 0.3),
        anchor="top-left",
    )
    viewer.draw_text(
        f"{hearts}",
        x=20,
        y=60,
        size=22,
        color=(1.0, 0.4, 0.4),
        anchor="top-left",
    )
    viewer.draw_text(
        f"Wave {state['wave']}",
        x=1260,
        y=20,
        size=22,
        color=(0.6, 0.86, 1.0),
        anchor="top-right",
    )
    viewer.draw_text(
        f"볼  {len(state['balls'])}",
        x=1260,
        y=52,
        size=18,
        color=(1.0, 0.63, 0.3),
        anchor="top-right",
    )

    # 조작법
    viewer.draw_text(
        "WASD / 방향키 이동   SPACE 점프",
        x=640,
        y=700,
        size=16,
        color=(0.7, 0.7, 0.7),
        anchor="center",
    )
    viewer.draw_text(
        "🟡 노란 존 = +10점  🔴 빨간 볼 = 피격",
        x=640,
        y=718,
        size=14,
        color=(0.65, 0.65, 0.65),
        anchor="center",
    )


# ─── 실행 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🎮 Dodge Blitz 시작!")
    print("   WASD / 방향키: 이동  |  SPACE: 점프")
    print("   노란 타일을 밟으면 +10점, 볼 1개 소멸!")
    print("   빨간 볼에 맞으면 목숨 -1")
    app.run()
