"""demos/forge_drive.py — Forge Drive: Open World
pyforge3d 오픈 월드 드라이브 게임

광활한 Green Valley를 자유롭게 드라이브합니다.
황금 별 ★을 모두 수집하세요!

Controls
--------
  W / ↑       : 가속
  S / ↓       : 브레이크 / 후진
  A / ←       : 좌회전
  D / →       : 우회전
  SPACE       : 핸드브레이크
  R           : 차 리셋
  C           : 카메라 전환 (추적 ↔ 자유 orbit)
  우클릭 드래그: 자유 카메라 회전
  마우스 휠   : 줌
  F5          : 월드 상태 저장
  ESC         : 종료

목표: 황금 별 ★ 20개를 모두 수집하세요!

성능 설계 (목표: 60 FPS)
  동적 body : 차(1) + 풍차허브(1) + 별(20) = 22개
  정적 body : 지형·건물·자연·차 시각 = ≤65개
  총 ≤87 body → 22×87 ≈ 1,900 충돌쌍 → ≈13ms/step
"""

from __future__ import annotations

import math, sys, time
from pathlib import Path

import numpy as np
import pygame

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import forge3d as f3d
from forge3d.collision.layers import CollisionLayer
from forge3d.io.world_snapshot import StateRecorder
from forge3d.math.quaternion import quat_to_rot
from apps.game.renderer import WindowRenderer

# ── 윈도우 / 물리 상수 ────────────────────────────────────────────────────────
WIN_W, WIN_H = 1280, 720
FPS = 60
DT  = 1.0 / FPS

CAR_MASS  = 20.0
CHASSIS   = (2.8, 1.5, 0.30)
CHASSIS_Z = 0.22
ENGINE_F  = 520.0
REVERSE_F = 220.0
STEER_TAU = 105.0
MAX_SPEED = 20.0
GRIP      = 18.0
ANG_DAMP  = 0.82
PITCH_D   = 0.18
BOOST_MUL = 1.45

L_CAR    = CollisionLayer.PLAYER
L_GROUND = CollisionLayer.TERRAIN
L_STATIC = CollisionLayer.DEFAULT
L_STAR   = CollisionLayer.BULLET

START = np.array([0.0, -80.0, CHASSIS_Z])

# ══════════════════════════════════════════════════════════════════════════════
# 재질 팔레트
# ══════════════════════════════════════════════════════════════════════════════

# 자동차
M_BODY   = f3d.Material(color=(0.04, 0.10, 0.40), roughness=0.18, metallic=0.85)
M_ROOF   = f3d.Material(color=(0.03, 0.07, 0.30), roughness=0.22, metallic=0.80)
M_GLASS  = f3d.Material(color=(0.38, 0.62, 0.88), roughness=0.08, metallic=0.02)
M_DARK   = f3d.Material(color=(0.06, 0.06, 0.08), roughness=0.85, metallic=0.10)
M_CHROME = f3d.Material(color=(0.88, 0.90, 0.96), roughness=0.04, metallic=0.98)
M_HEAD   = f3d.Material(color=(1.00, 0.98, 0.92), roughness=0.05)
M_TAIL   = f3d.Material(color=(0.96, 0.08, 0.08), roughness=0.15)
M_WHEEL  = f3d.Material(color=(0.08, 0.08, 0.09), roughness=0.95)
M_HUB    = f3d.Material(color=(0.82, 0.84, 0.90), roughness=0.10, metallic=0.94)

