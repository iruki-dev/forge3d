"""HUD rendering — health, ammo, zone, crosshair, minimap, kill feed."""
from __future__ import annotations

import math
from collections import deque

from apps.fps_battleroyal.config import (
    HUD_BLUE,
    HUD_GRAY,
    HUD_GREEN,
    HUD_RED,
    HUD_WHITE,
    HUD_YELLOW,
    ZONE_CENTER,
)

import forge3d as f3d


class KillFeed:
    """Scrolling kill event display."""

    def __init__(self, max_entries: int = 5, display_time: float = 4.0) -> None:
        self._entries: deque[tuple[str, float]] = deque(maxlen=max_entries)
        self._display_time = display_time

    def add(self, text: str, game_time: float) -> None:
        self._entries.appendleft((text, game_time))

    def get_active(self, game_time: float) -> list[str]:
        return [
            text for text, t in self._entries
            if game_time - t < self._display_time
        ]


class HUD:
    """Manages and draws all HUD elements."""

    def __init__(self, width: int, height: int) -> None:
        self.W  = width
        self.H  = height
        self.kill_feed = KillFeed()
        self._hit_flash = 0.0   # white flash on hitting enemy

    # ── Per-frame update ──────────────────────────────────────────────────────

    def on_player_hit_enemy(self) -> None:
        self._hit_flash = 0.35

    def update(self, dt: float) -> None:
        if self._hit_flash > 0:
            self._hit_flash = max(0.0, self._hit_flash - dt * 3.0)

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(
        self,
        viewer: f3d.Viewer,
        player: object,    # Player
        zone: object,      # Zone
        bots: list,        # list[Bot]
        game_time: float,
        alive_count: int,
        game_over: bool = False,
        victory: bool = False,
        cursor_captured: bool = False,
    ) -> None:
        W, H = self.W, self.H

        if not cursor_captured:
            self._draw_capture_hint(viewer, W, H)
            return

        if game_over:
            self._draw_death_screen(viewer, W, H)
            return

        if victory:
            self._draw_victory_screen(viewer, W, H)
            return

        # Zone damage overlay (screen edge tint)
        if hasattr(player, 'position') and not zone.is_inside(player.position):
            self._draw_zone_overlay(viewer, W, H, zone, player.position)

        # Damage flash
        if hasattr(player, '_damage_flash') and player._damage_flash > 0:
            alpha = player._damage_flash * 0.45
            viewer.draw_rect(0, 0, W, H, color=(0.85, 0.05, 0.05), alpha=alpha)

        # Hit indicator
        if self._hit_flash > 0:
            viewer.draw_text(
                "×", x=W // 2, y=H // 2 - 30,
                size=28, color=HUD_YELLOW, bg_alpha=0.0, anchor="center",
            )

        # ── Crosshair ────────────────────────────────────────────────────────
        self._draw_crosshair(viewer, W, H, player)

        # ── Bottom-left: health + armor ───────────────────────────────────────
        self._draw_health(viewer, player, W, H)

        # ── Bottom-center: weapon ─────────────────────────────────────────────
        self._draw_weapon(viewer, player, W, H)

        # ── Top-right: alive count + zone ─────────────────────────────────────
        self._draw_status(viewer, alive_count, game_time, zone, W, H)

        # ── Top-left: kill feed ────────────────────────────────────────────────
        self._draw_kill_feed(viewer, game_time, W, H)

        # ── Mini-map ──────────────────────────────────────────────────────────
        self._draw_minimap(viewer, player, bots, zone, W, H)

    # ── Section drawers ───────────────────────────────────────────────────────

    def _draw_capture_hint(self, viewer, W, H):
        viewer.draw_rect(W // 2 - 200, H // 2 - 35, 400, 70, color=(0, 0, 0), alpha=0.7)
        viewer.draw_text(
            "Click to capture mouse  |  ESC to release",
            x=W // 2, y=H // 2,
            size=22, color=HUD_WHITE, bg_alpha=0.0, anchor="center",
        )

    def _draw_death_screen(self, viewer, W, H):
        viewer.draw_rect(0, 0, W, H, color=(0, 0, 0), alpha=0.65)
        viewer.draw_text("ELIMINATED", x=W // 2, y=H // 2 - 30, size=56,
                         color=HUD_RED, bg_alpha=0.0, anchor="center")
        viewer.draw_text("Press ESC to exit", x=W // 2, y=H // 2 + 50, size=22,
                         color=HUD_GRAY, bg_alpha=0.0, anchor="center")

    def _draw_victory_screen(self, viewer, W, H):
        viewer.draw_rect(0, 0, W, H, color=(0, 0, 0), alpha=0.55)
        viewer.draw_text("VICTORY", x=W // 2, y=H // 2 - 30, size=64,
                         color=HUD_YELLOW, bg_alpha=0.0, anchor="center")
        viewer.draw_text("#1 ROYALE", x=W // 2, y=H // 2 + 50, size=28,
                         color=HUD_WHITE, bg_alpha=0.0, anchor="center")
        viewer.draw_text("Press ESC to exit", x=W // 2, y=H // 2 + 100, size=20,
                         color=HUD_GRAY, bg_alpha=0.0, anchor="center")

    def _draw_crosshair(self, viewer, W, H, player):
        cx, cy = W // 2, H // 2
        # Color: green normally, yellow when zoomed
        col = HUD_GREEN
        gap, arm, thick = 7, 14, 2

        if hasattr(player, 'active_weapon') and player.active_weapon:
            spread = player.active_weapon.data.get("spread", 0.04)
            gap = max(5, int(spread * 200))

        # Horizontal arms
        viewer.draw_rect(cx - arm - gap, cy - thick // 2, arm, thick, color=col, alpha=0.9)
        viewer.draw_rect(cx + gap,       cy - thick // 2, arm, thick, color=col, alpha=0.9)
        # Vertical arms
        viewer.draw_rect(cx - thick // 2, cy - arm - gap, thick, arm, color=col, alpha=0.9)
        viewer.draw_rect(cx - thick // 2, cy + gap,       thick, arm, color=col, alpha=0.9)
        # Center dot
        viewer.draw_rect(cx - 1, cy - 1, 3, 3, color=col, alpha=1.0)

    def _draw_health(self, viewer, player, W, H):
        bar_x, bar_y = 20, H - 80
        bar_w, bar_h = 200, 18

        # Background
        viewer.draw_rect(bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4,
                         color=(0, 0, 0), alpha=0.60)

        # HP bar
        hp_frac = player.health_frac if hasattr(player, 'health_frac') else 1.0
        if hp_frac > 0.6:
            bar_col = HUD_GREEN
        elif hp_frac > 0.3:
            bar_col = HUD_YELLOW
        else:
            bar_col = HUD_RED
        viewer.draw_rect(bar_x, bar_y, int(bar_w * hp_frac), bar_h, color=bar_col, alpha=0.85)

        hp_val = int(player.hp) if hasattr(player, 'hp') else 0
        viewer.draw_text(f"HP  {hp_val}", x=bar_x + 4, y=bar_y + 1,
                         size=15, color=HUD_WHITE, bg_alpha=0.0)

        # Armor bar (below HP)
        armor_frac = player.armor_frac if hasattr(player, 'armor_frac') else 0.0
        if armor_frac > 0:
            arm_y = bar_y + bar_h + 4
            viewer.draw_rect(bar_x - 2, arm_y - 1, bar_w + 4, 12,
                             color=(0, 0, 0), alpha=0.55)
            viewer.draw_rect(bar_x, arm_y, int(bar_w * armor_frac), 10,
                             color=HUD_BLUE, alpha=0.75)
            viewer.draw_text(f"ARM {int(player.armor)}", x=bar_x + 4, y=arm_y,
                             size=10, color=HUD_WHITE, bg_alpha=0.0)

        # Kill counter
        kills = player.kills if hasattr(player, 'kills') else 0
        viewer.draw_text(f"Kills: {kills}", x=bar_x, y=H - 105,
                         size=16, color=HUD_WHITE, bg_alpha=0.45)

    def _draw_weapon(self, viewer, player, W, H):
        if not hasattr(player, 'active_weapon') or not player.active_weapon:
            return
        w = player.active_weapon
        cx = W // 2

        # Weapon name
        viewer.draw_text(
            w.display_name,
            x=cx, y=H - 75,
            size=18, color=HUD_WHITE, bg_alpha=0.40, anchor="center",
        )

        # Ammo
        if w.reloading:
            prog = w.reload_elapsed / w.data["reload_s"]
            ammo_str = f"Reloading... {int(prog * 100)}%"
            col = HUD_YELLOW
        else:
            ammo_str = f"{w.ammo}  /  {w.reserve}"
            col = HUD_WHITE if w.ammo > 2 else HUD_RED

        viewer.draw_text(
            ammo_str,
            x=cx, y=H - 48,
            size=22, color=col, bg_alpha=0.40, anchor="center",
        )

        # Slot indicators
        if hasattr(player, 'weapons') and len(player.weapons) > 1:
            for i, ww in enumerate(player.weapons):
                marker = f"[{i + 1}] {ww.display_name[:6]}"
                col_s = HUD_YELLOW if i == player.active_slot else HUD_GRAY
                viewer.draw_text(
                    marker,
                    x=cx - 80 + i * 90, y=H - 28,
                    size=13, color=col_s, bg_alpha=0.35, anchor="center",
                )

    def _draw_status(self, viewer, alive_count, game_time, zone, W, H):
        # Alive count
        viewer.draw_rect(W - 155, 10, 145, 60, color=(0, 0, 0), alpha=0.55)
        viewer.draw_text(
            f"Alive  {alive_count}",
            x=W - 15, y=14,
            size=22, color=HUD_WHITE, bg_alpha=0.0, anchor="topright",
        )

        # Zone info
        ttn = zone.time_to_next_shrink() if hasattr(zone, 'time_to_next_shrink') else None
        if ttn is not None:
            mins = int(ttn) // 60
            secs = int(ttn) % 60
            phase = getattr(zone, 'phase', 0)
            viewer.draw_text(
                f"Zone {phase + 1}  {mins}:{secs:02d}",
                x=W - 15, y=42,
                size=18, color=HUD_BLUE, bg_alpha=0.0, anchor="topright",
            )

        # Timer
        mins_g = int(game_time) // 60
        secs_g = int(game_time) % 60
        viewer.draw_text(
            f"{mins_g}:{secs_g:02d}",
            x=W // 2, y=10,
            size=18, color=HUD_GRAY, bg_alpha=0.40, anchor="center",
        )

    def _draw_kill_feed(self, viewer, game_time, W, H):
        entries = self.kill_feed.get_active(game_time)
        for i, text in enumerate(entries):
            alpha = 0.80 - i * 0.08
            viewer.draw_text(
                text,
                x=15, y=15 + i * 26,
                size=16, color=HUD_YELLOW, bg_alpha=max(0, alpha - 0.3),
            )

    def _draw_zone_overlay(self, viewer, W, H, zone, player_pos):
        # Pulsing blue edge tint when outside zone
        t = (math.sin(viewer.frame_count * 0.1) * 0.5 + 0.5)  # type: ignore[attr-defined]
        alpha = 0.18 + t * 0.15
        thickness = 40
        # Top/bottom/left/right edge bars
        viewer.draw_rect(0, 0, W, thickness, color=(0.1, 0.35, 1.0), alpha=alpha)
        viewer.draw_rect(0, H - thickness, W, thickness, color=(0.1, 0.35, 1.0), alpha=alpha)
        viewer.draw_rect(0, 0, thickness, H, color=(0.1, 0.35, 1.0), alpha=alpha)
        viewer.draw_rect(W - thickness, 0, thickness, H, color=(0.1, 0.35, 1.0), alpha=alpha)

        dmg = zone.damage_outside() if hasattr(zone, 'damage_outside') else 0
        viewer.draw_text(
            f"Outside zone! -{dmg:.0f} HP/s",
            x=W // 2, y=75,
            size=22, color=(0.2, 0.6, 1.0), bg_alpha=0.50, anchor="center",
        )

    def _draw_minimap(self, viewer, player, bots, zone, W, H):
        mm_x, mm_y = W - 155, H - 160
        mm_size = 145
        world_half = 110.0   # map extends ±105m, slight margin

        viewer.draw_rect(mm_x - 1, mm_y - 1, mm_size + 2, mm_size + 2,
                         color=(0.08, 0.12, 0.08), alpha=0.90)

        def world_to_mm(wx, wy):
            fx = (wx / world_half + 1.0) * 0.5
            fy = (wy / world_half + 1.0) * 0.5
            # Flip Y (world Y+ = top, screen Y+ = down)
            px = int(mm_x + fx * mm_size)
            py = int(mm_y + (1.0 - fy) * mm_size)
            return px, py

        # Zone circle (approximate with text corners)
        r = getattr(zone, 'current_radius', 100)
        zone_r_px = int(r / world_half * mm_size * 0.5)
        cx_mm, cy_mm = world_to_mm(ZONE_CENTER[0], ZONE_CENTER[1])
        # Draw zone circle (8 short segments using rects)
        for a_i in range(16):
            a = math.pi * a_i / 8
            sx = int(cx_mm + zone_r_px * math.cos(a)) - 1
            sy = int(cy_mm - zone_r_px * math.sin(a)) - 1
            viewer.draw_rect(sx, sy, 3, 3, color=(0.15, 0.50, 1.0), alpha=0.70)

        # Bot dots
        for bot in bots:
            if not bot.is_alive:
                continue
            bx, by = world_to_mm(bot.position[0], bot.position[1])
            viewer.draw_rect(bx - 2, by - 2, 5, 5, color=(0.85, 0.18, 0.10), alpha=0.85)

        # Player dot (slightly larger, white)
        if hasattr(player, 'position'):
            px_mm, py_mm = world_to_mm(player.position[0], player.position[1])
            viewer.draw_rect(px_mm - 3, py_mm - 3, 7, 7, color=(1.0, 1.0, 1.0), alpha=1.0)

            # Direction indicator (small line from player dot)
            if hasattr(player, 'camera'):
                fwd = player.camera.forward
                dlx = int(px_mm + fwd[0] * 8)
                dly = int(py_mm - fwd[1] * 8)
                viewer.draw_rect(dlx - 1, dly - 1, 3, 3, color=HUD_YELLOW, alpha=0.9)

        # "MAP" label
        viewer.draw_text("MAP", x=mm_x + 4, y=mm_y + 3, size=11, color=HUD_GRAY, bg_alpha=0.0)
