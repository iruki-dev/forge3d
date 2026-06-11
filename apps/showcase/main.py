"""forge3d Visual Showcase — a walking tour of physics and rendering.

Run:
    python -m apps.showcase.main

Controls:
    WASD         — move / strafe      Shift — sprint
    Mouse        — look               Space — jump
    E            — trigger tower demo (Physics Stage)
    TAB          — teleport to next zone
    ESC          — release mouse
"""
from __future__ import annotations

import contextlib
import math
import pathlib
import sys

import numpy as np

if __name__ == "__main__":
    sys.path.insert(0, str(pathlib.Path(__file__).parents[2]))

from apps.showcase.world_builder import M, ShowcaseAssets, build_showcase

import forge3d as f3d
from forge3d.render.snapshot import CameraSnapshot

SKY_COLOR = (0.06, 0.08, 0.20)

WAYPOINTS = [
    ("Entrance Colonnade", (  0.0, -68.0, 1.5), "20 marble columns — processional arcade"),
    ("Grand Plaza",        (  0.0,  12.0, 1.5), "Central obelisk, 5-point fountain, 4 shrines"),
    ("Materials Hall",     (-60.0,   0.0, 1.5), "8 PBR demonstrations: marble to mirror steel"),
    ("Physics Stage",      ( 60.0,  -8.0, 1.5), "Amphitheatre — press E near the tower"),
    ("Emissive Sanctum",   (  0.0,  70.0, 1.5), "9 coloured orbs in a sealed dark hall"),
    ("Cascade Court",      (-60.0,  62.0, 1.5), "Mirror pool — live physics waterfall"),
]


# ── Camera ────────────────────────────────────────────────────────────────────

class Camera:
    SENS = 0.0055   # CURSOR_HIDDEN: window is bounded, need higher sens for 360° sweep

    def __init__(self, pos=(0.0, -68.0, 1.8), yaw: float = math.pi / 2):
        self.yaw   = yaw
        self.pitch = 0.0
        self._eye  = np.array(pos, dtype=float)

    @property
    def forward(self):
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp = math.cos(self.pitch)
        sp = math.sin(self.pitch)
        return np.array([cy * cp, sy * cp, sp])

    @property
    def forward_flat(self):
        return np.array([math.cos(self.yaw), math.sin(self.yaw), 0.0])

    @property
    def right(self):
        return np.array([math.sin(self.yaw), -math.cos(self.yaw), 0.0])

    def update(self, dx: float, dy: float, foot_pos, eye_h: float = 1.65):
        self.yaw  -= dx * self.SENS
        self.pitch = float(np.clip(
            self.pitch - dy * self.SENS, -math.pi / 2 + 0.01, math.pi / 2 - 0.01
        ))
        self._eye = np.array(foot_pos) + np.array([0.0, 0.0, eye_h])

    def snapshot(self, fov: float = 68.0) -> CameraSnapshot:
        fwd    = self.forward
        target = self._eye + fwd
        up     = np.array([0.0, 0.0, 1.0])
        if abs(fwd[2]) > 0.98:
            up = np.array([math.cos(self.yaw), math.sin(self.yaw), 0.0])
        return CameraSnapshot(
            position=self._eye.copy(), target=target,
            up=up, fov_deg=fov, near=0.08, far=1200.0,
        )


# ── App ───────────────────────────────────────────────────────────────────────