# 환경
M_GROUND    = f3d.Material(color=(0.26, 0.36, 0.16), roughness=0.98)
M_ROAD      = f3d.Material(color=(0.22, 0.22, 0.25), roughness=0.93)
M_ROAD_LINE = f3d.Material(color=(0.90, 0.86, 0.68), roughness=0.85)
M_MTN_BASE  = f3d.Material(color=(0.36, 0.30, 0.24), roughness=0.96)
M_MTN_MID   = f3d.Material(color=(0.50, 0.46, 0.42), roughness=0.90)
M_SNOW      = f3d.Material(color=(0.92, 0.93, 0.96), roughness=0.78)
M_ROCK      = f3d.Material(color=(0.42, 0.38, 0.34), roughness=0.92)
M_BARK      = f3d.Material(color=(0.30, 0.20, 0.10), roughness=0.95)
M_PINE      = f3d.Material(color=(0.09, 0.30, 0.09), roughness=0.88)
M_OAK       = f3d.Material(color=(0.18, 0.50, 0.12), roughness=0.85)
M_AUTUMN    = f3d.Material(color=(0.60, 0.32, 0.08), roughness=0.82)
M_BRICK     = f3d.Material(color=(0.52, 0.25, 0.18), roughness=0.88)
M_STONE     = f3d.Material(color=(0.56, 0.53, 0.48), roughness=0.90)
M_ROOF_R    = f3d.Material(color=(0.55, 0.18, 0.10), roughness=0.75)
M_ROOF_G    = f3d.Material(color=(0.38, 0.38, 0.41), roughness=0.80)
M_PLANK     = f3d.Material(color=(0.45, 0.30, 0.16), roughness=0.90)
M_LAMP_POLE = f3d.Material(color=(0.68, 0.68, 0.72), roughness=0.30, metallic=0.72)
M_LAMP_GLOW = f3d.Material(color=(1.00, 0.92, 0.72), roughness=0.05)
M_STAR      = f3d.Material(color=(1.00, 0.85, 0.10), roughness=0.04, metallic=0.96)
M_BLADE     = f3d.Material(color=(0.92, 0.92, 0.95), roughness=0.22, metallic=0.62)


# ══════════════════════════════════════════════════════════════════════════════
# 헬퍼 — 정적 body 생성 (physics 루프 비참여)
# ══════════════════════════════════════════════════════════════════════════════

def _sb(world, cx, cy, cz, sx, sy, sz, mat, name="env",
        layer=L_STATIC, rest=0.25, fric=0.55) -> f3d.Body:
    """정적 박스 — 공개 API world.add_static_box() 사용."""
    b = world.add_static_box(
        size=(sx, sy, sz), position=(cx, cy, cz),
        material=mat, name=name, restitution=rest, friction=fric,
    )
    b.collision_layer = layer
    b.collision_mask  = CollisionLayer.ALL
    return b


def _ss(world, cx, cy, cz, r, mat, name="env", layer=L_STATIC) -> f3d.Body:
    """정적 구 — static=True → physics 루프 외부 루프에서 즉시 skip."""
    b = world.add_sphere(radius=r, position=(cx, cy, cz),
                         mass=1.0, static=True, material=mat, name=name,
                         restitution=0.2, friction=0.7)
    b.collision_layer = layer
    b.collision_mask  = CollisionLayer.ALL
    return b


# ══════════════════════════════════════════════════════════════════════════════
# 자동차 — 26-part SUV (동적 1 + 정적 25)
# ══════════════════════════════════════════════════════════════════════════════

