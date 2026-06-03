"""demos/physics_showcase.py — forge3d 물리 엔진 대규모 쇼케이스.

최적화된 엔진(AABB 브로드페이즈, 벡터화 충돌 감지)으로
수십~수백 개 물체의 실시간 물리 연산을 HQ 영상으로 기록합니다.

장면 구성
---------
  장면 1. 무지개 구 폭포   — 56 개 구 (7색 × 8개), 반발계수별 높이 차이
  장면 2. 피라미드 대붕괴  — 55 개 박스 5층 피라미드 + 볼링공 충돌
  장면 3. 혼돈의 아레나    — 50 개 오브젝트 (구 25 + 박스 25) 벽 있는 경기장

사용법
------
    python demos/physics_showcase.py                     # 기본 (480×320, samples=1)
    python demos/physics_showcase.py --hq                # 고품질 (640×400, samples=2)
    python demos/physics_showcase.py --ultra             # 최고 품질 (800×500, samples=4)
    python demos/physics_showcase.py --output my.mp4    # 파일명 지정
    python demos/physics_showcase.py --scene 2          # 특정 장면만 렌더링
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import imageio
import numpy as np

import forge3d as f3d
from forge3d.render.hq.renderer import HQRenderer

# ── 기본 설정 ────────────────────────────────────────────────────────────────

FPS = 24
# 안정적 스택을 위한 서브스텝: 렌더 프레임당 물리 N회 적분
PHYS_SUBSTEPS = 3
PHYS_DT = 1.0 / (FPS * PHYS_SUBSTEPS)  # ≈ 1/72 s


def _step(world: f3d.World, n: int = PHYS_SUBSTEPS) -> None:
    """렌더 프레임 1개에 해당하는 물리 스텝 수행."""
    for _ in range(n):
        world.step(PHYS_DT)


def _warmup(world: f3d.World, seconds: float) -> None:
    """장면을 정착시키기 위한 pre-simulate (렌더링 없음)."""
    steps = int(seconds / PHYS_DT)
    for _ in range(steps):
        world.step(PHYS_DT)


def _progress(current: int, total: int, label: str = "") -> None:
    bar_w = 32
    filled = int(bar_w * current / total)
    bar = "█" * filled + "░" * (bar_w - filled)
    pct = 100 * current / total
    print(f"\r  {label}: [{bar}] {pct:5.1f}%  ({current}/{total})", end="", flush=True)


# ── 색상 팔레트 ─────────────────────────────────────────────────────────────

RAINBOW_7 = [
    ("red",    0.10),
    ("orange", 0.25),
    ((1.0, 0.9, 0.1), 0.40),   # yellow
    ("green",  0.58),
    ((0.1, 0.7, 1.0), 0.72),   # cyan
    ("blue",   0.84),
    ((0.7, 0.2, 0.9), 0.95),   # violet
]

LEVEL_COLORS = ["gold", "orange", "red", "green", "blue"]

CHAOS_COLORS = [
    "red", "orange", "green", "blue", (0.9, 0.7, 0.1),
    (0.1, 0.8, 0.8), (0.9, 0.3, 0.6), "white", (0.5, 0.9, 0.3),
    (0.7, 0.5, 0.9), "default", (0.3, 0.3, 1.0), (1.0, 0.5, 0.5),
]


# ── 장면 1: 무지개 구 폭포 ────────────────────────────────────────────────────

def scene1_rainbow_waterfall(renderer: HQRenderer, n_frames: int = 144) -> list[np.ndarray]:
    """7색 × 8개 = 56개 구, 반발계수별로 튀어오르는 높이 차이를 시각화."""
    print("  [장면 1/3] 무지개 구 폭포 (56개 구)…")

    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground(material=f3d.Material(color="ground"))

    COLS = 8
    spacing_x = 0.38
    spacing_y = 0.40

    for row_i, (color, e) in enumerate(RAINBOW_7):
        drop_z = 5.0 + row_i * 0.5          # 무지개 열마다 살짝 다른 높이
        for col_i in range(COLS):
            x = (col_i - (COLS - 1) / 2) * spacing_x
            y = (row_i - 3) * spacing_y
            world.add_sphere(
                radius=0.13,
                position=(x, y, drop_z),
                mass=0.4,
                restitution=e,
                friction=0.25,
                material=f3d.Material(color=color),
            )

    # 카메라: 옆에서 바라봐 높이 차이가 잘 보이도록
    world.set_camera(position=(0, -9.5, 4.0), target=(0, 0, 2.0))

    frames: list[np.ndarray] = []
    for i in range(n_frames):
        _step(world)
        frames.append(renderer.render(world.snapshot()))
        _progress(i + 1, n_frames, "    무지개 구 폭포")

    print(f"  → {len(world._physics._bodies) - 1}개 구 물리 연산 완료")
    print()
    return frames


# ── 장면 2: 피라미드 대붕괴 ─────────────────────────────────────────────────

def scene2_pyramid_collapse(renderer: HQRenderer, n_frames: int = 192) -> list[np.ndarray]:
    """55개 박스 5층 피라미드 + 볼링공 충돌 대붕괴."""
    print("  [장면 2/3] 피라미드 대붕괴 (55개 박스 + 볼링공)…")

    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground(material=f3d.Material(color="ground"))

    BOX_SIZE = 0.50    # 한 변 길이
    half = BOX_SIZE / 2
    gap = 0.01         # 인접 박스 사이 미세 틈 (안정성)

    # 5층 3D 피라미드: 층 k (0=bottom)에 (5-k)×(5-k) 박스
    box_count = 0
    for lvl in range(5):
        n_side = 5 - lvl
        color = f3d.Material(color=LEVEL_COLORS[lvl])
        z = half + lvl * (BOX_SIZE + gap * 0.5)
        offsets = [(j - (n_side - 1) / 2) * (BOX_SIZE + gap) for j in range(n_side)]
        for xi in offsets:
            for yi in offsets:
                world.add_box(
                    size=(BOX_SIZE, BOX_SIZE, BOX_SIZE),
                    position=(xi, yi, z),
                    mass=0.8,
                    restitution=0.15,
                    friction=0.65,
                    material=color,
                )
                box_count += 1

    # 피라미드 정착
    print(f"\n    {box_count}개 박스 배치 완료. 정착 중…", end="", flush=True)
    _warmup(world, 1.5)
    print(" OK")

    # 볼링공: 피라미드 측면 바깥에서 발사
    BALL_RADIUS = 0.40
    BALL_MASS   = 12.0
    LAUNCH_V    = 6.0   # m/s
    ball = world.add_sphere(
        radius=BALL_RADIUS,
        position=(-5.5, 0.0, BALL_RADIUS),
        mass=BALL_MASS,
        restitution=0.10,
        friction=0.30,
        material=f3d.Material(color=(0.15, 0.15, 0.20)),  # dark gray
    )
    world._physics.apply_impulse(ball._id, np.array([LAUNCH_V * BALL_MASS, 0.0, 0.0]))

    # 카메라: 측면 45° 앙각에서 피라미드 전체 조망
    world.set_camera(position=(7, -7, 5.5), target=(0, 0, 1.5))

    frames: list[np.ndarray] = []
    for i in range(n_frames):
        _step(world)
        frames.append(renderer.render(world.snapshot()))
        _progress(i + 1, n_frames, "    피라미드 붕괴  ")

    total_dyn = sum(1 for b in world._physics._bodies if not b.static)
    print(f"  → 동적 물체 {total_dyn}개 (박스 {box_count} + 볼링공 1) 물리 연산 완료")
    print()
    return frames


# ── 장면 3: 혼돈의 아레나 ────────────────────────────────────────────────────

def scene3_chaos_arena(renderer: HQRenderer, n_frames: int = 168) -> list[np.ndarray]:
    """벽 있는 경기장에 구 25 + 박스 25 = 50개 무작위 낙하."""
    print("  [장면 3/3] 혼돈의 아레나 (구 25 + 박스 25 = 50개)…")

    world = f3d.World(gravity=(0, 0, -9.81))
    world.add_ground(material=f3d.Material(color="ground"))

    # 경기장 벽 (4면, 높이 3m)
    ARENA = 4.5
    WALL_H = 3.0
    WALL_T = 0.25
    for px, py, sx, sy in [
        (0,       +ARENA,  ARENA*2, WALL_T),
        (0,       -ARENA,  ARENA*2, WALL_T),
        (+ARENA,  0,       WALL_T,  ARENA*2),
        (-ARENA,  0,       WALL_T,  ARENA*2),
    ]:
        world._physics.add_static_box(
            size=(sx, sy, WALL_H),
            position=(px, py, WALL_H / 2),
            friction=0.3, restitution=0.5,
        )

    rng = np.random.default_rng(2025)
    N_EACH = 25

    # 구 25개
    for i in range(N_EACH):
        r = float(rng.uniform(0.12, 0.22))
        x = float(rng.uniform(-ARENA + r + 0.2, ARENA - r - 0.2))
        y = float(rng.uniform(-ARENA + r + 0.2, ARENA - r - 0.2))
        z = float(rng.uniform(2.5, 7.0))
        color = CHAOS_COLORS[i % len(CHAOS_COLORS)]
        world.add_sphere(
            radius=r,
            position=(x, y, z),
            mass=float(rng.uniform(0.3, 1.2)),
            restitution=float(rng.uniform(0.2, 0.75)),
            friction=float(rng.uniform(0.3, 0.7)),
            material=f3d.Material(color=color),
        )

    # 박스 25개
    for i in range(N_EACH):
        sz = float(rng.uniform(0.28, 0.48))
        x = float(rng.uniform(-ARENA + sz + 0.2, ARENA - sz - 0.2))
        y = float(rng.uniform(-ARENA + sz + 0.2, ARENA - sz - 0.2))
        z = float(rng.uniform(3.5, 8.0))
        color = CHAOS_COLORS[(i + 5) % len(CHAOS_COLORS)]
        world.add_box(
            size=(sz, sz, sz),
            position=(x, y, z),
            mass=float(rng.uniform(0.4, 1.5)),
            restitution=float(rng.uniform(0.1, 0.4)),
            friction=float(rng.uniform(0.4, 0.8)),
            material=f3d.Material(color=color),
        )

    # 카메라: 경기장 위 대각선
    world.set_camera(position=(8, -8, 9), target=(0, 0, 1.5))

    frames: list[np.ndarray] = []
    for i in range(n_frames):
        _step(world)
        frames.append(renderer.render(world.snapshot()))
        _progress(i + 1, n_frames, "    혼돈의 아레나  ")

    total_dyn = sum(1 for b in world._physics._bodies if not b.static)
    print(f"  → 동적 물체 {total_dyn}개 (구 {N_EACH} + 박스 {N_EACH}) 물리 연산 완료")
    print()
    return frames


# ── 배너 ────────────────────────────────────────────────────────────────────

def _banner(width: int, height: int, samples: int, scenes: list[int],
            n_total: int, out: str) -> None:
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║     forge3d — 물리 엔진 대규모 쇼케이스  🎬              ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print("║  AABB 브로드페이즈 + 벡터화 충돌 감지로                  ║")
    print("║  수십~수백 개 물체의 물리 연산을 실시간 처리              ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print("║  장면 1. 무지개 구 폭포  (56개 구, 반발계수 비교)        ║")
    print("║  장면 2. 피라미드 대붕괴 (55개 박스 + 볼링공)            ║")
    print("║  장면 3. 혼돈의 아레나  (구 25 + 박스 25 = 50개)        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(f"  해상도  : {width}×{height}")
    print(f"  샘플수  : {samples} spp")
    print(f"  장면    : {scenes}")
    print(f"  총 프레임: {n_total}  ({n_total/FPS:.0f}초 @ {FPS}fps)")
    print(f"  물리 dt : {PHYS_DT*1000:.1f}ms ({FPS*PHYS_SUBSTEPS}Hz, "
          f"서브스텝×{PHYS_SUBSTEPS})")
    print(f"  출력    : {out}")
    print()


# ── 메인 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="forge3d 물리 대규모 쇼케이스 (AABB + 벡터화 솔버 데모)"
    )
    parser.add_argument("--output", "-o", default="physics_showcase.mp4")
    parser.add_argument("--hq",    action="store_true",
                        help="고품질: 640×400, samples=2")
    parser.add_argument("--ultra", action="store_true",
                        help="최고 품질: 800×500, samples=4 (느림)")
    parser.add_argument("--scene", "-s", type=int, choices=[1, 2, 3],
                        help="특정 장면만 렌더링 (1/2/3)")
    args = parser.parse_args()

    # 품질 설정
    if args.ultra:
        W, H, samples = 800, 500, 4
    elif args.hq:
        W, H, samples = 640, 400, 2
    else:
        W, H, samples = 480, 320, 1

    scene_funcs = {
        1: (scene1_rainbow_waterfall, 144),   # 6초
        2: (scene2_pyramid_collapse,  192),   # 8초
        3: (scene3_chaos_arena,       168),   # 7초
    }

    target_scenes = [args.scene] if args.scene else [1, 2, 3]
    n_total = sum(scene_funcs[s][1] for s in target_scenes)

    _banner(W, H, samples, target_scenes, n_total, args.output)

    t_start = time.perf_counter()
    renderer = HQRenderer(width=W, height=H, samples=samples)

    all_frames: list[np.ndarray] = []
    for s in target_scenes:
        fn, n_f = scene_funcs[s]
        all_frames.extend(fn(renderer, n_frames=n_f))

    renderer.close()

    # 영상 저장
    print(f"  영상 저장 중 → {args.output} …", end="", flush=True)
    writer = imageio.get_writer(args.output, fps=FPS, quality=8)
    for frame in all_frames:
        writer.append_data(frame)
    writer.close()
    print(" 완료")

    elapsed = time.perf_counter() - t_start
    size_kb  = os.path.getsize(args.output) // 1024

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    완료! 🎉                              ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  파일   : {args.output:<46}║")
    print(f"║  크기   : {size_kb} KB{'':<48}║")
    print(f"║  길이   : {len(all_frames)/FPS:.1f}초  ({len(all_frames)}프레임 @ {FPS}fps){'':<20}║")
    print(f"║  렌더   : {elapsed:.0f}초 소요  "
          f"({elapsed/len(all_frames):.1f}초/프레임){'':<20}║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(f"  재생: mpv {args.output}  또는  vlc {args.output}")
    print()


if __name__ == "__main__":
    main()
