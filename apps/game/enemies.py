"""FORGE RUNNER — sentry enemies."""

from __future__ import annotations

import numpy as np
import settings as S

import forge3d as f3d

SENTRY_MAT = f3d.Material(color=(0.85, 0.12, 0.55), emissive=0.7, metallic=0.4, roughness=0.4)
EYE_MAT = f3d.Material(color=(1.0, 0.95, 0.3), emissive=1.0)


class Sentry:
    def __init__(self, world: f3d.World, post_a: np.ndarray, post_b: np.ndarray, idx: int):
        self.world = world
        self.a = post_a.astype(float)
        self.b = post_b.astype(float)
        self.body = world.add_box(
            size=(0.9, 0.9, 0.9),
            position=tuple(post_a),
            mass=40.0,
            material=SENTRY_MAT,
            name=f"sentry_{idx}",
            friction=0.2,
            restitution=0.1,
        )
        self.body.collision_layer = f3d.CollisionLayer.ENEMY
        self.eye = world.add_sphere(
            radius=0.18,
            position=tuple(post_a + np.array([0, 0, 0.55])),
            static=True,
            material=EYE_MAT,
            name=f"sentry_eye_{idx}",
        )
        self.eye.collision_mask = 0
        self.t_dir = 1.0
        self.alerted = False

    def _has_los(self, player_pos: np.ndarray) -> bool:
        origin = self.body.position + np.array([0, 0, 0.3])
        target = player_pos + np.array([0, 0, 0.5])
        to = target - origin
        dist = float(np.linalg.norm(to))
        if dist > S.SENTRY_SIGHT_RANGE or dist < 1e-6:
            return False
        # Raycast now hits both bodies AND terrain, so one call suffices
        hits = self.world.raycast_all(
            origin,
            to / dist,
            max_dist=dist,
            layer_mask=f3d.CollisionLayer.DEFAULT | f3d.CollisionLayer.TERRAIN,
        )
        return not hits

    def update(self, dt: float, player) -> None:
        pos = self.body.position
        self.alerted = self._has_los(player.position)

        if self.alerted:
            target = player.position
            speed = S.SENTRY_CHASE_SPEED
        else:
            target = self.b if self.t_dir > 0 else self.a
            speed = S.SENTRY_PATROL_SPEED
            if np.linalg.norm((target - pos)[:2]) < 0.8:
                self.t_dir *= -1.0

        d = target - pos
        d[2] = 0.0
        n = np.linalg.norm(d)
        vxy = (d / n * speed) if n > 1e-6 else np.zeros(3)

        # Hover: downward raycast for terrain height (now works on heightfields)
        hit = self.world.raycast(
            pos + np.array([0, 0, 0.5]),
            (0, 0, -1),
            max_dist=8.0,
            layer_mask=f3d.CollisionLayer.DEFAULT | f3d.CollisionLayer.TERRAIN,
        )
        want_z = float(hit.point[2]) + 1.2 if hit is not None else pos[2]
        vz = float(np.clip((want_z - pos[2]) * 4.0, -4.0, 6.0))
        self.body.set_velocity((vxy[0], vxy[1], vz))
        self.eye.set_position(pos + np.array([0, 0, 0.55]))

        # contact damage
        flat = player.position - pos
        if np.linalg.norm(flat[:2]) < S.SENTRY_HIT_RANGE and abs(flat[2]) < 1.6:
            player.damage(S.SENTRY_DAMAGE, knock_from=pos)


def spawn_sentries(world: f3d.World, posts) -> list[Sentry]:
    return [Sentry(world, a, b, i) for i, (a, b) in enumerate(posts)]