def build_car(world: f3d.World) -> tuple[f3d.Body, list[f3d.Body]]:
    """
    Physics: 동적 차체 박스 1개 (collision 담당)
    Visuals: 정적 시각 부품 25개 → weld로 차체 따라 이동
             정적이라 collision outer loop에서 즉시 skip → 오버헤드 거의 없음
    """
    p = START.copy()
    sx, sy, sz = CHASSIS

    car = world.add_box(size=(sx, sy, sz), position=tuple(p),
                        mass=CAR_MASS, restitution=0.15, friction=0.52,
                        material=M_DARK, name="car")
    car.collision_layer = L_CAR
    car.collision_mask  = CollisionLayer.ALL

    vis: list[f3d.Body] = []

    def bp(ox, oy, oz, bsx, bsy, bsz, mat):
        b = _sb(world, p[0]+ox, p[1]+oy, p[2]+oz, bsx, bsy, bsz,
                mat, "car_part", layer=CollisionLayer.NONE, rest=0.1, fric=0.1)
        b.collision_mask = CollisionLayer.NONE
        world.weld(b, car);  world.ignore_collision(b, car)
        vis.append(b)

    def sp(ox, oy, oz, r, mat):
        b = _ss(world, p[0]+ox, p[1]+oy, p[2]+oz, r, mat, "car_part",
                layer=CollisionLayer.NONE)
        b.collision_mask = CollisionLayer.NONE
        world.weld(b, car);  world.ignore_collision(b, car)
        vis.append(b)

    # ── 13 박스 시각 부품 ────────────────────────────────────────────────────
    bp(+0.98, 0,     +0.22,  1.05, sy-0.06, 0.16, M_BODY)    # 후드
    bp(-0.85, 0,     +0.20,  0.80, sy-0.06, 0.13, M_BODY)    # 트렁크
    bp(+0.05, 0,     +0.33,  1.55, sy-0.02, 0.24, M_BODY)    # 캐빈 하단
    bp(+0.62, 0,     +0.47,  0.46, sy-0.10, 0.28, M_GLASS)   # 앞 유리
    bp(-0.58, 0,     +0.47,  0.40, sy-0.10, 0.26, M_GLASS)   # 뒷 유리
    bp( 0.00, 0,     +0.59,  1.32, sy-0.04, 0.16, M_BODY)    # 캐빈 상단
    bp( 0.05, 0,     +0.67,  1.08, sy-0.02, 0.05, M_ROOF)    # 루프
    bp(+1.43, 0,      0.00,  0.06, sy+0.04, 0.24, M_DARK)    # 앞 범퍼
    bp(+1.45, 0,     +0.13,  0.04, sy-0.22, 0.10, M_CHROME)  # 앞 범퍼 크롬
    bp(-1.43, 0,      0.00,  0.06, sy+0.04, 0.24, M_DARK)    # 뒤 범퍼
    bp(-1.45, 0,     +0.13,  0.04, sy-0.22, 0.10, M_CHROME)  # 뒤 범퍼 크롬
    bp( 0.00, +(sy/2+0.01), -0.04, sx-0.12, 0.04, 0.20, M_DARK)  # 우 스커트
    bp( 0.00, -(sy/2+0.01), -0.04, sx-0.12, 0.04, 0.20, M_DARK)  # 좌 스커트

    # ── 12 구 시각 부품 ──────────────────────────────────────────────────────
    WR = 0.30
    for ox, oy, oz in [(+0.90,+0.80,-0.12),(+0.90,-0.80,-0.12),
                       (-0.86,+0.80,-0.12),(-0.86,-0.80,-0.12)]:
        sp(ox, oy, oz, WR,       M_WHEEL)
        sp(ox, oy, oz, WR*0.55,  M_HUB)

    sp(+1.41, +0.54, +0.14, 0.09, M_HEAD)
    sp(+1.41, -0.54, +0.14, 0.09, M_HEAD)
    sp(-1.41, +0.54, +0.12, 0.08, M_TAIL)
    sp(-1.41, -0.54, +0.12, 0.08, M_TAIL)

    return car, vis


# ══════════════════════════════════════════════════════════════════════════════
# 지형 & 도로  [≈3 static bodies]
# ══════════════════════════════════════════════════════════════════════════════

