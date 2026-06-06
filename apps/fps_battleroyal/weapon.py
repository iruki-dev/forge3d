"""Weapon types, instances, and raycast shooting logic."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from apps.fps_battleroyal.config import WEAPON_DATA


@dataclass
class WeaponInstance:
    """Runtime state for a single weapon held by a player or bot."""

    kind:     str           # key into WEAPON_DATA
    ammo:     int  = 0      # current magazine
    reserve:  int  = 0      # reserve ammo
    cooldown: float = 0.0   # seconds until next shot allowed
    reloading: bool = False
    reload_elapsed: float = 0.0

    @classmethod
    def spawn(cls, kind: str) -> WeaponInstance:
        d = WEAPON_DATA[kind]
        return cls(
            kind=kind,
            ammo=d["mag_size"],
            reserve=d["reserve"],
        )

    # ── Data accessors ────────────────────────────────────────────────────────

    @property
    def data(self) -> dict:
        return WEAPON_DATA[self.kind]

    @property
    def display_name(self) -> str:
        return self.data["display"]

    @property
    def is_auto(self) -> bool:
        return self.data["auto"]

    @property
    def ready(self) -> bool:
        return self.cooldown <= 0.0 and not self.reloading and self.ammo > 0

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        if self.cooldown > 0:
            self.cooldown -= dt
        if self.reloading:
            self.reload_elapsed += dt
            if self.reload_elapsed >= self.data["reload_s"]:
                needed = self.data["mag_size"] - self.ammo
                taken  = min(needed, self.reserve)
                self.ammo    += taken
                self.reserve -= taken
                self.reloading      = False
                self.reload_elapsed = 0.0

    def start_reload(self) -> None:
        if not self.reloading and self.ammo < self.data["mag_size"] and self.reserve > 0:
            self.reloading      = True
            self.reload_elapsed = 0.0

    def consume(self) -> None:
        """Spend one shot and reset cooldown."""
        self.ammo -= 1
        self.cooldown = 1.0 / self.data["fire_rate"]


# ── Shooting ──────────────────────────────────────────────────────────────────

@dataclass
class ShotResult:
    hit:        bool
    body_name:  str  = ""
    distance:   float = 0.0
    point:      np.ndarray = field(default_factory=lambda: np.zeros(3))


def shoot_ray(
    world: object,  # forge3d.World
    origin: np.ndarray,
    direction: np.ndarray,
    weapon: WeaponInstance,
    rng: np.random.Generator,
    *,
    exclude_name: str = "",
) -> ShotResult:
    """Fire one shot from *origin* in *direction* with weapon spread.

    Returns a ShotResult. Does NOT modify weapon state — caller must call
    weapon.consume() if the shot should cost ammo.
    """
    d = weapon.data
    spread = d["spread"]
    max_range = d["range"]

    # Apply random spread (Gaussian, clamped)
    if spread > 0:
        dx = float(rng.normal(0, spread))
        dy = float(rng.normal(0, spread))
        right = np.array([-direction[1], direction[0], 0.0])
        r_len = math.sqrt(right[0] ** 2 + right[1] ** 2)
        if r_len > 1e-9:
            right /= r_len
        up = np.cross(direction, right)
        fired_dir = direction + dx * right + dy * up
    else:
        fired_dir = direction.copy()

    norm = math.sqrt(fired_dir[0]**2 + fired_dir[1]**2 + fired_dir[2]**2)
    if norm < 1e-12:
        return ShotResult(hit=False)
    fired_dir /= norm

    hit = world.raycast(origin, fired_dir, max_dist=max_range)
    if hit is None:
        return ShotResult(hit=False)
    if hit.body.name == exclude_name:
        return ShotResult(hit=False)

    return ShotResult(
        hit=True,
        body_name=hit.body.name,
        distance=hit.distance,
        point=np.asarray(hit.point, dtype=np.float64),
    )
