"""Forge Ball — 3-D physics bowling game.

Controls
--------
  W / ↑       : roll forward (camera-relative)
  S / ↓       : roll backward
  A           : roll left
  D           : roll right
  ← / →       : rotate camera azimuth
  SPACE       : jump (upward impulse)
  R           : reset ball to centre
  ESC         : quit

Goal: knock as many coloured boxes as possible in 60 seconds.
  Box falls below z = -1.0  →  +10 points
  Gold box                  →  +30 points (3× bonus)

Run::

    cd /workspaces/2026_python_toy_project_1
    python -m apps.game.main
"""

from __future__ import annotations

import math
import sys

import numpy as np
import pygame

sys.path.insert(0, ".")

from apps.game.renderer import WindowRenderer
from apps.game.scene import build_scene

import forge3d as f3d

# ── Constants ─────────────────────────────────────────────────────────────────

WINDOW_W, WINDOW_H = 1024, 768
TARGET_FPS = 60
PHYS_DT = 1.0 / 60.0   # 60 Hz physics — 1 step/frame at target FPS
PHYS_MAX_STEPS = 3      # cap: prevent spiral-of-death when FPS drops
FORCE_SCALE = 14.0  # N applied each frame the key is held
JUMP_IMPULSE = 4.5  # m/s upward impulse
GAME_DURATION = 60.0  # seconds

CAM_DIST = 9.0
CAM_ELEV = 0.42  # radians (≈ 24°)
CAM_AZ_SPEED = 75.0  # degrees / second
CAM_SMOOTH = 0.08  # position lerp factor

FALL_THRESHOLD = -1.0  # z below which a box is counted as knocked off
GOLD_BONUS = 3  # gold boxes worth 3× points
BOX_POINTS = 10


# ── Game state ─────────────────────────────────────────────────────────────────


class GameState:
    def __init__(self) -> None:
        self.score = 0
        self.time_left = GAME_DURATION
        self.over = False
        self.knocked: set[int] = set()  # body_id of already-counted boxes
        self.cam_az = 0.0  # degrees
        self.cam_target = np.array([0.0, 0.0, 0.5], dtype=float)

    def update_score(
        self,
        world: f3d.World,
        targets: list[f3d.Body],
        gold_ids: set[int],
    ) -> None:
        for body in targets:
            if body._id in self.knocked:
                continue
            pos = body.position
            if pos[2] < FALL_THRESHOLD:
                mult = GOLD_BONUS if body._id in gold_ids else 1
                self.score += BOX_POINTS * mult
                self.knocked.add(body._id)


# ── Camera ─────────────────────────────────────────────────────────────────────


def camera_eye(player_pos: np.ndarray, az_deg: float) -> np.ndarray:
    az = math.radians(az_deg)
    dx = CAM_DIST * math.cos(CAM_ELEV) * math.cos(az)
    dy = CAM_DIST * math.cos(CAM_ELEV) * math.sin(az)
    dz = CAM_DIST * math.sin(CAM_ELEV)
    return player_pos + np.array([dx, dy, dz])


# ── Main loop ──────────────────────────────────────────────────────────────────


def main() -> None:
    renderer = WindowRenderer(WINDOW_W, WINDOW_H, "Forge Ball")
    renderer.init()

    world, player, targets = build_scene()
    gold_ids = {b._id for b in targets if "gold" in b._state().material_id}

    state = GameState()
    clock = pygame.time.Clock()
    phys_accum = 0.0

    while True:
        dt_real = clock.tick(TARGET_FPS) / 1000.0
        dt_real = min(dt_real, 0.05)  # cap to 50 ms to avoid spiral-of-death

        # ── Events ─────────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                renderer.close()
                sys.exit(0)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    renderer.close()
                    sys.exit(0)
                if event.key == pygame.K_r:
                    world.teleport(player, (0.0, 0.0, 0.5))
                    world._physics.apply_impulse(
                        player._id, -player.velocity * player._state().mass
                    )
                    if state.over:
                        # Restart game
                        renderer.close()
                        main()
                        return
                if event.key == pygame.K_SPACE and not state.over:
                    # Jump: only if roughly on ground
                    if player.position[2] < 0.8:
                        world.apply_impulse(
                            player,
                            np.array([0.0, 0.0, JUMP_IMPULSE]) * player._state().mass,
                        )

        if state.over:
            # Game over: still render but accept only R/ESC
            snap = world.snapshot()
            renderer.render(snap, camera_eye(player.position, state.cam_az), state.cam_target)
            renderer.render_hud(
                f"Final Score: {state.score}",
                game_over=True,
            )
            pygame.display.flip()
            continue

        # ── Player input ────────────────────────────────────────────────────────
        keys = pygame.key.get_pressed()

        if keys[pygame.K_LEFT]:
            state.cam_az += CAM_AZ_SPEED * dt_real
        if keys[pygame.K_RIGHT]:
            state.cam_az -= CAM_AZ_SPEED * dt_real

        az = math.radians(state.cam_az)
        fwd = np.array([math.cos(az), math.sin(az), 0.0])
        right = np.array([-math.sin(az), math.cos(az), 0.0])

        force = np.zeros(3)
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            force += fwd
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            force -= fwd
        if keys[pygame.K_a]:
            force -= right
        if keys[pygame.K_d]:
            force += right

        fn = np.linalg.norm(force)
        if fn > 1e-6:
            force = force / fn * FORCE_SCALE * PHYS_DT * player._state().mass

        # ── Physics steps ───────────────────────────────────────────────────────
        phys_accum += dt_real
        steps_done = 0
        while phys_accum >= PHYS_DT and steps_done < PHYS_MAX_STEPS:
            if fn > 1e-6:
                world.apply_impulse(player, force)
            world.step(PHYS_DT)
            phys_accum -= PHYS_DT
            steps_done += 1
        # If we hit the cap, discard excess accumulation to stay real-time
        if steps_done >= PHYS_MAX_STEPS:
            phys_accum = 0.0

        # ── Game logic ──────────────────────────────────────────────────────────
        state.time_left -= dt_real
        if state.time_left <= 0.0:
            state.time_left = 0.0
            state.over = True

        state.update_score(world, targets, gold_ids)

        # Smooth camera target
        ppos = player.position.copy()
        ppos[2] += 0.3  # look slightly above ball
        state.cam_target += (ppos - state.cam_target) * min(CAM_SMOOTH * 60 * dt_real, 1.0)

        # ── Render ──────────────────────────────────────────────────────────────
        snap = world.snapshot()
        eye = camera_eye(player.position, state.cam_az)
        renderer.render(snap, eye, state.cam_target)

        # HUD line
        remaining = int(state.time_left)
        knocked = len(state.knocked)
        hud = (
            f"Score: {state.score:4d}   "
            f"Boxes: {knocked}/{len(targets)}   "
            f"Time: {remaining:3d}s   "
            f"[WASD] move  [←→] cam  [SPACE] jump  [R] reset"
        )
        renderer.render_hud(hud)

        pygame.display.flip()


if __name__ == "__main__":
    main()
