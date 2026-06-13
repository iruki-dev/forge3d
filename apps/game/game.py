"""FORGE RUNNER — game state machine and event wiring."""

from __future__ import annotations

import numpy as np
import settings as S
from enemies import spawn_sentries
from level import Level
from player import Player

import forge3d as f3d

MENU, PLAYING, DEAD, WIN = "menu", "playing", "dead", "win"


class Game:
    def __init__(self, world: f3d.World):
        self.world = world
        self.level = Level(world)
        self.player = Player(world, self.level.spawn)
        self.sentries = spawn_sentries(world, self.level.sentry_posts)

        self.state = MENU
        self.time = 0.0
        self.score = 0
        self.cores_collected = 0
        self.cores_total = len(self.level.cores)
        self.all_cores = False
        self.won = False
        self.message = ""
        self.message_timer = 0.0

        self._wire_events()

    # ── event wiring ─────────────────────────────────────────────────────
    def _wire_events(self) -> None:
        for core in self.level.cores:

            @core.zone.on_enter
            def grab(body, core=core):
                if body.name != "player" or core.collected:
                    return
                core.collected = True
                core.zone.enabled = False
                pos = core.marker.position.copy()
                self.world.remove(core.marker)
                self.cores_collected += 1
                self.score += S.CORE_SCORE
                self.world.particle_burst(pos, color=(1.0, 0.82, 0.15), count=12, speed=4.5, up=5.0)
                if self.cores_collected >= self.cores_total:
                    self.all_cores = True
                    self.level.open_goal()
                    self.flash("ALL CORES ONLINE — THE GATE IS OPEN")
                else:
                    self.flash(f"CORE SECURED  ({self.cores_collected}/{self.cores_total})")

        for zone, point, flag in self.level.checkpoints:

            @zone.on_enter
            def cp(body, point=point, flag=flag):
                if body.name != "player":
                    return
                if not np.allclose(self.player.respawn_point, point):
                    self.player.respawn_point = point.copy()
                    self.world.particle_burst(
                        flag.position, color=(0.2, 0.9, 1.0), count=8, speed=3.0
                    )
                    self.flash("CHECKPOINT")

        for zone in self.level.lava_zones:

            @zone.on_enter
            def burn(body, _z=zone):
                if body.name != "player":
                    return
                self.world.particle_burst(
                    self.player.position, color=(1.0, 0.3, 0.05), count=10, speed=5.0
                )
                self.player.damage(S.LAVA_DAMAGE)
                self.player.respawn()
                self.flash("THE LAVA BITES")

        for zone, launch in self.level.spring_pads:

            @zone.on_enter
            def boing(body, launch=launch):
                if body.name != "player":
                    return
                v = self.player.body.velocity
                self.player.body.set_velocity((v[0], v[1], launch))
                self.player.has_double_jump = True
                self.world.particle_burst(
                    self.player.position, color=(0.2, 0.95, 0.35), count=8, speed=3.5
                )

        @self.level.goal_zone.on_enter
        def goal(body):
            if body.name == "player" and self.all_cores and not self.won:
                self.won = True
                self.score += max(0, S.TIME_BONUS_BASE - int(self.time) * 5)
                self.state = WIN
                self.world.particle_burst(
                    self.player.position, color=(0.3, 1.0, 0.5), count=20, speed=6.0, up=7.0
                )

        @self.world.on_collision_begin
        def impact(event: f3d.CollisionEvent):
            names = {event.body_a.name, event.body_b.name}
            if "player" not in names:
                return
            other = event.body_b if event.body_a.name == "player" else event.body_a
            if other.name.startswith("blade") and event.relative_speed > 4.0:
                self.player.damage(10, knock_from=other.position)
                self.world.particle_burst(
                    np.asarray(event.contact_point), color=(1.0, 0.6, 0.1), count=6, speed=4.0
                )
            elif event.relative_speed > 9.0:
                self.world.particle_burst(
                    np.asarray(event.contact_point),
                    color=(0.7, 0.65, 0.55),
                    count=5,
                    speed=2.5,
                    up=2.0,
                )

    # ── helpers ──────────────────────────────────────────────────────────
    def flash(self, msg: str, t: float = 2.2) -> None:
        self.message, self.message_timer = msg, t

    def start(self) -> None:
        self.state = PLAYING

    def retry(self) -> None:
        self.player.body.unfreeze()
        self.player.hp = S.MAX_HP
        self.player.respawn()
        self.score = max(0, self.score - 50)
        self.state = PLAYING
        self.flash("BACK IN THE FIGHT")

    # ── per-frame ────────────────────────────────────────────────────────
    def update(self, inp, dt: float, cam) -> None:
        self.message_timer = max(0.0, self.message_timer - dt)
        self.level.update(self.world.time, dt)

        if self.state == MENU:
            if inp.key_pressed(f3d.Key.ENTER):
                self.start()
            return

        if self.state in (DEAD, WIN):
            self.player.body.freeze()
            if self.state == DEAD and inp.key_pressed(f3d.Key.ENTER):
                self.retry()
            return

        # PLAYING
        self.time += dt
        self.player.update(inp, dt, cam)
        for sentry in self.sentries:
            sentry.update(dt, self.player)

        if self.player.position[2] < S.KILL_Z:
            self.player.damage(S.FALL_DAMAGE)
            self.player.respawn()
            self.flash("LONG WAY DOWN")

        if self.player.hp <= 0:
            self.state = DEAD
