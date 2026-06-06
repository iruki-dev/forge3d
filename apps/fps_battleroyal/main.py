"""FPS Battle Royale — main game loop.

Run:
    python -m apps.fps_battleroyal.main

Controls:
    WASD          — move
    Mouse         — look (click window to capture cursor)
    Left Mouse    — shoot
    Right Mouse   — aim (narrow FOV)
    Space         — jump
    Shift         — sprint
    R             — reload
    1 / 2         — switch weapon slots
    Scroll Wheel  — switch weapon
    ESC           — release cursor  (ESC again closes window)
    Tab           — scoreboard (while held)
"""
from __future__ import annotations

import math
import sys
import time

import numpy as np

# ensure project root is on path when run directly
if __name__ == "__main__":
    import pathlib, sys as _sys
    _sys.path.insert(0, str(pathlib.Path(__file__).parents[2]))

import forge3d as f3d

from apps.fps_battleroyal.config import (
    BOT_COUNT,
    C_ENEMY,
    C_SKY,
    GRAVITY,
    MAP_HALF,
    PLAYER_HEIGHT,
    PLAYER_RADIUS,
    WEAPON_DATA,
    ZONE_CENTER,
    ZONE_N_PILLARS,
    ZONE_PHASES,
)
from apps.fps_battleroyal.enemy import Bot, create_bots
from apps.fps_battleroyal.hud import HUD
from apps.fps_battleroyal.player import Player, create_player
from apps.fps_battleroyal.weapon import WEAPON_DATA as WD, shoot_ray
from apps.fps_battleroyal.world_builder import WorldAssets, build_world
from apps.fps_battleroyal.zone import Zone


