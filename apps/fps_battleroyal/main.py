"""FPS Battle Royale — clean game loop, kinematic bots, sphere hit-detection.

Run:
    python -m apps.fps_battleroyal.main

Controls:
    WASD + Mouse   — move and look  (cursor auto-captured on start)
    Left Mouse     — shoot
    Right Mouse    — ADS (aim-down-sights)
    Space          — jump  (single jump, 400ms cooldown)
    Shift          — sprint
    R              — reload
    1 / 2 / Scroll — switch weapon
    ESC            — release mouse  (ESC again = exit)
"""
from __future__ import annotations

import math
import pathlib
import sys

import numpy as np

if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).parents[2]))

from apps.fps_battleroyal.config import (
    BOT_COUNT,
    BOT_HIT_RADIUS,
    C_ENEMY,
    C_SKY,
    GRACE_PERIOD_SEC,
    GRAVITY,
    PLAYER_HEIGHT,
    PLAYER_RADIUS,
    WEAPON_DATA,
    ZONE_CENTER,
    ZONE_N_PILLARS,
    ZONE_PHASES,
)
from apps.fps_battleroyal.enemy import Bot, create_bots
from apps.fps_battleroyal.hud import HUD
from apps.fps_battleroyal.player import create_player
from apps.fps_battleroyal.world_builder import WorldAssets, build_world
from apps.fps_battleroyal.zone import Zone

import forge3d as f3d
from forge3d.io import load_obj

_ASSET_DIR   = pathlib.Path(__file__).parents[2] / "assets" / "characters"
_SOLDIER_OBJ = _ASSET_DIR / "soldier.obj"


# ── Sphere intersection hit detection ─────────────────────────────────────────

def _ray_sphere(
    origin: np.ndarray,
    direction: np.ndarray,
    center: np.ndarray,
    radius: float,
) -> float:
    """Return distance to nearest intersection, or -1 if no hit."""
    oc = origin - center
    b  = float(np.dot(oc, direction))
    c  = float(np.dot(oc, oc)) - radius * radius
    disc = b * b - c
    if disc < 0:
        return -1.0
    t = -b - math.sqrt(disc)
    return t if t > 0.05 else -1.0


def _find_hit_bot(
    origin: np.ndarray,
    direction: np.ndarray,
    bots: list[Bot],
    world: f3d.World,
    max_range: float = 500.0,
) -> tuple[Bot | None, float]:
    """Find the closest bot hit by the ray, blocked by world geometry."""
    # Wall distance
    world_hit = world.raycast(origin, direction, max_dist=max_range)
    wall_dist = world_hit.distance if world_hit else max_range

    best_bot: Bot | None = None
    best_t = wall_dist

    for bot in bots:
        if not bot.is_alive:
            continue
        # Check torso sphere
        torso = bot.position + np.array([0, 0, PLAYER_HEIGHT * 0.5])
        t = _ray_sphere(origin, direction, torso, BOT_HIT_RADIUS)
        if 0 < t < best_t:
            best_t = t
            best_bot = bot
        # Also check head sphere (smaller but bonus hit)
        head = bot.position + np.array([0, 0, PLAYER_HEIGHT * 0.9])
        t2 = _ray_sphere(origin, direction, head, BOT_HIT_RADIUS * 0.5)
        if 0 < t2 < best_t:
            best_t = t2
            best_bot = bot

    return best_bot, best_t


# ── Damage numbers ─────────────────────────────────────────────────────────────

class FloatingNumber:
    def __init__(self, text: str, x: int, y: int, color: tuple, ttl: float = 1.0):
        self.text  = text
        self.x, self.y = x, y
        self.color = color
        self.ttl   = ttl
        self.age   = 0.0

    def update(self, dt: float) -> None:
        self.age += dt
        self.y   -= int(30 * dt)  # float upward

    @property
    def alive(self) -> bool:
        return self.age < self.ttl

    @property
    def alpha(self) -> float:
        return max(0.0, 1.0 - self.age / self.ttl)


# ── Main game class ────────────────────────────────────────────────────────────