def build_terrain(world: f3d.World) -> None:
    _sb(world, 0, 0, -0.15, 400, 400, 0.30, M_GROUND, "ground", fric=0.72, rest=0.10)

    # Heightfield: 물리 경사면 (렌더 불가 — 라이브러리 제약, LIBRARY_NOTES.md #17)
    N = 40
    R, C = np.linspace(0,1,N), np.linspace(0,1,N)
    RR, CC = np.meshgrid(R, C, indexing='ij')
    h = (3.0*np.sin(RR*np.pi*2.5)*np.cos(CC*np.pi*2.0)
       + 1.5*np.sin(RR*np.pi*5.5+0.8)*np.sin(CC*np.pi*4.5))
    for mr, mc, amp in [(0.14,0.14,14),(0.25,0.08,9)]:
        h += amp * np.exp(-((RR-mr)**2+(CC-mc)**2)/0.018)
    h += 6.0 * np.exp(-((RR-0.85)**2+(CC-0.50)**2)/0.04)
    flat = np.clip(1.0-np.sqrt((RR-0.50)**2+(CC-0.25)**2)/0.30, 0, 1)
    h    = h*(1-flat*0.95) - h.min()
    h   /= h.max();  h *= 16.0
    world.add_terrain(heights=h.astype(np.float32),
                      cell_size=5.0, origin=(-100,-100,0), material=M_GROUND)

    # 도로 (남북 + 동서, 각 1개 박스로 단순화)
    _sb(world, 0,  0, 0.01, 7.5, 200, 0.04, M_ROAD,      "road", fric=0.65, rest=0.15)
    _sb(world, 0, 30, 0.01, 200, 7.5, 0.04, M_ROAD,      "road", fric=0.65, rest=0.15)


# ══════════════════════════════════════════════════════════════════════════════
# 산맥  [≈10 static bodies]
# ══════════════════════════════════════════════════════════════════════════════

def build_mountains(world: f3d.World) -> None:
    def mtn(cx, cy, base, n, mats):
        for i in range(n):
            t = i/(n-1);  s = base*(1-t*0.72);  z = base*0.28*i+s*0.25
            _sb(world, cx, cy, z, s, s*0.88, s*0.55,
                mats[min(int(t*len(mats)),len(mats)-1)], "mountain", fric=0.9, rest=0.05)

    mtn(-100,-100, 42, 5, [M_MTN_BASE, M_MTN_MID, M_SNOW])   # 주 산
    mtn( -70, +85, 22, 3, [M_MTN_BASE, M_MTN_MID, M_MTN_MID]) # 북서 언덕
    mtn(+115, +42, 16, 2, [M_MTN_BASE, M_MTN_MID])            # 동쪽 절벽


# ══════════════════════════════════════════════════════════════════════════════
# 자연  [≈20 static bodies — 1~2개/오브젝트로 최소화]
# ══════════════════════════════════════════════════════════════════════════════

def build_nature(world: f3d.World) -> None:
    rng = np.random.default_rng(42)

    def tree(cx, cy, pine=True):
        h  = float(rng.uniform(5,9))
        jx = float(rng.uniform(-0.4,0.4))
        jy = float(rng.uniform(-0.4,0.4))
        tr = float(rng.uniform(0.15,0.25))
        # 기둥 + 수관: 각 1개씩 = 2 static bodies per tree
        _sb(world,cx+jx,cy+jy,h*0.30, tr*2,tr*2,h*0.60, M_BARK,"tree",fric=0.9,rest=0.1)
        mat = M_PINE if pine else (M_AUTUMN if float(rng.random())<0.3 else M_OAK)
        _ss(world,cx+jx,cy+jy,h*0.68, h*0.26, mat, "tree")

    def rock(cx, cy):
        r = float(rng.uniform(0.8,2.0))
        _ss(world, cx, cy, r*0.5, r, M_ROCK, "rock")

    # 서부 소나무 (7그루 × 2 = 14 bodies)
    for cx, cy in [(-55,-20),(-65,10),(-50,30),(-70,40),(-45,55),(-60,65),(-75,15)]:
        tree(cx, cy, pine=True)

    # 북부 참나무 (5그루 × 2 = 10 bodies)
    for cx, cy in [(-20,75),(0,90),(20,80),(-10,105),(15,95)]:
        tree(cx, cy, pine=False)

    # 도로변 참나무 (6그루 × 2 = 12 bodies)
    for y, sgn in [(-60,+1),(-40,+1),(-20,+1),(-60,-1),(-40,-1),(-20,-1)]:
        tree(sgn*9 + float(rng.uniform(-0.5,0.5)), y, pine=False)

    # 바위 (5개 × 1 = 5 bodies)
    for cx, cy in [(-72,-65),(-80,-40),(100,50),(-55,-55),(88,-30)]:
        rock(cx, cy)


