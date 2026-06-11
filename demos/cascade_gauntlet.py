"""demos/cascade_gauntlet.py — pyforge3d 종합 기능 쇼케이스

세 개의 장면을 통해 라이브러리의 주요 기능을 최대한 활용합니다.

활용 기능
---------
 물리   : World, Body (box/sphere/capsule), 중력, 마찰, 반발
 형상   : add_box / add_sphere / add_capsule / add_terrain (heightfield)
 재질   : Material 프리셋·RGB·PBR (metallic, roughness)
 조인트 : hinge, spring, distance, ball, fixed (add_joint / remove_joint)
 구속   : weld / release
 이벤트 : on_collision_begin, on_collision_stay, add_collision_handler,
          add_trigger_zone (on_enter / on_exit)
 충돌레이어 : CollisionLayer (PLAYER, ENEMY, BULLET, DEBRIS, DEFAULT)
 힘/충격 : apply_force, apply_torque, apply_impulse, teleport
 슬리핑  : body.is_sleeping
 직렬화  : World.save / World.load, StateRecorder
 렌더링  : HQRenderer, SceneSnapshot, set_camera
 카메라  : OrbitCamera

장면 구성
---------
  장면 1 — "핀볼 아레나"
      봄버(spring joint) 범퍼, 힌지 패들, 트리거존 득점,
      충돌 이벤트로 히트 카운팅, CollisionLayer 분리

  장면 2 — "철거의 탑"
      distance joint 쇄도 공, 벽 weld→release, 캡슐 체인,
      충돌 핸들러로 타격 감지, 직렬화(save/load) 데모

  장면 3 — "지형 슬라이드"
      heightfield terrain, 다양한 반발·마찰 물체,
      StateRecorder 기록, PBR 재질 혼합

사용법
------
    python demos/cascade_gauntlet.py                   # 기본 (480×320, samples=1)
    python demos/cascade_gauntlet.py --hq              # 640×400, samples=2
    python demos/cascade_gauntlet.py --ultra           # 800×500, samples=4
    python demos/cascade_gauntlet.py --scene 1        # 특정 장면만
    python demos/cascade_gauntlet.py -o my_demo.mp4   # 출력 파일명 지정
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import tempfile
from pathlib import Path

import numpy as np

# 프로젝트 루트를 경로에 추가 (설치 없이 실행 가능하도록)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import imageio
import forge3d as f3d
from forge3d.collision.layers import CollisionLayer
from forge3d.io.world_snapshot import StateRecorder
from forge3d.render.hq.renderer import HQRenderer

# ── 전역 설정 ─────────────────────────────────────────────────────────────────

FPS = 24
SUBSTEPS = 4
PHYS_DT = 1.0 / (FPS * SUBSTEPS)  # ≈ 1/96 s


def _step(world: f3d.World, n: int = SUBSTEPS) -> None:
    for _ in range(n):
        world.step(PHYS_DT)


def _warmup(world: f3d.World, seconds: float) -> None:
    for _ in range(int(seconds / PHYS_DT)):
        world.step(PHYS_DT)


def _progress(i: int, total: int, label: str) -> None:
    w = 30
    f = int(w * i / total)
    bar = "█" * f + "░" * (w - f)
    print(f"\r  {label}: [{bar}] {100*i/total:4.0f}%", end="", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# 장면 1 — 핀볼 아레나
# ══════════════════════════════════════════════════════════════════════════════

def scene1_pinball_arena(renderer: HQRenderer, n_frames: int = 192) -> list[np.ndarray]:
    """Spring bumper, hinge paddle, trigger zone, collision layers, collision events."""

    print("  [장면 1/3] 핀볼 아레나 …")

    world = f3d.World(gravity=(0, 0, -9.81))

    # ── 바닥 및 벽 ───────────────────────────────────────────────────────────
    world.add_ground(material=f3d.Material(color=(0.15, 0.12, 0.25), roughness=0.8))

    ARENA_W, ARENA_D, WALL_H = 6.0, 8.0, 2.5
    wall_mat = f3d.Material(color=(0.35, 0.35, 0.45), roughness=0.6)
    for px, py, sx, sy in [
        (0,          ARENA_D/2,  ARENA_W, 0.3),
        (0,         -ARENA_D/2,  ARENA_W, 0.3),
        ( ARENA_W/2, 0,          0.3,     ARENA_D),
        (-ARENA_W/2, 0,          0.3,     ARENA_D),
    ]:
        world._physics.add_static_box(
            size=(sx, sy, WALL_H),
            position=(px, py, WALL_H / 2),
            material=wall_mat._material_id(),
            friction=0.3, restitution=0.6,
        )
        world._materials[wall_mat._material_id()] = wall_mat

    # ── 충돌 레이어 정의 ────────────────────────────────────────────────────
    # PLAYER: 공, ENEMY: 범퍼, DEFAULT: 일반 환경

    # ── 플레이어 공 (주황 구) ────────────────────────────────────────────────
    ball = world.add_sphere(
        radius=0.28,
        position=(0, -3.0, 1.5),
        mass=0.8,
        restitution=0.7,
        friction=0.3,
        material=f3d.Material(color="orange", roughness=0.3, metallic=0.1),
        name="player_ball",
    )
    ball.collision_layer = CollisionLayer.PLAYER
    ball.collision_mask  = CollisionLayer.ALL

    # 위쪽으로 강하게 발사
    world.apply_impulse(ball, np.array([0.3, 5.5, 2.5]) * ball.mass)

    # ── Spring Bumper 세 개 ──────────────────────────────────────────────────
    bumper_mat = f3d.Material(color=(0.2, 0.8, 0.3), roughness=0.2, metallic=0.5)
    bumper_positions = [(-1.5, 0.5), (1.5, 0.5), (0.0, 2.2)]
    bumpers: list[f3d.Body] = []

    for bx, by in bumper_positions:
        # 고정 앵커 (static)
        anchor = world.add_box(
            size=(0.15, 0.15, 0.15),
            position=(bx, by, 0.6),
            mass=1.0,
            material=f3d.Material(color=(0.5, 0.5, 0.6), roughness=0.9),
            name=f"bumper_anchor_{bx}",
        )
        anchor.collision_layer = CollisionLayer.NONE  # 충돌 비활성

        # 탄성 범퍼 헤드
        head = world.add_sphere(
            radius=0.22,
            position=(bx, by, 1.1),
            mass=0.5,
            restitution=0.95,
            friction=0.1,
            material=bumper_mat,
            name=f"bumper_{bx}",
        )
        head.collision_layer = CollisionLayer.ENEMY
        head.collision_mask  = CollisionLayer.PLAYER | CollisionLayer.DEFAULT

        # spring joint: 범퍼 헤드 ↔ 앵커
        world.add_joint(
            "spring", head, anchor,
            stiffness=300.0, damping=15.0, rest_length=0.5,
        )
        bumpers.append(head)

    # ── Hinge Paddle ─────────────────────────────────────────────────────────
    pivot = world.add_box(
        size=(0.1, 0.1, 0.1),
        position=(0, -1.5, 0.3),
        mass=1.0,
        material=f3d.Material(color=(0.6, 0.6, 0.6)),
        name="paddle_pivot",
    )
    pivot.collision_layer = CollisionLayer.NONE

    paddle = world.add_box(
        size=(2.2, 0.25, 0.2),
        position=(0, -1.5, 0.3),
        mass=1.2,
        restitution=0.8,
        friction=0.2,
        material=f3d.Material(color=(0.9, 0.7, 0.1), roughness=0.3, metallic=0.4),
        name="paddle",
    )
    paddle.collision_layer = CollisionLayer.DEFAULT
    _ = world.add_joint(
        "hinge", paddle, pivot,
        anchor_a=(0, 0, 0),
        anchor_b=(0, 0, 0),
        axis=(0, 0, 1),
        limits=(-1.2, 1.2),
        motor_velocity=2.5,
        motor_max_torque=30.0,
    )

    # ── 추가 장애물 박스들 ───────────────────────────────────────────────────
    obstacle_colors = ["red", "blue", (0.8, 0.3, 0.9), "green"]
    for i, (ox, oy, oz) in enumerate([(-1.5, 1.8, 0.5), (1.5, 1.8, 0.5), (0, 3.2, 0.5), (0, 0.8, 0.7)]):
        ob = world.add_box(
            size=(0.5, 0.5, 0.5),
            position=(ox, oy, oz),
            mass=0.6,
            restitution=0.5,
            material=f3d.Material(color=obstacle_colors[i % len(obstacle_colors)]),
            name=f"obstacle_{i}",
        )
        ob.collision_layer = CollisionLayer.DEFAULT

    # ── Trigger Zone: 득점 영역 ──────────────────────────────────────────────
    score_zone = world.add_trigger_zone(
        position=(0, 3.5, 0.5),
        size=(1.5, 1.0, 1.5),
        name="score_goal",
    )
    hit_count = [0]
    bumper_hits = [0]

    @score_zone.on_enter
    def on_score(body: f3d.Body) -> None:
        if body.name == "player_ball":
            hit_count[0] += 1

    # ── 충돌 이벤트: 범퍼 타격 감지 ─────────────────────────────────────────
    @world.on_collision_begin
    def on_any_collision(event: f3d.CollisionEvent) -> None:
        names = {event.body_a.name, event.body_b.name}
        if "player_ball" in names:
            is_bumper_hit = any(n.startswith("bumper_") for n in names)
            if is_bumper_hit:
                bumper_hits[0] += 1

    # 특정 쌍 충돌 핸들러: ball ↔ paddle
    paddle_handler = world.add_collision_handler(ball, paddle)
    paddle_bounce_count = [0]
    paddle_handler.on_begin = lambda e: paddle_bounce_count.__setitem__(0, paddle_bounce_count[0] + 1)

    # ── 카메라: 위 45° ──────────────────────────────────────────────────────
    world.set_camera(position=(0, -10, 9), target=(0, 0, 1))

    # 정착
    _warmup(world, 0.3)

    frames: list[np.ndarray] = []
    for i in range(n_frames):
        _step(world)
        frames.append(renderer.render(world.snapshot()))
        _progress(i + 1, n_frames, "    핀볼 아레나     ")

    print(f"\n    → 득점존 진입 {hit_count[0]}회 | 범퍼 충돌 {bumper_hits[0]}회 | 패들 반사 {paddle_bounce_count[0]}회")
    print()
    return frames


# ══════════════════════════════════════════════════════════════════════════════
# 장면 2 — 철거의 탑
# ══════════════════════════════════════════════════════════════════════════════

def scene2_demolition_tower(
    renderer: HQRenderer,
    n_frames: int = 216,
    save_dir: str | None = None,
) -> list[np.ndarray]:
    """Distance joint wrecking ball, weld→release, capsule chain, serialization."""

    print("  [장면 2/3] 철거의 탑 …")

    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground(material=f3d.Material(color="ground", roughness=0.9))

    # ── 타워 축조 ─────────────────────────────────────────────────────────────
    TOWER_LEVELS = 6
    BOX_W, BOX_D, BOX_H = 0.8, 0.8, 0.55
    GAP = 0.02
    tower_blocks: list[f3d.Body] = []
    level_colors = ["red", "orange", (0.9, 0.85, 0.1), "green", "blue", (0.7, 0.2, 0.9)]

    for lvl in range(TOWER_LEVELS):
        z_center = BOX_H / 2 + lvl * (BOX_H + GAP)
        n_wide = 3 if lvl % 2 == 0 else 2
        mat = f3d.Material(color=level_colors[lvl], roughness=0.6)
        for ci in range(n_wide):
            x_off = (ci - (n_wide - 1) / 2) * (BOX_W + GAP)
            b = world.add_box(
                size=(BOX_W, BOX_D, BOX_H),
                position=(x_off, 0.0, z_center),
                mass=1.2,
                restitution=0.15,
                friction=0.7,
                material=mat,
                name=f"tower_lvl{lvl}_c{ci}",
            )
            b.collision_layer = CollisionLayer.DEFAULT
            tower_blocks.append(b)

    # 타워 꼭대기에 금 트로피 박스
    _ = world.add_box(
        size=(0.4, 0.4, 0.4),
        position=(0, 0, TOWER_LEVELS * (BOX_H + GAP) + 0.2),
        mass=0.5,
        restitution=0.4,
        material=f3d.Material(color="gold", roughness=0.1, metallic=0.95),
        name="trophy",
    )

    _warmup(world, 1.2)

    # ── 직렬화 데모: 타워 완성 상태 저장 ────────────────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        save_path = Path(tmp) / "tower_state.json"
        world.save(save_path)
        loaded = f3d.World.load(save_path)
        print(f"\n    직렬화 확인: {len(loaded.bodies)}개 body 복원 완료 (저장→로드)")

    # ── 캡슐 체인 (weld constraint 시연) ────────────────────────────────────
    # 체인 고정점 (천장 높이를 흉내 낸 static sphere)
    ceiling_anchor = world.add_sphere(
        radius=0.12,
        position=(-5.0, 0.0, 6.5),
        mass=1.0,
        material=f3d.Material(color=(0.6, 0.6, 0.6)),
        name="ceiling_anchor",
        static=True,
    )

    # 캡슐 링크 3개를 weld로 연결
    chain_links: list[f3d.Body] = []
    for li in range(3):
        link = world.add_capsule(
            radius=0.10,
            half_length=0.25,
            position=(-5.0, 0.0, 6.0 - li * 0.6),
            mass=0.4,
            restitution=0.2,
            friction=0.5,
            material=f3d.Material(color=(0.4, 0.4, 0.5), roughness=0.4, metallic=0.6),
            name=f"chain_{li}",
        )
        link.collision_layer = CollisionLayer.DEBRIS
        link.collision_mask  = CollisionLayer.DEFAULT | CollisionLayer.DEBRIS
        chain_links.append(link)
        if li == 0:
            world.weld(link, ceiling_anchor)
        else:
            world.weld(link, chain_links[li - 1])

    # ── 쇄도 공 (distance joint: 진자 운동) ──────────────────────────────────
    wrecking_ball = world.add_sphere(
        radius=0.55,
        position=(-5.0, 0.0, 4.5),
        mass=15.0,
        restitution=0.25,
        friction=0.35,
        material=f3d.Material(color=(0.12, 0.12, 0.15), roughness=0.2, metallic=0.85),
        name="wrecking_ball",
    )
    wrecking_ball.collision_layer = CollisionLayer.DEFAULT

    # distance joint: 쇄도 공 ↔ 천장 앵커 (4.5m 체인)
    _ = world.add_joint(
        "distance",
        wrecking_ball, ceiling_anchor,
        anchor_a=(0, 0, 0),
        anchor_b=(0, 0, 0),
        target_distance=2.0,
    )

    # 수평 충격으로 진자 운동 시작 → 타워 방향
    world.apply_impulse(wrecking_ball, np.array([60.0, 0.0, 10.0]))

    # 쇄도 공이 타워 타격 시 체인 release (순수 자유 비행)
    release_done = [False]

    @world.on_collision_begin
    def on_hit(event: f3d.CollisionEvent) -> None:
        if release_done[0]:
            return
        names = {event.body_a.name, event.body_b.name}
        if "wrecking_ball" in names:
            is_tower = any(n.startswith("tower_") for n in names)
            if is_tower:
                for lnk in chain_links:
                    world.release(lnk)
                release_done[0] = True

    # ── 카메라 ───────────────────────────────────────────────────────────────
    world.set_camera(position=(8, -8, 7), target=(0, 0, 2))

    frames: list[np.ndarray] = []
    for i in range(n_frames):
        _step(world)
        frames.append(renderer.render(world.snapshot()))
        _progress(i + 1, n_frames, "    철거의 탑        ")

    sleeping_count = sum(1 for b in world.bodies if b.is_sleeping)
    print(f"\n    → 타격 후 수면 물체: {sleeping_count}개")
    print()
    return frames


# ══════════════════════════════════════════════════════════════════════════════
# 장면 3 — 지형 슬라이드 + StateRecorder
# ══════════════════════════════════════════════════════════════════════════════

def scene3_terrain_slide(renderer: HQRenderer, n_frames: int = 168) -> list[np.ndarray]:
    """Heightfield terrain, PBR materials, StateRecorder, apply_torque, teleport."""

    print("  [장면 3/3] 지형 슬라이드 …")

    world = f3d.World(gravity=(0, 0, -9.81))

    # ── Heightfield 지형 ─────────────────────────────────────────────────────
    GRID = 24
    rng = np.random.default_rng(77)
    # 완만한 슬로프 기반 + 노이즈
    xs = np.linspace(0, 1, GRID)
    ys = np.linspace(0, 1, GRID)
    XX, YY = np.meshgrid(xs, ys)
    heights = (
        2.5 * (1.0 - XX)                        # 뒤쪽(x≈0)이 높음
        + 0.8 * np.sin(YY * np.pi * 2)          # 좌우 물결
        + rng.uniform(-0.15, 0.15, (GRID, GRID)).astype(np.float32)
    ).astype(np.float32)
    heights = np.clip(heights, 0.0, 3.5)

    world.add_terrain(
        heights=heights,
        cell_size=0.55,
        origin=(-6.5, -6.5, 0.0),
        material=f3d.Material(color=(0.38, 0.32, 0.22), roughness=0.95),
    )

    # ── 다양한 PBR 재질 물체 낙하 ────────────────────────────────────────────
    materials_showcase = [
        f3d.Material(color="white",   roughness=0.05, metallic=0.95),   # mirror metal
        f3d.Material(color="gold",    roughness=0.2,  metallic=0.9),    # gold
        f3d.Material(color="red",     roughness=0.7,  metallic=0.0),    # matte red
        f3d.Material(color=(0.1, 0.6, 1.0), roughness=0.1, metallic=0.0),  # shiny blue
        f3d.Material(color=(0.9, 0.5, 0.1), roughness=0.5, metallic=0.3),  # orange semi-metal
        f3d.Material(color="green",   roughness=0.8,  metallic=0.0),    # rubber green
        f3d.Material(color=(0.7, 0.2, 0.9), roughness=0.3, metallic=0.6),  # purple metal
        f3d.Material(color="white",   roughness=0.9,  metallic=0.0),    # chalk white
    ]

    dropped: list[f3d.Body] = []
    for i, mat in enumerate(materials_showcase):
        col = i % 4
        row = i // 4
        x = -4.0 + col * 1.8
        y = -1.5 + row * 2.0
        z = 4.5 + rng.uniform(0, 1.5)
        r = float(rng.uniform(0.18, 0.32))
        b = world.add_sphere(
            radius=r,
            position=(x, y, z),
            mass=float(rng.uniform(0.5, 2.0)),
            restitution=float(rng.uniform(0.2, 0.8)),
            friction=float(rng.uniform(0.2, 0.7)),
            material=mat,
            name=f"pbr_ball_{i}",
        )
        b.collision_layer = CollisionLayer.DEFAULT
        dropped.append(b)

    # 캡슐 굴리기 (회전력 적용 시연)
    barrel = world.add_capsule(
        radius=0.3,
        half_length=0.5,
        position=(-3.0, 0.0, 5.5),
        mass=2.0,
        restitution=0.3,
        friction=0.4,
        material=f3d.Material(color=(0.6, 0.4, 0.2), roughness=0.5, metallic=0.2),
        name="barrel",
    )
    barrel.apply_torque((0, 20, 0))   # 굴리기 시작 토크

    # ── Trigger Zone: 목표 영역 (슬라이드 도착점) ──────────────────────────
    finish_zone = world.add_trigger_zone(
        position=(3.5, 0, 0.8),
        size=(3.0, 5.0, 2.0),
        name="finish_line",
    )
    arrived = [0]

    @finish_zone.on_enter
    def on_finish(body: f3d.Body) -> None:
        arrived[0] += 1

    # ── teleport 시연: 3초 후 한 공을 리셋 ─────────────────────────────────
    teleport_done = [False]
    teleport_frame = int(3.0 * FPS)

    # ── StateRecorder 시작 ──────────────────────────────────────────────────
    state_rec = StateRecorder(world)
    state_rec.start()

    # ── ball → ball 충돌 stay 이벤트 카운터 ─────────────────────────────────
    stay_events = [0]

    @world.on_collision_stay
    def on_stay(event: f3d.CollisionEvent) -> None:
        stay_events[0] += 1

    # ── 카메라 ───────────────────────────────────────────────────────────────
    world.set_camera(position=(9, -7, 8), target=(0, 0, 2))

    frames: list[np.ndarray] = []
    for i in range(n_frames):
        # teleport 시연
        if i == teleport_frame and not teleport_done[0]:
            world.teleport(dropped[0], position=(-4.0, -1.5, 5.5))
            dropped[0].set_velocity((0, 0, 0))
            teleport_done[0] = True

        _step(world)
        state_rec.record()
        frames.append(renderer.render(world.snapshot()))
        _progress(i + 1, n_frames, "    지형 슬라이드    ")

    state_rec.stop()

    # StateRecorder 저장 (임시)
    with tempfile.TemporaryDirectory() as tmp:
        rec_path = Path(tmp) / "slide.npz"
        state_rec.save(rec_path)
        size_kb = rec_path.stat().st_size // 1024
        print(f"\n    StateRecorder: {len(state_rec._frames)}프레임 저장 ({size_kb} KB)")

    print(f"    도착 물체: {arrived[0]}개 | stay 이벤트 누적: {stay_events[0]}")
    print()
    return frames


# ══════════════════════════════════════════════════════════════════════════════
# 배너 및 메인
# ══════════════════════════════════════════════════════════════════════════════

def _banner(W: int, H: int, spp: int, scenes: list[int], n_total: int, out: str) -> None:
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     pyforge3d — Cascade Gauntlet 종합 기능 쇼케이스          ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  활용 기능: 조인트·트리거존·충돌이벤트·레이어·직렬화·지형     ║")
    print("║             StateRecorder·weld/release·PBR재질·캡슐·토크     ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  장면 1. 핀볼 아레나  — spring/hinge/trigger/collision layer ║")
    print("║  장면 2. 철거의 탑    — distance joint/weld/release/save     ║")
    print("║  장면 3. 지형 슬라이드 — terrain/PBR/StateRecorder/teleport  ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print(f"  해상도: {W}×{H}   SPP: {spp}   장면: {scenes}")
    print(f"  총 프레임: {n_total}  ({n_total/FPS:.1f}초 @ {FPS}fps)")
    print(f"  물리 dt: {PHYS_DT*1000:.2f}ms  (서브스텝×{SUBSTEPS})")
    print(f"  출력: {out}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="pyforge3d Cascade Gauntlet — 종합 기능 쇼케이스"
    )
    parser.add_argument("--output", "-o", default="cascade_gauntlet.mp4")
    parser.add_argument("--hq",    action="store_true", help="640×400, spp=2")
    parser.add_argument("--ultra", action="store_true", help="800×500, spp=4")
    parser.add_argument("--scene", "-s", type=int, choices=[1, 2, 3],
                        help="특정 장면만 렌더링")
    args = parser.parse_args()

    if args.ultra:
        W, H, spp = 800, 500, 4
    elif args.hq:
        W, H, spp = 640, 400, 2
    else:
        W, H, spp = 480, 320, 1

    scene_map = {
        1: (scene1_pinball_arena,     192),
        2: (scene2_demolition_tower,  216),
        3: (scene3_terrain_slide,     168),
    }

    target = [args.scene] if args.scene else [1, 2, 3]
    n_total = sum(scene_map[s][1] for s in target)

    _banner(W, H, spp, target, n_total, args.output)

    t0 = time.perf_counter()
    renderer = HQRenderer(width=W, height=H, samples=spp)

    all_frames: list[np.ndarray] = []
    for s in target:
        fn, nf = scene_map[s]
        all_frames.extend(fn(renderer, n_frames=nf))

    renderer.close()

    print(f"  영상 저장 중 → {args.output} …", end="", flush=True)
    writer = imageio.get_writer(args.output, fps=FPS, quality=8)
    for frame in all_frames:
        writer.append_data(frame)
    writer.close()
    print(" 완료")

    elapsed = time.perf_counter() - t0
    size_kb = os.path.getsize(args.output) // 1024

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║                       완료!                                  ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║  파일  : {args.output:<52}║")
    print(f"║  크기  : {size_kb} KB{'':<54}║")
    print(f"║  길이  : {len(all_frames)/FPS:.1f}초  ({len(all_frames)}프레임){'':<34}║")
    print(f"║  소요  : {elapsed:.0f}초  ({elapsed/len(all_frames):.2f}초/프레임){'':<30}║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print(f"  재생: mpv {args.output}  또는  vlc {args.output}")
    print()


if __name__ == "__main__":
    main()