class BattleRoyale:
    """Top-level game object."""

    WIDTH  = 1280
    HEIGHT = 720
    FIXED_PHYSICS_DT = 1.0 / 60.0   # 60 Hz physics (was 120 Hz)

    def __init__(self) -> None:
        print("Initializing Battle Royale...")

        # ── Physics world ─────────────────────────────────────────────────────
        self.world = f3d.World(gravity=GRAVITY)
        self.world.fixed_dt    = self.FIXED_PHYSICS_DT
        self.world.max_substeps = 2   # 2 sub-steps (was 4)

        # ── Build map ─────────────────────────────────────────────────────────
        print("Building map...")
        self.assets: WorldAssets = build_world(self.world)

        # ── Player spawn — inside factory for immediate cover ─────────────────
        # (0, -5, 1.5) is inside the main factory hall, 5 m south of centre
        player_start = np.array([0.0, -5.0, 1.5])
        self.player = create_player(self.world, player_start)

        # ── Bot spawns ─────────────────────────────────────────────────────────
        print(f"Spawning {BOT_COUNT} bots...")
        self.bots: list[Bot] = create_bots(
            self.world, self.assets.bot_spawn_positions, BOT_COUNT
        )

        # ── Bot stagger index (spread AI updates across frames) ───────────────
        self._bot_update_idx = 0

        # ── Zone ──────────────────────────────────────────────────────────────
        self.zone = Zone()

        # ── RNG ───────────────────────────────────────────────────────────────
        self._rng = np.random.default_rng(42)

        # ── Game state ────────────────────────────────────────────────────────
        self.game_time    = 0.0
        self.is_running   = True
        self.game_over    = False
        self.victory      = False
        self._cursor_captured = False
        self._prev_mouse_held = False
        self._last_zone_radius = ZONE_PHASES[0][1]  # track radius for pillar update

        # ── Viewer ────────────────────────────────────────────────────────────
        self.viewer = f3d.Viewer(
            self.world,
            width=self.WIDTH,
            height=self.HEIGHT,
            title="Battle Royale  —  forge3d",
            fps=60,
            shadow_resolution=1024,
            sky_color=C_SKY,
        )
        # Don't render the local player's body (FPS mode)
        self.viewer.set_excluded_names({"player_local"})

        # ── HUD ───────────────────────────────────────────────────────────────
        self.hud = HUD(self.WIDTH, self.HEIGHT)

        print("Ready. Click the window to start.")

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        while self.viewer.is_open:
            dt = max(1e-4, min(self.viewer.dt, 0.05))
            inp = self.viewer.input

            # ── Cursor capture toggle ──────────────────────────────────────────
            if inp.mouse_button(0) and not self._prev_mouse_held and not self._cursor_captured:
                self.viewer.set_cursor_captured(True)
                self._cursor_captured = True
            self._prev_mouse_held = inp.mouse_button(0)

            # Detect ESC releasing cursor
            if self._cursor_captured:
                # InputBuilder sees ESC before renderer — if cursor not captured the
                # renderer closes the window instead. Check via key state each frame.
                pass  # cursor release handled in window renderer

            # ── Game update ────────────────────────────────────────────────────
            if self._cursor_captured and not self.game_over and not self.victory:
                self._update(dt, inp)

            # ── Physics ────────────────────────────────────────────────────────
            self.world.update(dt)

            # ── Render ─────────────────────────────────────────────────────────
            if self.player.is_alive:
                self.viewer.set_camera(self.player.camera.to_snapshot())
            self.viewer.draw()

            # ── HUD ────────────────────────────────────────────────────────────
            alive_count = sum(1 for b in self.bots if b.is_alive)
            if self.player.is_alive:
                alive_count += 1

            self.hud.update(dt)
            self.hud.draw(
                self.viewer,
                self.player,
                self.zone,
                self.bots,
                self.game_time,
                alive_count,
                game_over=self.game_over,
                victory=self.victory,
                cursor_captured=self._cursor_captured,
            )

        self.viewer.close()

    # ── Update ────────────────────────────────────────────────────────────────

    def _update(self, dt: float, inp: f3d.Input) -> None:
        self.game_time += dt

        # ── Player update ─────────────────────────────────────────────────────
        self.player.update(inp, dt, self.world)

        # ── Player shooting ────────────────────────────────────────────────────
        self._handle_player_shoot(inp, dt)

        # ── Zone update ────────────────────────────────────────────────────────
        self.zone.update(dt)
        self._update_zone_pillars()

        # ── Zone damage ────────────────────────────────────────────────────────
        dmg_ps = self.zone.damage_outside()
        if dmg_ps > 0:
            if not self.zone.is_inside(self.player.position):
                self.player.take_damage(dmg_ps * dt)
            for bot in self.bots:
                if bot.is_alive and not self.zone.is_inside(bot.position):
                    bot.take_damage(dmg_ps * dt * 0.7)  # bots survive longer

        # ── Bot AI (staggered: update N bots per frame, cycling through all) ───
        # With 19 bots and BOTS_PER_FRAME=7, each bot is updated ~every 3 frames.
        # Movement stays smooth because cc.move() is still called every frame
        # (the expensive LoS raycast is already throttled inside bot.update).
        BOTS_PER_FRAME = 7
        alive_bots = [b for b in self.bots if b.is_alive]
        n = len(alive_bots)
        if n > 0:
            start = self._bot_update_idx % n
            subset = alive_bots[start : start + BOTS_PER_FRAME]
            if start + BOTS_PER_FRAME > n:
                subset += alive_bots[: (start + BOTS_PER_FRAME) - n]
            self._bot_update_idx = (self._bot_update_idx + BOTS_PER_FRAME) % max(1, n)

            for bot in subset:
                hit = bot.update(
                    dt,
                    self.game_time,
                    self.world,
                    self.player.position,
                    self.player.is_alive,
                    [],   # skip other-bot list (costly list comp every frame)
                    self.zone.current_radius,
                    self._rng,
                )
                if hit and self.player.is_alive:
                    origin     = bot.eye_pos
                    player_pos = self.player.position + np.array([0, 0, 1.0])
                    dist = float(np.linalg.norm(player_pos - origin))
                    if dist < bot.weapon.data["range"]:
                        self.player.take_damage(bot.weapon.data["damage"] * 0.8)

        # ── Pickup detection ──────────────────────────────────────────────────
        self._check_pickups()

        # ── Remove dead bot bodies from vision (don't remove physics) ─────────
        # (bodies stay for now — would need corpse management)

        # ── Win condition ─────────────────────────────────────────────────────
        if not self.player.is_alive:
            self.game_over = True

        alive_bots = sum(1 for b in self.bots if b.is_alive)
        if self.player.is_alive and alive_bots == 0:
            self.victory = True

    def _handle_player_shoot(self, inp: f3d.Input, dt: float) -> None:
        """Handle left-mouse fire and aim-down-sights (right mouse)."""
        weapon = self.player.active_weapon
        if weapon is None:
            return

        # ADS — narrow FOV
        if inp.mouse_button(1):
            self.player.camera.fov_deg = max(35.0, self.player.camera.fov_deg - 90 * dt)
        else:
            self.player.camera.fov_deg = min(72.0, self.player.camera.fov_deg + 90 * dt)

        # Fire
        fire_key = inp.mouse_button(0)
        if weapon.is_auto:
            wants_fire = fire_key
        else:
            # Semi-auto: only fire on new press
            wants_fire = inp.mouse_button(0) and not hasattr(self, '_prev_lmb_fire')
        # Simpler: always check current held state, cooldown prevents spam
        wants_fire = fire_key

        if wants_fire and weapon.ready:
            cam_snap = self.player.camera.to_snapshot()
            origin    = np.asarray(cam_snap.position)
            direction = np.asarray(cam_snap.target) - origin
            d_len = float(np.linalg.norm(direction))
            if d_len > 1e-9:
                direction /= d_len

            pellets = weapon.data.get("pellets", 1)
            hit_enemy = False
            for _ in range(pellets):
                result = shoot_ray(
                    self.world, origin, direction, weapon, self._rng,
                    exclude_name="player_local",
                )
                if result.hit:
                    # Check if hit a bot
                    hit_bot = self._find_bot_by_name(result.body_name)
                    if hit_bot is not None and hit_bot.is_alive:
                        hit_enemy = True
                        dmg = weapon.data["damage"]
                        hit_bot.take_damage(float(dmg))
                        if not hit_bot.is_alive:
                            self.player.kills += 1
                            self.hud.kill_feed.add(
                                f"You → {hit_bot.name}",
                                self.game_time,
                            )

            weapon.consume()
            if hit_enemy:
                self.hud.on_player_hit_enemy()

    def _find_bot_by_name(self, name: str) -> Bot | None:
        for bot in self.bots:
            if bot.name == name:
                return bot
        return None

    def _check_pickups(self) -> None:
        player_pos = self.player.position
        for pickup in self.assets.pickups:
            if not pickup.active:
                continue
            dist = float(np.linalg.norm(player_pos[:2] - pickup.body.position[:2]))
            if dist < 2.5:
                if self.player.pick_up_weapon(pickup.weapon_kind):
                    pickup.active = False
                    self.world.remove(pickup.body)
                    self.hud.kill_feed.add(
                        f"Picked up: {WEAPON_DATA[pickup.weapon_kind]['display']}",
                        self.game_time,
                    )

    def _update_zone_pillars(self) -> None:
        """Move zone pillars only when the radius has changed by ≥ 0.3 m."""
        r = self.zone.current_radius
        if abs(r - self._last_zone_radius) < 0.3:
            return
        self._last_zone_radius = r
        for i, pillar in enumerate(self.assets.zone_pillars):
            angle = 2 * math.pi * i / ZONE_N_PILLARS
            x = ZONE_CENTER[0] + r * math.cos(angle)
            y = ZONE_CENTER[1] + r * math.sin(angle)
            self.world.teleport(pillar, position=(x, y, 9.0))


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    game = BattleRoyale()
    game.run()


if __name__ == "__main__":
    main()