class ShowcaseApp:
    W, H         = 1280, 720
    MOVE_SPEED   = 8.0
    SPRINT_SPEED = 15.0

    CASCADE_INTERVAL = 2.0
    CASCADE_MAX      = 14
    CASCADE_RADIUS   = 55.0
    TOWER_RESET_SECS = 22.0

    def __init__(self):
        print("Building showcase world…")
        self.world = f3d.World(gravity=(0, 0, -18))
        self.world.fixed_dt     = 1 / 60
        self.world.max_substeps = 2

        self.assets: ShowcaseAssets = build_showcase(self.world)

        start = WAYPOINTS[0][1]
        self.cc = self.world.add_character(
            position=start, height=1.80, radius=0.34, mass=75.0,
            name="player", ground_check_hz=60.0,
        )
        self.cam = Camera(pos=start, yaw=math.pi / 2)

        self._tower_dynamic: list  = []
        self._tower_trigger_sphere = None
        self._tower_active         = False
        self._tower_reset_t        = 0.0

        self._cascade_spheres: list = []
        self._cascade_t = 0.0

        self._wp_idx     = 0
        self._area_text  = ""
        self._area_desc  = ""
        self._area_flash = 0.0
        self._tab_held   = False

        # _playing: True while mouse is captured and user is in control.
        # _mouse_skip: discard this many frames of mouse delta after capture
        # to absorb any position-jump that CURSOR_DISABLED causes on the platform.
        self._playing    = False
        self._mouse_skip = 0

        self.viewer = f3d.Viewer(
            self.world, width=self.W, height=self.H,
            title="forge3d — Visual Showcase",
            fps=60, shadow_resolution=2048,
            sky_color=SKY_COLOR,
        )
        self.viewer.set_excluded_names({"player"})
        self.viewer.set_camera(self.cam.snapshot())
        # Disable debug grid — scene has a proper ground plane
        r = self.viewer._renderer
        if r is not None:
            r._show_grid = False
        self.viewer.draw()   # warm-up: creates GLFW window + GL context

        print("Ready — click window to start, ESC to release mouse.")

    # ── Tower ─────────────────────────────────────────────────────────────────

    def _trigger_tower(self):
        body_map = {b.name: b for b in self.world.bodies
                    if b.name and b.name.startswith("tower_")}
        for k, (tx, ty, tz, mat_k) in enumerate(self.assets.tower_positions):
            with contextlib.suppress(Exception):
                if b := body_map.get(f"tower_{k}"):
                    self.world.remove(b)
            self._tower_dynamic.append(
                self.world.add_box(
                    size=(1.3, 1.3, 0.88), position=(tx, ty, tz),
                    mass=2.5, material=M[mat_k], name=f"tower_d{k}",
                )
            )
        sx, sy, sz = self.assets.tower_spawn
        self._tower_trigger_sphere = self.world.add_sphere(
            radius=0.55, position=(sx, sy, sz), mass=5.0, material=M["gold"],
        )
        tx0 = self.assets.tower_positions[5][0]
        ty0 = self.assets.tower_positions[5][1]
        d   = np.array([tx0 - sx, ty0 - sy, 0.0])
        d  /= np.linalg.norm(d) + 1e-9
        self._tower_trigger_sphere.set_velocity(tuple(d * 15.0))
        self._tower_active  = True
        self._tower_reset_t = self.TOWER_RESET_SECS

    def _reset_tower(self):
        for b in self._tower_dynamic:
            with contextlib.suppress(Exception):
                self.world.remove(b)
        self._tower_dynamic.clear()
        if self._tower_trigger_sphere is not None:
            with contextlib.suppress(Exception):
                self.world.remove(self._tower_trigger_sphere)
            self._tower_trigger_sphere = None
        for k, (tx, ty, tz, mat_k) in enumerate(self.assets.tower_positions):
            self.world.add_box(
                size=(1.3, 1.3, 0.88), position=(tx, ty, tz),
                static=True, material=M[mat_k], name=f"tower_{k}",
            )
        self._tower_active = False

    # ── Cascade ───────────────────────────────────────────────────────────────

    def _update_cascade(self, dt: float):
        self._cascade_t += dt
        if self._cascade_t < self.CASCADE_INTERVAL:
            return
        self._cascade_t = 0.0
        if len(self._cascade_spheres) >= self.CASCADE_MAX:
            with contextlib.suppress(Exception):
                self.world.remove(self._cascade_spheres.pop(0))
        sx, sy, sz = self.assets.cascade_spout
        cycle = [
            ((0.42, 0.44, 0.46), 0.28, 0.88),
            ((0.83, 0.68, 0.21), 0.11, 0.97),
            ((0.72, 0.45, 0.20), 0.42, 0.78),
            ((0.55, 0.40, 0.18), 0.55, 0.70),
            ((0.38, 0.40, 0.42), 0.05, 0.97),
            ((0.27, 0.26, 0.25), 0.65, 0.60),
        ]
        c, r, m = cycle[len(self._cascade_spheres) % len(cycle)]
        radius  = float(np.random.uniform(0.18, 0.30))
        ox      = float(np.random.uniform(-0.6,  0.6))
        oy      = float(np.random.uniform(-0.2,  0.2))
        self._cascade_spheres.append(
            self.world.add_sphere(
                radius=radius, position=(sx + ox, sy + oy, sz),
                mass=radius * 4.0,
                material=f3d.Material(color=c, roughness=r, metallic=m),
            )
        )

    # ── Area detection ────────────────────────────────────────────────────────

    def _detect_area(self) -> tuple[str, str]:
        pos2 = np.array(self.cc.position[:2])
        for name, wp, desc in WAYPOINTS:
            if np.linalg.norm(pos2 - np.array(wp[:2])) < 30.0:
                return name, desc
        return "Open Path", "Walk between the six showcase zones"

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        while self.viewer.is_open:
            dt  = float(np.clip(self.viewer.dt, 1e-4, 0.05))
            inp = self.viewer.input

            # ── Capture state ────────────────────────────────────────────────
            r = self.viewer._renderer

            if not self._playing and inp.mouse_button(0):
                self.viewer.set_cursor_captured(True)
                self._playing    = True
                self._mouse_skip = 3   # discard first 3 frames after capture

            # ESC: renderer releases cursor (sets _cursor_captured=False)
            # detect this to stop playing.  Only check when already playing,
            # and read _cursor_captured AFTER the click block so it reflects
            # the state set by set_cursor_captured() this same frame.
            if self._playing:
                still_captured = bool(r and getattr(r, "_cursor_captured", False))
                if not still_captured:
                    self._playing = False

            # ── Camera look ──────────────────────────────────────────────────
            if self._playing:
                dx, dy = inp.mouse_delta()
                if self._mouse_skip > 0:
                    dx, dy = 0.0, 0.0
                    self._mouse_skip -= 1
                self.cam.update(dx, dy, self.cc.position)
            else:
                self.cam.update(0.0, 0.0, self.cc.position)

            # ── Movement ─────────────────────────────────────────────────────
            if self._playing:
                spd  = self.SPRINT_SPEED if inp.key_held(f3d.Key.SHIFT) else self.MOVE_SPEED
                move = np.zeros(3)
                if inp.key_held(f3d.Key.W):
                    move += self.cam.forward_flat
                if inp.key_held(f3d.Key.S):
                    move -= self.cam.forward_flat
                if inp.key_held(f3d.Key.A):
                    move -= self.cam.right
                if inp.key_held(f3d.Key.D):
                    move += self.cam.right
                mag = float(np.linalg.norm(move[:2]))
                if mag > 1e-9:
                    move[:2] /= mag
                    self.cc.move(direction=tuple(move), speed=spd, dt=dt)
                else:
                    # Instant stop: zero horizontal velocity explicitly
                    vel = list(self.cc.body.velocity)
                    vel[0] = 0.0
                    vel[1] = 0.0
                    self.cc.body.set_velocity(tuple(vel))
                    self.cc.move(direction=(0.0, 0.0, 0.0), speed=0.0, dt=dt)

                if inp.key_pressed(f3d.Key.SPACE) and self.cc.is_grounded:
                    self.cc.jump(impulse=8.5)

                tab_now = inp.key_held(f3d.Key.TAB)
                if tab_now and not self._tab_held:
                    self._wp_idx = (self._wp_idx + 1) % len(WAYPOINTS)
                    name, pos, desc = WAYPOINTS[self._wp_idx]
                    self.world.teleport(self.cc.body, position=pos)
                    self.cam.yaw     = math.pi / 2
                    self._mouse_skip = 1   # one skip after teleport
                    self._area_text  = name
                    self._area_desc  = desc
                    self._area_flash = 3.5
                self._tab_held = tab_now

                if inp.key_pressed(f3d.Key.E):
                    pos  = self.cc.position
                    if math.hypot(pos[0] - 60, pos[1]) < 35 and not self._tower_active:
                        self._trigger_tower()

            # ── Simulation ───────────────────────────────────────────────────
            self.world.update(dt)

            if self._tower_active:
                self._tower_reset_t -= dt
                if self._tower_reset_t <= 0.0:
                    self._reset_tower()

            pos = self.cc.position
            if math.hypot(pos[0] - (-60), pos[1] - 70) < self.CASCADE_RADIUS:
                self._update_cascade(dt)

            self._area_flash = max(0.0, self._area_flash - dt)

            # ── Render ───────────────────────────────────────────────────────
            self.viewer.set_camera(self.cam.snapshot())
            self.viewer.draw()
            self._draw_hud(self._playing)

        self.viewer.close()

    # ── HUD ───────────────────────────────────────────────────────────────────

    def _draw_hud(self, playing: bool):
        W, H = self.W, self.H

        if not playing:
            self.viewer.draw_rect(W // 2 - 240, H // 2 - 34, 480, 68,
                                  color=(0, 0, 0), alpha=0.75)
            self.viewer.draw_text(
                "Click to start  |  ESC to release mouse",
                x=W // 2, y=H // 2, size=20,
                color=(0.9, 0.9, 0.9), bg_alpha=0.0, anchor="center",
            )
            return

        # Crosshair
        self.viewer.draw_rect(W // 2 - 2, H // 2 - 2, 5, 5,
                              color=(1, 1, 1), alpha=0.65)

        # Area name
        area, desc  = self._detect_area()
        disp_area   = self._area_text if self._area_flash > 0 else area
        disp_desc   = self._area_desc if self._area_flash > 0 else desc
        alpha_t     = min(1.0, self._area_flash) if self._area_flash > 0 else 0.55
        self.viewer.draw_text(disp_area, x=W // 2, y=16, size=28,
                              color=(1.0, 0.88, 0.52), bg_alpha=alpha_t * 0.45,
                              anchor="center")
        self.viewer.draw_text(disp_desc, x=W // 2, y=52, size=14,
                              color=(0.80, 0.80, 0.80), bg_alpha=alpha_t * 0.30,
                              anchor="center")

        # Controls
        for i, hint in enumerate([
            "WASD / Shift — move / sprint",
            "Space — jump",
            "TAB — next zone",
            "E — trigger demo  (Physics Stage)",
        ]):
            self.viewer.draw_text(hint, x=12, y=H - 22 - i * 22,
                                  size=13, color=(0.60, 0.60, 0.60), bg_alpha=0.0)

        if self._tower_active and self._tower_reset_t > 0:
            self.viewer.draw_text(
                f"Tower reset in {self._tower_reset_t:.0f}s",
                x=W - 12, y=H - 28, size=15,
                color=(1.0, 0.68, 0.20), bg_alpha=0.40, anchor="topright",
            )
        if self._cascade_spheres:
            self.viewer.draw_text(
                f"Cascade: {len(self._cascade_spheres)}/{self.CASCADE_MAX}",
                x=W - 12, y=H - 56, size=13,
                color=(0.45, 0.85, 1.0), bg_alpha=0.35, anchor="topright",
            )

        pos2 = self.cc.position[:2]
        for label, (lx, ly) in self.assets.material_labels:
            if math.hypot(pos2[0] - lx, pos2[1] - ly) < 4.5:
                self.viewer.draw_text(label, x=W // 2, y=H // 2 - 65, size=24,
                                      color=(1.0, 0.85, 0.50), bg_alpha=0.50,
                                      anchor="center")
                break


def main():
    ShowcaseApp().run()


if __name__ == "__main__":
    main()
