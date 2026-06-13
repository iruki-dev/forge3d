"""FORGE RUNNER — player controller."""

from __future__ import annotations

import numpy as np
import settings as S

import forge3d as f3d


class Player:
    def __init__(self, world: f3d.World, spawn: np.ndarray):
        self.world = world
        self.cc = world.add_character(
            position=tuple(spawn),
            height=S.PLAYER_HEIGHT,
            radius=S.PLAYER_RADIUS,
            mass=S.PLAYER_MASS,
            name="player",
            ground_layer_mask=(f3d.CollisionLayer.TERRAIN | f3d.CollisionLayer.DEFAULT),
        )
        self.body = self.cc.body
        self.body.collision_layer = f3d.CollisionLayer.PLAYER
        self.respawn_point = spawn.copy()

        self.hp = S.MAX_HP
        self.coyote = 0.0
        self.has_double_jump = True
        self.jump_cooldown = 0.0
        self.dash_timer = 0.0
        self.dash_cooldown = 0.0
        self.dash_dir = np.zeros(3)
        self.invuln = 0.0
        self.facing = np.array([1.0, 0.0, 0.0])
        self.gliding = False

    @property
    def position(self) -> np.ndarray:
        return self.body.position

    @property
    def velocity(self) -> np.ndarray:
        return self.body.velocity

    @property
    def grounded(self) -> bool:
        return self.cc.is_grounded

    @property
    def dashing(self) -> bool:
        return self.dash_timer > 0.0

    def damage(self, amount: int, knock_from: np.ndarray | None = None) -> bool:
        if self.invuln > 0.0:
            return False
        self.hp = max(0, self.hp - amount)
        self.invuln = S.INVULN_TIME
        if knock_from is not None:
            d = self.position - knock_from
            d[2] = 0.0
            n = np.linalg.norm(d)
            d = d / n if n > 1e-6 else self.facing * -1
            self.body.set_velocity(d * S.SENTRY_KNOCKBACK + np.array([0, 0, 6.0]))
        return True

    def respawn(self) -> None:
        self.world.teleport(self.body, tuple(self.respawn_point))
        self.body.set_velocity((0.0, 0.0, 0.0))
        self.dash_timer = 0.0
        self.invuln = S.INVULN_TIME

    def update(self, inp, dt: float, cam) -> None:
        """cam: OrbitCamera (or any object with forward_azimuth property)."""
        self.invuln = max(0.0, self.invuln - dt)
        self.dash_cooldown = max(0.0, self.dash_cooldown - dt)
        self.jump_cooldown = max(0.0, self.jump_cooldown - dt)

        self.coyote = S.COYOTE_TIME if self.grounded else max(0.0, self.coyote - dt)
        if self.grounded:
            self.has_double_jump = True

        # dash
        if inp.key_pressed(f3d.Key.SHIFT) and self.dash_cooldown <= 0.0 and not self.dashing:
            self.dash_timer = S.DASH_TIME
            self.dash_cooldown = S.DASH_COOLDOWN
            self.dash_dir = self.facing.copy()

        if self.dashing:
            self.dash_timer -= dt
            v = self.dash_dir * S.DASH_SPEED
            self.body.set_velocity((v[0], v[1], 0.0))
        else:
            speed = S.RUN_SPEED if self.grounded else S.AIR_SPEED
            move = self.cc.move_camera_relative(inp, cam, speed=speed, dt=dt)
            if np.linalg.norm(move) > 1e-6:
                self.facing = move / np.linalg.norm(move)

        # jump
        if inp.key_pressed(f3d.Key.SPACE) and self.jump_cooldown <= 0.0:
            v = self.body.velocity
            if self.coyote > 0.0:
                self.body.set_velocity((v[0], v[1], S.JUMP_IMPULSE))
                self.coyote = 0.0
                self.jump_cooldown = 0.25
            elif self.has_double_jump:
                self.body.set_velocity((v[0], v[1], S.DOUBLE_JUMP_IMPULSE))
                self.has_double_jump = False
                self.jump_cooldown = 0.25

        # glide
        self.gliding = (
            inp.key_held(f3d.Key.SPACE)
            and not self.grounded
            and self.velocity[2] < 0.0
            and not self.dashing
        )
        if self.gliding:
            self.cc.glide(target_fall_speed=S.GLIDE_FALL_SPEED, dt=dt)
