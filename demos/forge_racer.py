"""demos/forge_racer.py — Forge Racer 🏎
pyforge3d 자동차 드라이브 레이싱 게임

Controls
--------
  W / ↑    : 가속
  S / ↓    : 브레이크 / 후진
  A / ←    : 좌회전 (반시계)
  D / →    : 우회전 (시계)
  SPACE    : 핸드브레이크 (즉각 감속)
  R        : 마지막 체크포인트로 리셋
  C        : 카메라 모드 전환 (추적 ↔ 자유 orbit)
  마우스 우클릭 드래그 : 자유 카메라 회전
  스크롤   : 줌 in/out
  F5       : 현재 월드 상태 저장
  ESC      : 종료

목표: 3바퀴를 완주하세요!

활용 기능
---------
  World, Body (box/sphere/capsule), Material (PBR),
  add_joint (spring/hinge/distance/fixed), weld/release,
  add_trigger_zone (checkpoints, lap, pickup),
  on_collision_begin, add_collision_handler,
  CollisionLayer (PLAYER/TERRAIN/DEFAULT/ENEMY/BULLET/DEBRIS),
  apply_force, apply_torque, apply_impulse, teleport,
  OrbitCamera, is_sleeping, World.save, StateRecorder
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np
import pygame

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.game.renderer import WindowRenderer

import forge3d as f3d
from forge3d.collision.layers import CollisionLayer
from forge3d.io.world_snapshot import StateRecorder
from forge3d.math.quaternion import quat_to_rot

# ── 윈도우 ────────────────────────────────────────────────────────────────────
W, H   = 1280, 720
FPS    = 60
DT     = 1.0 / FPS

# ── 트랙 치수 ─────────────────────────────────────────────────────────────────
OUTER_HW = 22   # 외벽 반폭 (x)
OUTER_HD = 32   # 외벽 반깊이 (y)
INNER_HW = 10   # 내벽 반폭
INNER_HD = 20   # 내벽 반깊이
WALL_H   = 3.0  # 벽 높이
WALL_T   = 0.8  # 벽 두께

# ── 자동차 물리 ───────────────────────────────────────────────────────────────
CAR_MASS      = 18.0   # kg
CAR_SIZE      = (2.2, 1.1, 0.55)
WHEEL_R       = 0.32

ENGINE_F      = 400.0  # 구동력 (N)
REVERSE_F     = 180.0  # 후진력
STEER_TAU     = 90.0   # 조향 토크 (N·m)
MAX_SPEED     = 18.0   # 최고속도 (m/s)  ≈ 65 km/h
GRIP          = 16.0   # 옆미끄럼 감쇠
ANG_DAMP      = 0.80   # 각속도 감쇠 (스텝당 × 계수)
PITCH_DAMP    = 0.25   # 피치/롤 각속도 감쇠 (더 강하게 억제)

CARGO_DETACH_SPD = 8.0  # 충돌 상대속도 ≥ 이 값이면 화물 분리
DAMAGE_PER_HIT   = 5.0

# ── 충돌 레이어 ───────────────────────────────────────────────────────────────
L_CAR    = CollisionLayer.PLAYER
L_GROUND = CollisionLayer.TERRAIN
L_WALL   = CollisionLayer.DEFAULT
L_OBS    = CollisionLayer.ENEMY
L_PICKUP = CollisionLayer.BULLET
L_DEBRIS = CollisionLayer.DEBRIS

# ── PBR 재질 팔레트 ───────────────────────────────────────────────────────────
MAT_CAR      = f3d.Material(color=(0.85, 0.08, 0.08), roughness=0.25, metallic=0.65)
MAT_WHEEL    = f3d.Material(color=(0.08, 0.08, 0.08), roughness=0.95, metallic=0.0)
MAT_CARGO    = f3d.Material(color=(0.95, 0.75, 0.1),  roughness=0.45, metallic=0.4)
MAT_WALL_OUT = f3d.Material(color=(0.70, 0.70, 0.72), roughness=0.70)
MAT_WALL_IN  = f3d.Material(color=(0.55, 0.55, 0.60), roughness=0.70)
MAT_GROUND   = f3d.Material(color=(0.22, 0.22, 0.25), roughness=0.95)
MAT_BUMPER   = f3d.Material(color=(0.1,  0.85, 0.2),  roughness=0.20, metallic=0.55)
MAT_SPINNER  = f3d.Material(color=(0.95, 0.40, 0.05), roughness=0.30, metallic=0.75)
MAT_SWING    = f3d.Material(color=(0.12, 0.12, 0.18), roughness=0.18, metallic=0.92)
MAT_ANCHOR   = f3d.Material(color=(0.40, 0.40, 0.45), roughness=0.80)
MAT_PYLON    = f3d.Material(color=(1.0,  0.45, 0.05), roughness=0.65)
MAT_PICKUP   = f3d.Material(color=(0.2,  0.6,  1.0),  roughness=0.10, metallic=0.0)
MAT_STAR     = f3d.Material(color=(1.0,  0.9,  0.0),  roughness=0.05, metallic=0.9)

TOTAL_LAPS = 3

# ── 유틸: 정적 벽 추가 ────────────────────────────────────────────────────────

def _add_static(
    world: f3d.World,
    cx: float, cy: float, cz: float,
    sx: float, sy: float, sz: float,
    mat: f3d.Material,
    name: str = "wall",
    layer: int = L_WALL,
    restitution: float = 0.30,
    friction: float = 0.45,
) -> f3d.Body:
    """Static body를 추가하고 world._bodies에도 등록한다."""
    mid = mat._material_id()
    world._materials[mid] = mat
    bid = world._physics.add_static_box(
        size=(sx, sy, sz),
        position=(cx, cy, cz),
        material=mid,
        name=name,
        restitution=restitution,
        friction=friction,
    )
    body = f3d.Body(world._physics, bid)
    world._bodies[bid] = body
    body.collision_layer = layer
    body.collision_mask  = CollisionLayer.ALL
    return body


# ══════════════════════════════════════════════════════════════════════════════
# 1. 트랙 건설
# ══════════════════════════════════════════════════════════════════════════════

def build_track(world: f3d.World) -> None:
    """직사각형 서킷 — 외벽 + 내벽 + 바닥."""

    # 바닥 (넓은 정적 박스, 두 겹)
    world.add_ground(
        material=MAT_GROUND,
        size=(OUTER_HW * 2 + 2, OUTER_HD * 2 + 2, 0.3),
    )

    hw, hd = OUTER_HW, OUTER_HD
    iw, id_ = INNER_HW, INNER_HD

    # 외벽 4면 (두께 WALL_T, 높이 WALL_H)
    for cx, cy, sx, sy in [
        (0,   hd,   hw * 2 + WALL_T * 2, WALL_T),   # 북
        (0,  -hd,   hw * 2 + WALL_T * 2, WALL_T),   # 남
        (hw,  0,    WALL_T,              hd * 2),    # 동
        (-hw, 0,    WALL_T,              hd * 2),    # 서
    ]:
        _add_static(world, cx, cy, WALL_H / 2, sx, sy, WALL_H, MAT_WALL_OUT)

    # 내벽 4면 (섬 경계)
    for cx, cy, sx, sy in [
        (0,   id_,  iw * 2 + WALL_T * 2, WALL_T),
        (0,  -id_,  iw * 2 + WALL_T * 2, WALL_T),
        (iw,  0,    WALL_T,              id_ * 2),
        (-iw, 0,    WALL_T,              id_ * 2),
    ]:
        _add_static(world, cx, cy, WALL_H / 2, sx, sy, WALL_H, MAT_WALL_IN)

    # 시작선 표식 — 얇고 납작한 골드 박스
    _add_static(world, 0, -(id_ + (hd - id_) / 2), 0.05,
                3.0, (hd - id_) - 0.5, 0.10,
                MAT_STAR, name="startline", restitution=0.1, friction=0.1)


# ══════════════════════════════════════════════════════════════════════════════
# 2. 자동차 조립
# ══════════════════════════════════════════════════════════════════════════════

def build_car(world: f3d.World) -> tuple[f3d.Body, list[f3d.Body], f3d.Body]:
    """
    차체(box) + 바퀴 4개(sphere, weld) + 화물(box, weld·분리 가능)
    Returns: (car_body, wheels, cargo)
    """
    # 시작 위치: 남쪽 직선 중앙, 동쪽 방향 (+X)
    start = (0.0, -(INNER_HD + (OUTER_HD - INNER_HD) / 2), 0.5)

    car = world.add_box(
        size=CAR_SIZE,
        position=start,
        mass=CAR_MASS,
        restitution=0.15,
        friction=0.50,
        material=MAT_CAR,
        name="car",
    )
    car.collision_layer = L_CAR
    car.collision_mask  = CollisionLayer.ALL

    # 바퀴 4개 (시각적 장식; physics collision 없음 → layer NONE)
    wheel_offsets = [
        (+CAR_SIZE[0] / 2 - 0.25, +CAR_SIZE[1] / 2 + WHEEL_R * 0.4, -CAR_SIZE[2] / 2 + 0.05),
        (+CAR_SIZE[0] / 2 - 0.25, -CAR_SIZE[1] / 2 - WHEEL_R * 0.4, -CAR_SIZE[2] / 2 + 0.05),
        (-CAR_SIZE[0] / 2 + 0.25, +CAR_SIZE[1] / 2 + WHEEL_R * 0.4, -CAR_SIZE[2] / 2 + 0.05),
        (-CAR_SIZE[0] / 2 + 0.25, -CAR_SIZE[1] / 2 - WHEEL_R * 0.4, -CAR_SIZE[2] / 2 + 0.05),
    ]
    wheels: list[f3d.Body] = []
    for i, (ox, oy, oz) in enumerate(wheel_offsets):
        w_pos = (start[0] + ox, start[1] + oy, start[2] + oz)
        wheel = world.add_sphere(
            radius=WHEEL_R,
            position=w_pos,
            mass=1.0,
            restitution=0.1,
            friction=0.8,
            material=MAT_WHEEL,
            name=f"wheel_{i}",
        )
        wheel.collision_layer = CollisionLayer.NONE  # 충돌 비활성
        wheel.collision_mask  = CollisionLayer.NONE
        world.weld(wheel, car)
        world.ignore_collision(wheel, car)
        wheels.append(wheel)

    # 화물 박스 (차체 위에 weld, 강한 충돌 시 분리됨)
    cargo_pos = (start[0], start[1], start[2] + CAR_SIZE[2] / 2 + 0.2)
    cargo = world.add_box(
        size=(0.9, 0.7, 0.4),
        position=cargo_pos,
        mass=3.0,
        restitution=0.2,
        friction=0.6,
        material=MAT_CARGO,
        name="cargo",
    )
    cargo.collision_layer = L_DEBRIS
    cargo.collision_mask  = L_WALL | L_GROUND | L_OBS | CollisionLayer.DEFAULT
    world.weld(cargo, car)
    world.ignore_collision(cargo, car)

    return car, wheels, cargo


# ══════════════════════════════════════════════════════════════════════════════
# 3. 장애물 설치
# ══════════════════════════════════════════════════════════════════════════════

def build_obstacles(
    world: f3d.World,
    car: f3d.Body,
) -> tuple[list[f3d.Body], list[f3d.Body]]:
    """
    Spring 범퍼 3개 (동쪽 직선)
    Hinge 회전 장애물 1개 (북쪽 직선)
    Distance joint 진자 장애물 1개 (서쪽 직선)
    Capsule 슬라럼 파일론 6개 (남동 코너)
    Returns: (bumper_heads, pylons)
    """
    bumper_heads: list[f3d.Body] = []

    # ── Spring 범퍼 (동쪽 직선, x≈17) ──────────────────────────────────────
    for by in [-10.0, 0.0, 10.0]:
        anchor = _add_static(world, 17.5, by, 0.6,
                             0.2, 0.2, 0.2, MAT_ANCHOR,
                             name="bumper_anchor", layer=CollisionLayer.NONE)
        head = world.add_sphere(
            radius=0.50,
            position=(17.5, by, 1.2),
            mass=1.5,
            restitution=0.95,
            friction=0.05,
            material=MAT_BUMPER,
            name=f"bumper_{by}",
        )
        head.collision_layer = L_OBS
        head.collision_mask  = L_CAR | L_WALL | L_GROUND | CollisionLayer.DEFAULT
        world.add_joint("spring", head, anchor,
                        stiffness=500.0, damping=20.0, rest_length=0.6)
        world.ignore_collision(head, anchor)
        bumper_heads.append(head)

    # ── Hinge 회전 장애물 (북쪽 직선 중앙, y≈27) ────────────────────────────
    # 고정 축 (world-anchored: body_b=None → 월드 고정점)
    spin_pivot_z = 1.5
    spin_anchor = _add_static(world, 0, 27, spin_pivot_z,
                              0.2, 0.2, 0.2, MAT_ANCHOR,
                              name="spin_anchor", layer=CollisionLayer.NONE)
    spinner = world.add_box(
        size=(5.0, 0.4, 0.4),
        position=(0, 27, spin_pivot_z),
        mass=4.0,
        restitution=0.3,
        friction=0.2,
        material=MAT_SPINNER,
        name="spinner",
    )
    spinner.collision_layer = L_OBS
    spinner.collision_mask  = L_CAR | L_WALL | L_GROUND | CollisionLayer.DEFAULT
    world.add_joint("hinge", spinner, spin_anchor,
                    anchor_a=(0, 0, 0), anchor_b=(0, 0, 0),
                    axis=(0, 0, 1),
                    motor_velocity=2.0,
                    motor_max_torque=80.0)
    world.ignore_collision(spinner, spin_anchor)

    # ── Distance joint 진자 (서쪽 직선, x≈-17) ──────────────────────────────
    ceil_anchor = _add_static(world, -17, -8, WALL_H,
                              0.3, 0.3, 0.3, MAT_ANCHOR,
                              name="swing_ceiling", layer=CollisionLayer.NONE)
    swing_ball = world.add_sphere(
        radius=0.70,
        position=(-17, -8, WALL_H - 3.0),
        mass=8.0,
        restitution=0.3,
        friction=0.2,
        material=MAT_SWING,
        name="swing_ball",
    )
    swing_ball.collision_layer = L_OBS
    swing_ball.collision_mask  = L_CAR | L_WALL | L_GROUND | CollisionLayer.DEFAULT
    world.add_joint("distance", swing_ball, ceil_anchor,
                    anchor_a=(0, 0, 0), anchor_b=(0, 0, 0),
                    target_distance=3.0)
    world.ignore_collision(swing_ball, ceil_anchor)
    # 옆으로 밀어 진자 시작
    world.apply_impulse(swing_ball, np.array([40.0, 0.0, 0.0]))

    # ── Capsule 슬라럼 파일론 (남동 코너) ────────────────────────────────────
    pylons: list[f3d.Body] = []
    for i in range(6):
        px = 12.5 + i * 1.2
        py = -22.5
        pylon = world.add_capsule(
            radius=0.15,
            half_length=0.7,
            position=(px, py, 0.85),
            mass=0.4,
            restitution=0.5,
            friction=0.4,
            material=MAT_PYLON,
            name=f"pylon_{i}",
        )
        pylon.collision_layer = L_OBS
        pylon.collision_mask  = L_CAR | L_WALL | L_GROUND | CollisionLayer.DEFAULT
        pylons.append(pylon)

    return bumper_heads, pylons


# ══════════════════════════════════════════════════════════════════════════════
# 4. 픽업 아이템 + 체크포인트 트리거 존
# ══════════════════════════════════════════════════════════════════════════════

def build_pickups_and_checkpoints(
    world: f3d.World,
    car: f3d.Body,
    game: GameState,
) -> list[f3d.Body]:
    """
    파란 픽업 구체 4개 (속도 부스트)
    체크포인트 트리거 존 4개 + 출발선/완주선
    """
    # ── 픽업 ──────────────────────────────────────────────────────────────────
    pickup_locs = [
        (17.0, -20.0, 0.8),   # 남동
        (17.0,  20.0, 0.8),   # 북동
        (-17.0,  20.0, 0.8),  # 북서
        (-17.0, -20.0, 0.8),  # 남서
    ]
    pickups: list[f3d.Body] = []
    for i, (px, py, pz) in enumerate(pickup_locs):
        p = world.add_sphere(
            radius=0.45,
            position=(px, py, pz),
            mass=0.5,
            restitution=0.6,
            friction=0.1,
            material=MAT_PICKUP,
            name=f"pickup_{i}",
        )
        p.collision_layer = L_PICKUP
        p.collision_mask  = L_CAR | L_GROUND | L_WALL
        pickups.append(p)

        # 픽업과 자동차 사이 충돌 핸들러
        handler = world.add_collision_handler(car, p)
        _i = i  # closure capture
        def _on_pickup_hit(event: f3d.CollisionEvent, idx: int = _i) -> None:
            if game.boost_timer <= 0:
                game.boost_timer  = 4.0     # 4초 부스트
                game.score       += 50
                game.pickup_count += 1
                # 픽업을 반대편 코너로 이동 (재활용)
                new_pos = pickup_locs[(idx + 2) % len(pickup_locs)]
                world.teleport(pickups[idx], new_pos)
                pickups[idx].set_velocity((0, 0, 0))

        handler.on_begin = _on_pickup_hit

    # ── 체크포인트 트리거 존 ──────────────────────────────────────────────────
    # 코리도 중심에 배치: x/y 중심 = (inner+outer)/2
    cx_east  =  INNER_HW + (OUTER_HW - INNER_HW) / 2   # 동쪽 코리도 중심 x = 16
    cy_north =  INNER_HD + (OUTER_HD - INNER_HD) / 2   # 북쪽 코리도 중심 y = 26
    corr_w   = OUTER_HW - INNER_HW - 0.5               # 코리도 폭 - 여유 = 11.5
    # (cx, cy, cz, sx, sy, sz, cp_index)
    cp_defs = [
        (cx_east,  0,         2.0, corr_w, 4.0,    4.0, 0),   # 동쪽
        (0,        cy_north,  2.0, 4.0,    corr_w, 4.0, 1),   # 북쪽
        (-cx_east, 0,         2.0, corr_w, 4.0,    4.0, 2),   # 서쪽
    ]
    for cx, cy, cz, sx, sy, sz, idx in cp_defs:
        zone = world.add_trigger_zone(position=(cx, cy, cz), size=(sx, sy, sz))
        _idx = idx
        @zone.on_enter
        def _on_cp(body: f3d.Body, ci: int = _idx) -> None:
            if body.name == "car":
                game.register_checkpoint(ci)

    # 완주/출발선
    finish_zone = world.add_trigger_zone(
        position=(0, -(INNER_HD + (OUTER_HD - INNER_HD) / 2), 2.0),
        size=(OUTER_HW - INNER_HW - 1, 4.0, 4.0),
    )
    @finish_zone.on_enter
    def _on_finish(body: f3d.Body) -> None:
        if body.name == "car":
            game.cross_finish()

    return pickups


# ══════════════════════════════════════════════════════════════════════════════
# 5. 게임 상태
# ══════════════════════════════════════════════════════════════════════════════

class GameState:
    INTRO    = 0
    RACING   = 1
    FINISHED = 2

    def __init__(self) -> None:
        self.phase      = self.INTRO
        self.lap        = 0          # 현재 랩 (1-indexed during race)
        self.lap_start  = 0.0        # 랩 시작 시각
        self.best_lap   = float("inf")
        self.best_total = float("inf")
        self.race_start = 0.0
        self.total_time = 0.0

        self.next_cp    = 0          # 다음에 통과해야 할 체크포인트 (0/1/2)
        self.cps_done   = 0          # 이번 랩 통과한 체크포인트 수

        self.damage     = 0.0        # 누적 충돌 데미지
        self.score      = 0
        self.boost_timer = 0.0       # 남은 부스트 시간
        self.pickup_count = 0
        self.cargo_lost  = False

        self.lap_times: list[float] = []

    def start_race(self) -> None:
        self.phase     = self.RACING
        self.lap       = 1
        self.next_cp   = 0
        self.cps_done  = 0
        t = time.perf_counter()
        self.race_start = t
        self.lap_start  = t

    def register_checkpoint(self, idx: int) -> None:
        if self.phase != self.RACING:
            return
        if idx == self.next_cp:
            self.next_cp  = (self.next_cp + 1) % 3
            self.cps_done += 1
            self.score   += 100

    def cross_finish(self) -> None:
        if self.phase != self.RACING:
            # INTRO → 레이스 시작
            self.start_race()
            return
        if self.cps_done < 3:
            return   # 체크포인트 미통과 — 랩 무효
        now     = time.perf_counter()
        lap_t   = now - self.lap_start
        self.lap_times.append(lap_t)
        self.best_lap = min(self.best_lap, lap_t)
        self.score += max(0, int(1000 - lap_t * 10))

        self.lap      += 1
        self.cps_done  = 0
        self.next_cp   = 0
        self.lap_start = now

        if self.lap > TOTAL_LAPS:
            self.total_time = now - self.race_start
            self.best_total = min(self.best_total, self.total_time)
            self.phase = self.FINISHED

    def update(self, dt: float) -> None:
        if self.boost_timer > 0:
            self.boost_timer = max(0.0, self.boost_timer - dt)

    def speed_multiplier(self) -> float:
        return 1.5 if self.boost_timer > 0 else 1.0

    def hud_line(self, speed_ms: float) -> str:
        speed_kmh = speed_ms * 3.6
        if self.phase == self.INTRO:
            return (
                "  출발선을 통과하면 레이스 시작!  "
                "[WASD] 이동  [SPACE] 핸드브레이크  [R] 리셋  [C] 카메라  [ESC] 종료"
            )
        if self.phase == self.FINISHED:
            total = self.total_time
            best  = self.best_lap
            return (
                f"  완주!  총 시간: {total:.2f}s  "
                f"베스트 랩: {best:.2f}s  점수: {self.score}  "
                f"[R] 다시 시작  [ESC] 종료"
            )
        now    = time.perf_counter()
        cur_lap_t = now - self.lap_start
        boost  = f"  [BOOST {self.boost_timer:.1f}s]" if self.boost_timer > 0 else ""
        damage = f"  Dmg:{self.damage:.0f}" if self.damage > 0 else ""
        cargo  = "  화물분리!" if self.cargo_lost else ""
        return (
            f"  랩 {self.lap}/{TOTAL_LAPS}  "
            f"CP {self.cps_done}/3  "
            f"랩타임: {cur_lap_t:.1f}s  "
            f"베스트: {self.best_lap:.1f}s  "
            f"속도: {speed_kmh:.0f} km/h  "
            f"점수: {self.score}"
            f"{boost}{damage}{cargo}"
        )

    def gameover_line(self) -> str:
        laps_str = "  ".join(f"L{i+1}:{t:.2f}s" for i, t in enumerate(self.lap_times))
        return (
            f"총 시간: {self.total_time:.2f}s  "
            f"베스트 랩: {self.best_lap:.2f}s  "
            f"점수: {self.score}  |  {laps_str}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# 6. 자동차 물리
# ══════════════════════════════════════════════════════════════════════════════

def apply_car_physics(
    world: f3d.World,
    car: f3d.Body,
    keys: pygame.key.ScancodeWrapper,
    game: GameState,
) -> None:
    """매 프레임 자동차에 힘·토크·보정을 적용한다."""
    R       = quat_to_rot(car.orientation)     # 3×3 회전 행렬
    forward = R[:, 0]                           # 차의 전방 (로컬 X축)
    right   = R[:, 1]                           # 차의 우측 (로컬 Y축)

    vel     = car.velocity.copy()
    speed   = float(np.linalg.norm(vel))
    spd_mul = game.speed_multiplier()

    # ── 구동력 ────────────────────────────────────────────────────────────────
    throttle = keys[pygame.K_w] or keys[pygame.K_UP]
    reverse  = keys[pygame.K_s] or keys[pygame.K_DOWN]
    if throttle and speed < MAX_SPEED * spd_mul:
        world.apply_impulse(car, forward * ENGINE_F * spd_mul * DT)
    if reverse:
        if speed > 0.5:  # 이미 움직이면 브레이크
            world.apply_impulse(car, -vel * 0.15 * CAR_MASS)
        else:            # 후진
            world.apply_impulse(car, -forward * REVERSE_F * DT)

    # ── 조향 (Z축 토크) ──────────────────────────────────────────────────────
    steer_factor = max(0.3, 1.0 - speed / (MAX_SPEED * 2))  # 고속에서 약해짐
    if keys[pygame.K_a] or keys[pygame.K_LEFT]:
        car.apply_torque((0, 0,  STEER_TAU * steer_factor))
    if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
        car.apply_torque((0, 0, -STEER_TAU * steer_factor))

    # ── 핸드브레이크 ─────────────────────────────────────────────────────────
    if keys[pygame.K_SPACE]:
        world.apply_impulse(car, -vel * 0.30 * CAR_MASS)

    # ── 옆미끄럼 감쇠 (타이어 그립 시뮬레이션) ───────────────────────────────
    lat_vel = float(np.dot(vel, right))
    world.apply_impulse(car, -right * lat_vel * GRIP * DT * CAR_MASS)

    # ── 각속도 감쇠 (피치·롤은 강하게, 요는 약하게) ──────────────────────────
    omega = car.angular_velocity
    car.set_angular_velocity(np.array([
        omega[0] * PITCH_DAMP,
        omega[1] * PITCH_DAMP,
        omega[2] * ANG_DAMP,
    ]))

    # ── 차체를 수직으로 복원 (뒤집힘 방지) ───────────────────────────────────
    up = R[:, 2]   # 차의 위쪽 (로컬 Z축)
    if up[2] < 0.7:
        # 차가 많이 기울면 약한 복원 토크 적용
        tilt_axis = np.cross(up, np.array([0.0, 0.0, 1.0]))
        car.apply_torque(tilt_axis * 30.0)

    # ── 최고속도 제한 ─────────────────────────────────────────────────────────
    max_v = MAX_SPEED * spd_mul
    if speed > max_v:
        world.apply_impulse(car, (vel / speed) * (max_v - speed) * CAR_MASS)


# ══════════════════════════════════════════════════════════════════════════════
# 7. 카메라
# ══════════════════════════════════════════════════════════════════════════════

def update_follow_camera(
    cam: f3d.OrbitCamera,
    car: f3d.Body,
    alpha: float = 0.12,
) -> None:
    """OrbitCamera를 차 뒤에서 부드럽게 추적하도록 갱신한다."""
    R       = quat_to_rot(car.orientation)
    forward = R[:, 0]
    yaw_deg = math.degrees(math.atan2(forward[1], forward[0]))

    # target은 차 위치로 즉시 이동
    cam.target = car.position + np.array([0, 0, 0.3])

    # azimuth는 차 방향 뒤쪽으로 부드럽게 따라감
    desired_az = yaw_deg + 180.0   # 차 후방
    diff = (desired_az - cam.azimuth + 180) % 360 - 180
    cam.azimuth += diff * alpha


# ══════════════════════════════════════════════════════════════════════════════
# 8. 메인 루프
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    # ── 씬 구성 ──────────────────────────────────────────────────────────────
    world = f3d.World(gravity=(0, 0, -9.81))
    build_track(world)
    car, wheels, cargo = build_car(world)
    bumpers, pylons = build_obstacles(world, car)

    game = GameState()
    build_pickups_and_checkpoints(world, car, game)

    # ── 충돌 이벤트: 충돌 데미지 + 화물 분리 ─────────────────────────────────
    cargo_attached = [True]

    @world.on_collision_begin
    def on_hit(event: f3d.CollisionEvent) -> None:
        names = {event.body_a.name, event.body_b.name}
        if "car" not in names:
            return
        if event.relative_speed > 2.0:
            game.damage += event.relative_speed * 0.3
        if (cargo_attached[0]
                and event.relative_speed >= CARGO_DETACH_SPD
                and "cargo" not in names):
            world.release(cargo)
            cargo_attached[0] = False
            game.cargo_lost    = True
            game.score        -= 30

    # 자동차-스피너 핸들러: 충돌할 때마다 점수 차감
    spinner_body = world.get_body("spinner")
    spinner_handler = world.add_collision_handler(car, spinner_body)
    spinner_hit_count = [0]
    def _on_spinner(event: f3d.CollisionEvent) -> None:
        spinner_hit_count[0] += 1
        game.score -= 20
        game.damage += 5
    spinner_handler.on_begin = _on_spinner

    # ── StateRecorder: 레이스 전체 기록 ──────────────────────────────────────
    state_rec = StateRecorder(world)
    state_rec.start()

    # ── 카메라 ───────────────────────────────────────────────────────────────
    orbit_cam = f3d.OrbitCamera(
        target=car.position.tolist(),
        distance=12.0,
        azimuth=180.0,
        elevation=22.0,
        fov_deg=55.0,
    )
    cam_mode_follow = True   # True = 추적, False = 자유 orbit

    # ── 렌더러 ───────────────────────────────────────────────────────────────
    renderer = WindowRenderer(W, H, "Forge Racer — pyforge3d 🏎")
    renderer.init()

    clock      = pygame.time.Clock()
    phys_accum = 0.0
    prev_time  = time.perf_counter()
    save_path  = Path("/tmp/forge_racer_state.json")
    drag_active = False
    prev_mouse  = (0, 0)

    # ── 게임 루프 ─────────────────────────────────────────────────────────────
    running = True
    while running:
        now      = time.perf_counter()
        dt_real  = min(now - prev_time, 0.05)
        prev_time = now

        # ── pygame 이벤트 ─────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_r:
                    # 차를 시작 위치로 리셋
                    start_pos = (0.0, -(INNER_HD + (OUTER_HD - INNER_HD) / 2), 0.5)
                    world.teleport(car, start_pos, quat=(1, 0, 0, 0))
                    car.set_velocity((0, 0, 0))
                    car.set_angular_velocity((0, 0, 0))
                    if game.phase == GameState.FINISHED:
                        # 전체 재시작
                        game.__init__()
                        state_rec.start()

                elif event.key == pygame.K_c:
                    cam_mode_follow = not cam_mode_follow

                elif event.key == pygame.K_F5:
                    world.save(save_path)
                    print(f"\n  [저장됨] {save_path}")

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 3:   # 우클릭
                    drag_active = True
                    prev_mouse  = event.pos
                elif event.button == 4:  # 스크롤 업
                    orbit_cam.zoom(1.5)
                elif event.button == 5:  # 스크롤 다운
                    orbit_cam.zoom(-1.5)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3:
                    drag_active = False

            elif event.type == pygame.MOUSEMOTION:
                if drag_active and not cam_mode_follow:
                    dx = event.pos[0] - prev_mouse[0]
                    dy = event.pos[1] - prev_mouse[1]
                    orbit_cam.rotate(d_azimuth=dx * 0.4, d_elevation=-dy * 0.4)
                prev_mouse = event.pos

        # ── 입력 ─────────────────────────────────────────────────────────────
        keys = pygame.key.get_pressed()

        # ── 물리 스텝 ─────────────────────────────────────────────────────────
        phys_accum += dt_real
        steps = 0
        while phys_accum >= DT and steps < 3:
            apply_car_physics(world, car, keys, game)
            world.step(DT)
            state_rec.record()
            phys_accum -= DT
            steps += 1
        if steps >= 3:
            phys_accum = 0.0

        # ── 게임 상태 갱신 ────────────────────────────────────────────────────
        game.update(dt_real)

        # 수면 중인 파일론 수 (디버그 — HUD에 추가 시 활성화)
        # sum(1 for p in pylons if p.is_sleeping)

        # ── 카메라 갱신 ───────────────────────────────────────────────────────
        if cam_mode_follow:
            update_follow_camera(orbit_cam, car)

        cam_snap = orbit_cam.to_snapshot()
        cam_eye  = cam_snap.position
        cam_tgt  = cam_snap.target

        # ── 렌더 ─────────────────────────────────────────────────────────────
        speed = float(np.linalg.norm(car.velocity))
        snap  = world.snapshot()
        renderer.render(snap, cam_eye, cam_tgt, fov=orbit_cam.fov_deg)

        if game.phase == GameState.FINISHED:
            renderer.render_hud(game.gameover_line(), game_over=True)
        else:
            renderer.render_hud(game.hud_line(speed))

        pygame.display.flip()
        clock.tick(FPS)

    # ── 종료 처리 ─────────────────────────────────────────────────────────────
    state_rec.stop()

    # 마지막 랩 리플레이 저장
    if state_rec._frames:
        replay_path = Path("/tmp/forge_racer_replay.npz")
        state_rec.save(replay_path)
        size_kb = replay_path.stat().st_size // 1024
        print(f"\n  리플레이 저장: {replay_path} ({size_kb} KB, "
              f"{len(state_rec._frames)} 프레임)")

    # 최종 월드 상태 저장
    world.save(save_path)
    print(f"  월드 상태 저장: {save_path}")

    if game.lap_times:
        print("\n  ─── 레이스 결과 ───")
        for i, t in enumerate(game.lap_times):
            print(f"  랩 {i+1}: {t:.3f}s")
        print(f"  베스트 랩: {game.best_lap:.3f}s")
        print(f"  총 시간: {game.total_time:.3f}s")
        print(f"  최종 점수: {game.score}")
        print(f"  범퍼 충돌: {len(bumpers)}개 중 활성")
        print(f"  스피너 충돌 횟수: {spinner_hit_count[0]}")
        print(f"  픽업 수집: {game.pickup_count}")
        print(f"  누적 데미지: {game.damage:.1f}")

    renderer.close()
    print("\n  Forge Racer 종료.")


if __name__ == "__main__":
    main()