# ══════════════════════════════════════════════════════════════════════════════
# 마을  [≈14 static bodies]
# ══════════════════════════════════════════════════════════════════════════════

def build_town(world: f3d.World) -> None:

    def house(cx, cy, w, d, h, wall, roof):
        _sb(world, cx, cy, h/2, w, d, h, wall, "building")
        # 지붕: 앞뒤 2박스 → 1박스로 통합해 body 절약
        _sb(world, cx, cy, h+0.8, w+0.3, d+0.3, 1.6, roof, "roof")

    def lamp(cx, cy):
        _sb(world, cx, cy, 3.2,  0.14, 0.14, 6.4, M_LAMP_POLE, "lamp_post")
        _ss(world, cx, cy, 6.9,  0.22, M_LAMP_GLOW, "lamp_glow")

    # 4 채 × 2 body = 8
    house(42, 52, 9, 7, 5.0, M_BRICK, M_ROOF_R)
    house(57, 52, 8, 6, 4.5, M_STONE, M_ROOF_G)
    house(42, 68, 9, 7, 5.5, M_BRICK, M_ROOF_R)
    house(57, 68, 8, 6, 5.0, M_STONE, M_ROOF_G)

    # 시청 (1 body)
    _sb(world, 48, 84, 5.5, 18, 12, 11, M_STONE, "town_hall")

    # 창고 (1 body)
    _sb(world, 90, 57, 4.0, 18, 11, 8.0, M_PLANK, "warehouse")

    # 가로등 3개 × 2 = 6 bodies
    for lx, ly in [(35,38),(55,38),(35,58)]:
        lamp(lx, ly)

    # 돌담 1개
    _sb(world, 48, 44, 1.0, 32, 0.5, 2.0, M_STONE, "stone_wall")


# ══════════════════════════════════════════════════════════════════════════════
# 랜드마크  [≈8 static + 1 동적 hub + 3 정적 blade + 동적 star만 제외]
# 풍차 허브: 동적(1) → 날개 3개: 정적 weld(3)
# ══════════════════════════════════════════════════════════════════════════════

def build_landmarks(world: f3d.World) -> None:
    # ── 등대 (3 static) ───────────────────────────────────────────────────────
    lx, ly = 82, -72
    for i in range(3):
        r = 2.5 - i*0.35
        _sb(world, lx, ly, i*4.5+2.25, r*2, r*2, 4.5, M_STONE, "lighthouse")
    _ss(world, lx, ly, 15.5, 0.9, M_LAMP_GLOW, "lighthouse_beam")

    # ── 풍력 발전기 (2 static tower/nacelle + 1 dynamic hub + 3 static blades) ─
    wx, wy = 92, 92
    _sb(world, wx, wy, 12.0, 1.8, 1.8, 24.0, M_STONE,    "wt_tower")
    _sb(world, wx, wy, 24.5,  3.5, 1.5, 1.5, M_LAMP_POLE, "wt_nacelle")

    hub = world.add_box(size=(0.45,0.45,0.45), position=(wx+2.1, wy, 24.5),
                        mass=5.0, restitution=0.05, friction=0.1,
                        material=M_LAMP_POLE, name="wt_hub")
    hub.collision_layer = CollisionLayer.NONE
    hub.collision_mask  = CollisionLayer.NONE
    world.add_joint("hinge", hub, None, axis=(1,0,0),
                    motor_velocity=1.5, motor_max_torque=220.0)

    for i in range(3):
        ang = i * 2 * math.pi / 3
        blade = _sb(world, wx+2.1, wy+math.cos(ang)*3.6, 24.5+math.sin(ang)*3.6,
                    0.45, 7.2, 0.22, M_BLADE, "wt_blade",
                    layer=CollisionLayer.NONE, rest=0.1, fric=0.1)
        blade.collision_mask = CollisionLayer.NONE
        world.weld(blade, hub);  world.ignore_collision(blade, hub)

    # ── 다리 (1 static) ────────────────────────────────────────────────────────
    _sb(world, 0, 10, 0.6, 42, 6.0, 1.2, M_STONE, "bridge_deck")