class BattleRoyale:
    WIDTH  = 1280
    HEIGHT = 720

    def __init__(self) -> None:
        print("Initializing…")

        # World
        self.world = f3d.World(gravity=GRAVITY)
        self.world.fixed_dt    = 1 / 60
        self.world.max_substeps = 2

        # Map (static geometry only — no bot bodies)
        self.assets: WorldAssets = build_world(self.world)

        # Player
        self.player = create_player(self.world, np.array([0.0, -5.0, 1.5]))

        # Kinematic bots (zero physics bodies)
        self.bots: list[Bot] = create_bots(
            self.world, self.assets.bot_spawn_positions, BOT_COUNT
        )

        # Bot visual bodies (OBJ mesh, static, no collision)
        self._bot_vis: list[f3d.Body] = self._make_bot_visuals()

        # Exclude player capsule + no other bot physics to exclude
        self.viewer = f3d.Viewer(
            self.world, width=self.WIDTH, height=self.HEIGHT,
            title="Battle Royale  —  forge3d",
            fps=60, shadow_resolution=1024, sky_color=C_SKY,
        )
        self.viewer.set_excluded_names({"player_local"})

        # Zone
        self.zone = Zone()
        self._last_zone_r = ZONE_PHASES[0][1]

        # State
        self.game_time    = 0.0
        self.game_over    = False
        self.victory      = False
        self._cursor_cap  = False
        self._first_frame = True
        self._bot_update_idx = 0
        self._rng = np.random.default_rng(42)
        self._floats: list[FloatingNumber] = []

        # HUD
        self.hud = HUD(self.WIDTH, self.HEIGHT)
        print("Ready.")

    # ── Bot visuals ───────────────────────────────────────────────────────────

    def _make_bot_visuals(self) -> list[f3d.Body]:
        mat = f3d.Material(color=C_ENEMY, roughness=0.35, metallic=0.25)
        bodies: list[f3d.Body] = []
        mesh = None
        if _SOLDIER_OBJ.exists():
            mesh = load_obj(str(_SOLDIER_OBJ))

        for i, bot in enumerate(self.bots):
            p = bot.position
            if mesh:
                b = self.world.add_mesh(
                    mesh, position=(p[0], p[1], p[2]),
                    mass=0, static=True, material=mat,
                    name=f"bot_vis_{i:02d}",
                )
            else:
                b = self.world.add_capsule(
                    radius=PLAYER_RADIUS,
                    half_length=max(0.01, PLAYER_HEIGHT / 2 - PLAYER_RADIUS),
                    position=(p[0], p[1], p[2]),
                    static=True, material=mat,
                    name=f"bot_vis_{i:02d}",
                )
            b.collision_layer = 0
            b.collision_mask  = 0
            bodies.append(b)
        return bodies

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        while self.viewer.is_open:
            dt  = float(np.clip(self.viewer.dt, 1e-4, 0.05))
            inp = self.viewer.input

            # Auto-capture cursor on first render
            if self._first_frame and self.viewer.frame_count > 0:
                self.viewer.set_cursor_captured(True)
                self._cursor_cap = True
                self._first_frame = False

            # Re-capture on left click
            if inp.mouse_button(0) and not self._cursor_cap:
                self.viewer.set_cursor_captured(True)
                self._cursor_cap = True

            # Sync cursor flag with renderer
            r = self.viewer._renderer
            if r is not None and self._cursor_cap:
                self._cursor_cap = getattr(r, "_cursor_captured", True)

            # Update
            if self._cursor_cap and not self.game_over and not self.victory:
                self._update(dt, inp)

            # Physics (player only)
            self.world.update(dt)

            # Sync bot visual positions + rotations
            self._sync_visuals()

            # Render
            self.viewer.set_camera(self.player.camera.to_snapshot())
            self.viewer.draw()

            # HUD
            alive = sum(1 for b in self.bots if b.is_alive) + (1 if self.player.is_alive else 0)
            self.hud.update(dt)
            self.hud.draw(
                self.viewer, self.player, self.zone, self.bots,
                self.game_time, alive,
                game_over=self.game_over, victory=self.victory,
                cursor_captured=self._cursor_cap,
            )

            # Damage numbers
            self._draw_floats(dt)

        self.viewer.close()

    # ── Per-frame update ──────────────────────────────────────────────────────

    def _update(self, dt: float, inp: f3d.Input) -> None:
        self.game_time += dt

        # Player
        self.player.update(inp, dt, self.world)
        self._handle_shoot(inp)

        # Zone
        self.zone.update(dt)
        self._update_zone_pillars()

        # Zone damage
        dmg = self.zone.damage_outside()
        if dmg > 0:
            if not self.zone.is_inside(self.player.position):
                self.player.take_damage(dmg * dt)
            for bot in self.bots:
                if bot.is_alive and not self.zone.is_inside(bot.position):
                    bot.take_damage(dmg * dt * 0.6)

        # Bot AI (stagger: ~6 per frame across 19 bots)
        alive_bots = [b for b in self.bots if b.is_alive]
        n = len(alive_bots)
        if n:
            STEP = 6
            start  = self._bot_update_idx % n
            subset = (alive_bots[start:start+STEP] + alive_bots[:max(0, start+STEP-n)])[:STEP]
            self._bot_update_idx = (self._bot_update_idx + STEP) % n

            for bot in subset:
                shot = bot.update(
                    dt, self.game_time, self.world,
                    self.player.position, self.player.is_alive,
                    alive_bots, self.zone.current_radius, self._rng,
                )
                # Bot shot player?
                if shot and bot.target_is_player and self.player.is_alive and self.game_time > GRACE_PERIOD_SEC:
                    self.player.take_damage(bot.weapon.data["damage"] * 0.75)

                # Bot kill bookkeeping
                if not bot.is_alive:
                    pass  # handled inside bot.take_damage

        # Pickups
        self._check_pickups()

        # Win conditions
        if not self.player.is_alive:
            self.game_over = True
        if self.player.is_alive and all(not b.is_alive for b in self.bots):
            self.victory = True

    # ── Player shooting ───────────────────────────────────────────────────────

    def _handle_shoot(self, inp: f3d.Input) -> None:
        wp = self.player.active_weapon
        if not wp:
            return

        # ADS
        if inp.mouse_button(1):
            self.player.camera.fov_target = max(38.0, self.player.camera.fov_deg - 1)
        else:
            self.player.camera.fov_target = 72.0

        if not inp.mouse_button(0):
            return
        if not wp.ready:
            return

        cam = self.player.camera.to_snapshot()
        origin    = np.asarray(cam.position)
        direction = np.asarray(cam.target) - origin
        d_len = float(np.linalg.norm(direction))
        if d_len < 1e-9:
            return
        direction /= d_len

        hit_any = False
        for _ in range(wp.data.get("pellets", 1)):
            # Spread
            spread = wp.data["spread"]
            if spread > 0:
                dx = float(self._rng.normal(0, spread))
                dy = float(self._rng.normal(0, spread))
                right = self.player.camera.right
                up    = np.cross(direction, right)
                fired = direction + dx * right + dy * up
                f_len = float(np.linalg.norm(fired))
                if f_len > 1e-9:
                    fired /= f_len
            else:
                fired = direction

            bot, dist = _find_hit_bot(origin, fired, self.bots, self.world, wp.data["range"])
            if bot is not None:
                dmg = float(wp.data["damage"])
                bot.take_damage(dmg)
                hit_any = True
                # Floating damage number at screen center
                self._floats.append(FloatingNumber(
                    f"-{int(dmg)}", self.WIDTH // 2 + 40, self.HEIGHT // 2 - 10,
                    color=(1.0, 0.8, 0.2),
                ))
                if not bot.is_alive:
                    self.player.kills += 1
                    self.hud.kill_feed.add(f"You eliminated {bot.name}", self.game_time)
                    self._floats.append(FloatingNumber(
                        "KILL", self.WIDTH // 2, self.HEIGHT // 2 - 55,
                        color=(1.0, 0.3, 0.1), ttl=1.5,
                    ))

        wp.consume()
        if hit_any:
            self.hud.on_player_hit_enemy()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _check_pickups(self) -> None:
        ppos = self.player.position
        for pickup in self.assets.pickups:
            if not pickup.active:
                continue
            if float(np.linalg.norm(ppos[:2] - pickup.body.position[:2])) < 2.5:
                self.player.pick_up_weapon(pickup.weapon_kind)
                pickup.active = False
                self.world.remove(pickup.body)
                self.hud.kill_feed.add(
                    f"Picked up: {WEAPON_DATA[pickup.weapon_kind]['display']}",
                    self.game_time,
                )

    def _update_zone_pillars(self) -> None:
        r = self.zone.current_radius
        if abs(r - self._last_zone_r) < 0.3:
            return
        self._last_zone_r = r
        for i, pillar in enumerate(self.assets.zone_pillars):
            a = 2 * math.pi * i / ZONE_N_PILLARS
            self.world.teleport(
                pillar,
                position=(ZONE_CENTER[0] + r * math.cos(a),
                           ZONE_CENTER[1] + r * math.sin(a), 9.0),
            )

    def _sync_visuals(self) -> None:
        """Teleport visual mesh bodies to kinematic bot positions."""
        for bot, vis in zip(self.bots, self._bot_vis):
            if bot.is_alive:
                p = bot.position
                # Quaternion from yaw (rotation around Z)
                hy = bot.yaw / 2
                quat = [math.cos(hy), 0.0, 0.0, math.sin(hy)]
                self.world.teleport(vis, position=(p[0], p[1], p[2]), orientation=quat)
            else:
                cur = vis.position
                if cur[2] > -5:
                    self.world.teleport(vis, position=(cur[0], cur[1], -10.0))

    def _draw_floats(self, dt: float) -> None:
        for fn in self._floats:
            fn.update(dt)
            if fn.alive:
                self.viewer.draw_text(
                    fn.text, fn.x, fn.y, size=28,
                    color=fn.color, bg_alpha=fn.alpha * 0.3, anchor="center",
                )
        self._floats = [f for f in self._floats if f.alive]


# ── Entry ─────────────────────────────────────────────────────────────────────

def main() -> None:
    game = BattleRoyale()
    game.run()


if __name__ == "__main__":
    main()
