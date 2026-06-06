"""FPS Battle Royale — main game loop.

Run:
    python -m apps.fps_battleroyal.main

Controls:
    WASD          — move
    Mouse         — look  (cursor is auto-captured on game start)
    Left Mouse    — shoot (hold for auto, tap for semi-auto)
    Right Mouse   — aim-down-sights (narrow FOV)
    Space         — jump  (single jump only — cooldown prevents bunny-hop)
    Shift         — sprint
    R             — reload
    1 / 2 / Scroll— switch weapon slot
    ESC           — release cursor  (ESC again closes window)
"""
from __future__ import annotations

import math
import pathlib
import sys

import numpy as np

if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).parents[2]))

import forge3d as f3d
from forge3d.io import load_obj

from apps.fps_battleroyal.config import (
    BOT_COUNT,
    C_ENEMY,
    C_SKY,
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
from apps.fps_battleroyal.player import Player, create_player
from apps.fps_battleroyal.weapon import shoot_ray
from apps.fps_battleroyal.world_builder import WorldAssets, build_world
from apps.fps_battleroyal.zone import Zone

# ── OBJ asset paths (swap with Kenney / Quaternius assets as desired) ─────────
_ASSET_DIR  = pathlib.Path(__file__).parents[2] / "assets" / "characters"
_SOLDIER_OBJ = _ASSET_DIR / "soldier.obj"


class BattleRoyale:
    """Top-level game controller."""

    WIDTH  = 1280
    HEIGHT = 720

    def __init__(self) -> None:
        print("Initializing Battle Royale…")

        # ── Physics world ─────────────────────────────────────────────────────
        self.world = f3d.World(gravity=GRAVITY)
        self.world.fixed_dt    = 1.0 / 60.0
        self.world.max_substeps = 2

        # ── Map ───────────────────────────────────────────────────────────────
        print("Building map…")
        self.assets: WorldAssets = build_world(self.world)

        # ── Player — inside factory hall ──────────────────────────────────────
        self.player = create_player(self.world, np.array([0.0, -5.0, 1.5]))

        # ── Bots ──────────────────────────────────────────────────────────────
        print(f"Spawning {BOT_COUNT} bots…")
        self.bots: list[Bot] = create_bots(
            self.world, self.assets.bot_spawn_positions, BOT_COUNT
        )

        # ── Bot visual bodies (OBJ soldier mesh) ──────────────────────────────
        # Each bot has a PLAIN CAPSULE for physics (fast) + a MESH BODY for
        # visuals (static, no collision).  The capsule names are excluded from
        # rendering; the mesh bodies follow the capsule position each frame.
        self._bot_visual: list[f3d.Body] = self._create_bot_visuals()
        # Exclude capsule physics bodies from rendering
        bot_physics_names = {f"bot_{i:02d}" for i in range(len(self.bots))}
        self._render_excluded = {"player_local"} | bot_physics_names

        # ── Zone ──────────────────────────────────────────────────────────────
        self.zone = Zone()
        self._last_zone_radius = ZONE_PHASES[0][1]

        # ── RNG ───────────────────────────────────────────────────────────────
        self._rng = np.random.default_rng(42)

        # ── Game state ────────────────────────────────────────────────────────
        self.game_time        = 0.0
        self.game_over        = False
        self.victory          = False
        self._cursor_captured = False
        self._bot_update_idx  = 0

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
        self.viewer.set_excluded_names(self._render_excluded)

        # ── HUD ───────────────────────────────────────────────────────────────
        self.hud = HUD(self.WIDTH, self.HEIGHT)

        print("Ready — window will open momentarily.")

    # ── Visual bot bodies ─────────────────────────────────────────────────────

    def _create_bot_visuals(self) -> list[f3d.Body]:
        """Load the soldier OBJ and create one visual mesh body per bot."""
        enemy_mat = f3d.Material(
            color=C_ENEMY, roughness=0.35, metallic=0.25
        )

        if _SOLDIER_OBJ.exists():
            mesh = load_obj(str(_SOLDIER_OBJ))
            print(f"Loaded soldier mesh: {mesh.n_triangles} tris")
        else:
            mesh = None
            print(f"Warning: {_SOLDIER_OBJ} not found — bots will render as capsules")

        bodies: list[f3d.Body] = []
        for i, bot in enumerate(self.bots):
            pos = bot.position
            if mesh is not None:
                body = self.world.add_mesh(
                    mesh,
                    position=(pos[0], pos[1], pos[2]),
                    mass=0,         # static — no physics simulation
                    static=True,
                    material=enemy_mat,
                    name=f"bot_vis_{i:02d}",
                )
                # No collision for visual body
                body.collision_layer = 0
                body.collision_mask  = 0
            else:
                # Fallback: render capsule with enemy colour
                body = self.world.add_capsule(
                    radius=PLAYER_RADIUS,
                    half_length=max(0.01, PLAYER_HEIGHT / 2.0 - PLAYER_RADIUS),
                    position=(pos[0], pos[1], pos[2]),
                    static=True,
                    material=enemy_mat,
                    name=f"bot_vis_{i:02d}",
                )
                body.collision_layer = 0
                body.collision_mask  = 0
            bodies.append(body)
        return bodies

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        # Auto-capture cursor on the first rendered frame
        _first_render = True

        while self.viewer.is_open:
            dt  = max(1e-4, min(self.viewer.dt, 0.05))
            inp = self.viewer.input

            # ── Auto-capture cursor ────────────────────────────────────────────
            if _first_render and self.viewer.frame_count > 0:
                self.viewer.set_cursor_captured(True)
                self._cursor_captured = True
                _first_render = False

            # ── Re-capture on click (in case user pressed ESC) ─────────────────
            if inp.mouse_button(0) and not self._cursor_captured:
                self.viewer.set_cursor_captured(True)
                self._cursor_captured = True

            # Detect cursor release (ESC handled inside renderer; we sync flag)
            if self._cursor_captured and self.viewer._renderer is not None:
                if not getattr(self.viewer._renderer, "_cursor_captured", True):
                    self._cursor_captured = False

            # ── Game update ────────────────────────────────────────────────────
            if self._cursor_captured and not self.game_over and not self.victory:
                self._update(dt, inp)

            # ── Physics ────────────────────────────────────────────────────────
            self.world.update(dt)

            # ── Move visual bot bodies to physics positions ────────────────────
            self._sync_bot_visuals()

            # ── Render ────────────────────────────────────────────────────────
            if self.player.is_alive:
                self.viewer.set_camera(self.player.camera.to_snapshot())
            self.viewer.draw()

            # ── HUD ───────────────────────────────────────────────────────────
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

        # Player
        self.player.update(inp, dt, self.world)
        self._handle_player_shoot(inp, dt)

        # Zone
        self.zone.update(dt)
        self._update_zone_pillars()

        # Zone damage
        dmg_ps = self.zone.damage_outside()
        if dmg_ps > 0:
            if not self.zone.is_inside(self.player.position):
                self.player.take_damage(dmg_ps * dt)
            for bot in self.bots:
                if bot.is_alive and not self.zone.is_inside(bot.position):
                    bot.take_damage(dmg_ps * dt * 0.7)

        # Bot AI — staggered: 7 bots per frame
        BOTS_PER_FRAME = 7
        alive_bots = [b for b in self.bots if b.is_alive]
        n = len(alive_bots)
        if n > 0:
            start  = self._bot_update_idx % n
            end    = start + BOTS_PER_FRAME
            subset = (alive_bots[start:end] + alive_bots[:max(0, end - n)])[:BOTS_PER_FRAME]
            self._bot_update_idx = (self._bot_update_idx + BOTS_PER_FRAME) % max(1, n)

            for bot in subset:
                hit = bot.update(
                    dt, self.game_time, self.world,
                    self.player.position, self.player.is_alive,
                    [b for b in alive_bots if b is not bot],
                    self.zone.current_radius, self._rng,
                )
                if hit and self.player.is_alive and bot.target is not None:
                    if bot.target.is_player:
                        dist = float(np.linalg.norm(bot.position - self.player.position))
                        if dist < bot.weapon.data["range"]:
                            self.player.take_damage(bot.weapon.data["damage"] * 0.75)

                # Check if bot shot another bot (bot_ref damage)
                if hit and bot.target is not None and not bot.target.is_player:
                    ref = bot.target.bot_ref
                    if ref is not None and ref.is_alive:
                        ref.take_damage(bot.weapon.data["damage"] * 0.75)
                        if not ref.is_alive:
                            bot.kills += 1
                            self.hud.kill_feed.add(
                                f"bot_{bot.name[-2:]} → {ref.name}", self.game_time
                            )

        # Pickups
        self._check_pickups()

        # Win conditions
        if not self.player.is_alive:
            self.game_over = True
        if self.player.is_alive and sum(1 for b in self.bots if b.is_alive) == 0:
            self.victory = True

    # ── Player shooting ───────────────────────────────────────────────────────

    def _handle_player_shoot(self, inp: f3d.Input, dt: float) -> None:
        weapon = self.player.active_weapon
        if weapon is None:
            return

        # ADS
        if inp.mouse_button(1):
            self.player.camera.fov_deg = max(36.0, self.player.camera.fov_deg - 100 * dt)
        else:
            self.player.camera.fov_deg = min(72.0, self.player.camera.fov_deg + 100 * dt)

        if not inp.mouse_button(0):
            return
        if not weapon.ready:
            return

        cam  = self.player.camera.to_snapshot()
        origin    = np.asarray(cam.position)
        direction = np.asarray(cam.target) - origin
        d_len = float(np.linalg.norm(direction))
        if d_len < 1e-9:
            return
        direction /= d_len

        hit_enemy = False
        for _ in range(weapon.data.get("pellets", 1)):
            result = shoot_ray(
                self.world, origin, direction, weapon, self._rng,
                exclude_name="player_local",
            )
            if result.hit:
                bot = self._find_bot(result.body_name)
                if bot is not None and bot.is_alive:
                    hit_enemy = True
                    bot.take_damage(float(weapon.data["damage"]))
                    if not bot.is_alive:
                        self.player.kills += 1
                        self.hud.kill_feed.add(
                            f"You eliminated {bot.name}", self.game_time
                        )

        weapon.consume()
        if hit_enemy:
            self.hud.on_player_hit_enemy()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _find_bot(self, name: str) -> Bot | None:
        # Bot physics bodies named bot_XX; visual bodies named bot_vis_XX
        # Raycasts hit the physics capsule, so match against bot name
        for bot in self.bots:
            if bot.name == name:
                return bot
        return None

    def _check_pickups(self) -> None:
        ppos = self.player.position
        for pickup in self.assets.pickups:
            if not pickup.active:
                continue
            if float(np.linalg.norm(ppos[:2] - pickup.body.position[:2])) < 2.5:
                if self.player.pick_up_weapon(pickup.weapon_kind):
                    pickup.active = False
                    self.world.remove(pickup.body)
                    self.hud.kill_feed.add(
                        f"Picked up: {WEAPON_DATA[pickup.weapon_kind]['display']}",
                        self.game_time,
                    )

    def _update_zone_pillars(self) -> None:
        r = self.zone.current_radius
        if abs(r - self._last_zone_radius) < 0.3:
            return
        self._last_zone_radius = r
        for i, pillar in enumerate(self.assets.zone_pillars):
            angle = 2 * math.pi * i / ZONE_N_PILLARS
            x = ZONE_CENTER[0] + r * math.cos(angle)
            y = ZONE_CENTER[1] + r * math.sin(angle)
            self.world.teleport(pillar, position=(x, y, 9.0))

    def _sync_bot_visuals(self) -> None:
        """Teleport each visual mesh body to its physics capsule position."""
        for i, (bot, vis) in enumerate(zip(self.bots, self._bot_visual)):
            if bot.is_alive:
                pos = bot.position
                self.world.teleport(vis, position=(pos[0], pos[1], pos[2]))
            else:
                # Sink dead bots underground (remove from view)
                cur = vis.position
                if cur[2] > -5.0:
                    self.world.teleport(vis, position=(cur[0], cur[1], -10.0))


# ── Entry ─────────────────────────────────────────────────────────────────────

def main() -> None:
    game = BattleRoyale()
    game.run()


if __name__ == "__main__":
    main()