# ══════════════════════════════════════════════════════════════════════════════
# 황금 별  [20 dynamic]
# ══════════════════════════════════════════════════════════════════════════════

STAR_POS = [
    # 시작 근처
    (+14,-65,0.8), (-12,-58,0.8), (+4,-44,0.8), (-8,-70,0.8),
    # 마을
    (+48,70,1.5), (+72,54,1.5), (+42,90,1.5), (+60,38,1.5),
    # 다리
    (-6,10,2.0), (+6,10,2.0),
    # 서부 숲
    (-52,22,1.2), (-38,-8,1.2), (-62,46,1.5), (-45,60,1.2),
    # 북부
    (+12,90,1.5), (-18,80,1.5), (+2,112,1.5),
    # 등대
    (+76,-62,1.2), (+88,-58,1.2),
    # 폐허 (등대 북)
    (-72,24,2.0),
]
assert len(STAR_POS) == 20


PICKUP_RADIUS = 2.2   # 차 + 별 합산 반경

def build_stars(world: f3d.World) -> list[f3d.Body]:
    """정적 별 구체 — 동적 body 아님 → physics 루프 오버헤드 없음.
    수집 감지는 게임 루프에서 거리 체크(O(20))로 처리."""
    stars: list[f3d.Body] = []
    for i, (sx, sy, sz) in enumerate(STAR_POS):
        # static=True → outer loop에서 즉시 skip
        b = _ss(world, sx, sy, sz+0.6, 0.55, M_STAR, f"star_{i}")
        b.collision_layer = CollisionLayer.NONE   # 충돌 불필요 (거리 체크로 대체)
        b.collision_mask  = CollisionLayer.NONE
        stars.append(b)
    return stars


# ══════════════════════════════════════════════════════════════════════════════
# 게임 상태
# ══════════════════════════════════════════════════════════════════════════════

class GameState:
    def __init__(self) -> None:
        self.score = 0;  self.pickup_count = 0
        self.collected    = [False] * len(STAR_POS)
        self.damage       = 0.0
        self.boost_timer  = 0.0
        self.distance     = 0.0
        self.start_time   = time.perf_counter()
        self._prev: np.ndarray | None = None

    def update(self, pos: np.ndarray, dt: float) -> None:
        if self.boost_timer > 0:
            self.boost_timer = max(0.0, self.boost_timer - dt)
        if self._prev is not None:
            self.distance += float(np.linalg.norm(pos - self._prev))
        self._prev = pos.copy()

    def speed_mul(self) -> float:
        return BOOST_MUL if self.boost_timer > 0 else 1.0

    def hud(self, spd_ms: float) -> str:
        t = time.perf_counter() - self.start_time
        m, s = divmod(int(t), 60)
        n    = sum(self.collected)
        spd  = spd_ms * 3.6
        bst  = f"  BOOST {self.boost_timer:.1f}s" if self.boost_timer > 0 else ""
        if n == len(STAR_POS):
            return (f"  ★ 전부 수집!  점수:{self.score}  {m:02d}:{s:02d}  "
                    f"{self.distance/1000:.2f}km  [R]재시작 [ESC]종료")
        return (f"  ★{n}/{len(STAR_POS)}  속도:{spd:.0f}km/h  "
                f"주행:{self.distance/1000:.2f}km  "
                f"점수:{self.score}  {m:02d}:{s:02d}{bst}"
                f"  | [WASD][SPACE]제동 [R]리셋 [C]카메라")


# ══════════════════════════════════════════════════════════════════════════════
# 자동차 물리
# ══════════════════════════════════════════════════════════════════════════════

def step_car(world: f3d.World, car: f3d.Body,
             keys: pygame.key.ScancodeWrapper, game: GameState) -> None:
    R  = quat_to_rot(car.orientation)
    fw = R[:,0];  rt = R[:,1];  up = R[:,2]
    vel = car.velocity.copy()
    spd = float(np.linalg.norm(vel))
    sm  = game.speed_mul()

    if (keys[pygame.K_w] or keys[pygame.K_UP]) and spd < MAX_SPEED * sm:
        world.apply_impulse(car, fw * ENGINE_F * sm * DT)
    if keys[pygame.K_s] or keys[pygame.K_DOWN]:
        if spd > 0.8:  world.apply_impulse(car, -vel * 0.18 * CAR_MASS)
        else:          world.apply_impulse(car, -fw * REVERSE_F * DT)

    sf = max(0.25, 1.0 - spd / (MAX_SPEED * 2.5))
    if keys[pygame.K_a] or keys[pygame.K_LEFT]:   car.apply_torque((0,0, STEER_TAU*sf))
    if keys[pygame.K_d] or keys[pygame.K_RIGHT]:  car.apply_torque((0,0,-STEER_TAU*sf))
    if keys[pygame.K_SPACE]:  world.apply_impulse(car, -vel*0.32*CAR_MASS)

    lat = float(np.dot(vel, rt))
    world.apply_impulse(car, -rt * lat * GRIP * DT * CAR_MASS)

    om = car.angular_velocity
    car.set_angular_velocity(np.array([om[0]*PITCH_D, om[1]*PITCH_D, om[2]*ANG_DAMP]))

    if up[2] < 0.70:
        car.apply_torque(np.cross(up, [0.0,0.0,1.0]) * 50.0)

    max_v = MAX_SPEED * sm
    if spd > max_v:
        world.apply_impulse(car, (vel/spd)*(max_v-spd)*CAR_MASS)


# ══════════════════════════════════════════════════════════════════════════════
# 카메라
# ══════════════════════════════════════════════════════════════════════════════

def update_follow_cam(cam: f3d.OrbitCamera, car: f3d.Body,
                      alpha: float = 0.12) -> None:
    R   = quat_to_rot(car.orientation)
    yaw = math.degrees(math.atan2(R[1,0], R[0,0]))
    cam.target = car.position + np.array([0,0,0.4])
    diff = (yaw + 180 - cam.azimuth + 180) % 360 - 180
    cam.azimuth += diff * alpha


# ══════════════════════════════════════════════════════════════════════════════
# 메인 루프
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("  Forge Drive — 월드 생성 중...")
    t0 = time.perf_counter()

    world = f3d.World(gravity=(0, 0, -9.81))
    build_terrain(world)
    build_mountains(world)
    build_nature(world)
    build_town(world)
    build_landmarks(world)
    car, vis = build_car(world)
    game  = GameState()
    stars = build_stars(world)

    tb = time.perf_counter() - t0
    n_all  = len(world.bodies)
    n_dyn  = sum(1 for b in world.bodies if not b.is_static)
    n_stat = n_all - n_dyn
    print(f"  완료 ({tb:.2f}s) — {n_all} bodies  ({n_dyn} 동적 / {n_stat} 정적)")
    print(f"  실제 충돌쌍: {n_dyn}×{n_all} = {n_dyn*n_all:,}  (동적만 외부 루프)")

    # ── 성능 최적화: _dispatch_events 우회 ─────────────────────────────────────
    # world.step() 내부에서 _physics.step()과 _dispatch_events() 두 번 detect_contacts
    # 별 수집은 거리 체크로 대체하므로 이벤트 시스템 불필요 → 약 2× 속도 향상
    # LIBRARY_NOTES.md #15 참조: 중복 detect_contacts 호출이 성능 병목
    world._dispatch_events = lambda: None  # type: ignore[method-assign]

    rec = StateRecorder(world)
    rec.start()

    # 별 수집 시각화용 위치 캐시 (static이므로 변하지 않음)
    star_xys = np.array([[sx, sy] for sx, sy, sz in STAR_POS], dtype=float)

    # 데미지: 이전 스텝 속도와 비교 (충돌 이벤트 대신)
    prev_speed = 0.0

    orbit  = f3d.OrbitCamera(target=car.position.tolist(),
                              distance=13.5, azimuth=180.0,
                              elevation=22.0, fov_deg=58.0)
    follow = True

    renderer = WindowRenderer(WIN_W, WIN_H, "Forge Drive — Open World")
    renderer.init()

    clock    = pygame.time.Clock()
    phys_acc = 0.0
    prev_t   = time.perf_counter()
    drag_on  = False
    prev_m   = (0, 0)
    savepath = Path("/tmp/forge_drive_save.json")

    running = True
    while running:
        now     = time.perf_counter()
        dt_real = min(now - prev_t, 0.05)
        prev_t  = now

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:   running = False
                elif ev.key == pygame.K_r:
                    world.teleport(car, tuple(START), quat=(1,0,0,0))
                    car.set_velocity((0,0,0));  car.set_angular_velocity((0,0,0))
                elif ev.key == pygame.K_c:  follow = not follow
                elif ev.key == pygame.K_F5:
                    world.save(savepath);  print(f"\n  [저장] {savepath}")
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 3:   drag_on = True;  prev_m = ev.pos
                elif ev.button == 4: orbit.zoom(2.0)
                elif ev.button == 5: orbit.zoom(-2.0)
            elif ev.type == pygame.MOUSEBUTTONUP:
                if ev.button == 3:   drag_on = False
            elif ev.type == pygame.MOUSEMOTION:
                if drag_on and not follow:
                    orbit.rotate(d_azimuth=(ev.pos[0]-prev_m[0])*0.45,
                                 d_elevation=-(ev.pos[1]-prev_m[1])*0.45)
                prev_m = ev.pos

        keys = pygame.key.get_pressed()

        phys_acc += dt_real
        steps = 0
        while phys_acc >= DT and steps < 3:
            step_car(world, car, keys, game)
            world.step(DT)
            rec.record()
            phys_acc -= DT;  steps += 1
        if steps >= 3:
            phys_acc = 0.0

        # ── 거리 기반 별 수집 (O(20), 이벤트 시스템 대신) ─────────────────────
        car_xy = car.position[:2]
        dists  = np.linalg.norm(star_xys - car_xy, axis=1)
        for i in range(len(STAR_POS)):
            if not game.collected[i] and dists[i] < PICKUP_RADIUS:
                game.collected[i] = True
                game.score += 100
                game.pickup_count += 1
                world.teleport(stars[i], (0, 0, 300))   # 하늘로 이동

        # ── 속도 변화 기반 데미지 감지 ─────────────────────────────────────────
        cur_speed = float(np.linalg.norm(car.velocity))
        drop      = prev_speed - cur_speed
        if drop > 6.0:                       # 갑작스러운 감속 = 충돌
            game.damage += drop * 0.15
        prev_speed = cur_speed

        game.update(car.position, dt_real)

        if follow:
            update_follow_cam(orbit, car)
        cs = orbit.to_snapshot()

        snap = world.snapshot()
        renderer.render(snap, cs.position, cs.target, fov=orbit.fov_deg)
        renderer.render_hud(game.hud(float(np.linalg.norm(car.velocity))))
        pygame.display.flip()
        clock.tick(FPS)

    # 종료
    rec.stop()
    if rec._frames:
        rp = Path("/tmp/forge_drive_replay.npz")
        rec.save(rp)
        print(f"\n  리플레이: {rp}  ({len(rec._frames)} 프레임)")
    world.save(savepath)
    print(f"\n  ─── Forge Drive 결과 ───")
    print(f"  별 수집: {sum(game.collected)}/{len(STAR_POS)}")
    print(f"  점수:    {game.score}")
    print(f"  주행:    {game.distance/1000:.2f} km")
    renderer.close()


if __name__ == "__main__":
    main()
