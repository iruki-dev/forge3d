"""Local player state, movement, and health."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

import forge3d as f3d
from apps.fps_battleroyal.camera import FPSCamera
from apps.fps_battleroyal.config import (
    EYE_HEIGHT,
    JUMP_IMPULSE,
    MOVE_SPEED,
    PLAYER_HEIGHT,
    PLAYER_MAX_ARMOR,
    PLAYER_MAX_HP,
    PLAYER_RADIUS,
    SPRINT_MULT,
)
from apps.fps_battleroyal.weapon import WeaponInstance


@dataclass
class Player:
    """Complete state for the local (human) player."""

    cc: f3d.CharacterController     # physics + collision
    camera: FPSCamera

    hp:    float = PLAYER_MAX_HP
    armor: float = 0.0

    weapons: list[WeaponInstance] = field(default_factory=list)  # max 2 slots
    active_slot: int = 0

    kills:      int  = 0
    is_alive:   bool = True

    # Damage flash timer
    _damage_flash: float = 0.0

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def position(self) -> np.ndarray:
        return np.asarray(self.cc.position, dtype=np.float64)

    @property
    def active_weapon(self) -> WeaponInstance | None:
        if not self.weapons:
            return None
        return self.weapons[self.active_slot]

    @property
    def health_frac(self) -> float:
        return float(np.clip(self.hp / PLAYER_MAX_HP, 0.0, 1.0))

    @property
    def armor_frac(self) -> float:
        return float(np.clip(self.armor / PLAYER_MAX_ARMOR, 0.0, 1.0))

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, inp: f3d.Input, dt: float, world: f3d.World) -> None:
        if not self.is_alive:
            return

        # ── Camera look ───────────────────────────────────────────────────────
        dx, dy = inp.mouse_delta()
        self.camera.update(dx, dy, self.position, EYE_HEIGHT)

        # ── Movement ──────────────────────────────────────────────────────────
        speed = MOVE_SPEED
        if inp.key_held(f3d.Key.SHIFT):
            speed *= SPRINT_MULT

        fwd   = self.camera.forward
        right = self.camera.right
        fwd_h = np.array([fwd[0], fwd[1], 0.0])
        fwd_h_len = float(np.linalg.norm(fwd_h))
        if fwd_h_len > 1e-9:
            fwd_h /= fwd_h_len

        move = np.zeros(3)
        if inp.key_held(f3d.Key.W):
            move += fwd_h
        if inp.key_held(f3d.Key.S):
            move -= fwd_h
        if inp.key_held(f3d.Key.A):
            move -= right
        if inp.key_held(f3d.Key.D):
            move += right

        m_len = float(np.linalg.norm(move[:2]))
        if m_len > 1e-9:
            move[:2] /= m_len

        self.cc.move(direction=tuple(move), speed=speed, dt=dt)

        # ── Jump ──────────────────────────────────────────────────────────────
        if inp.key_pressed(f3d.Key.SPACE) and self.cc.is_grounded:
            self.cc.jump(impulse=JUMP_IMPULSE)

        # ── Weapon update ─────────────────────────────────────────────────────
        if self.active_weapon:
            self.active_weapon.update(dt)

        # ── Reload ────────────────────────────────────────────────────────────
        if inp.key_pressed(f3d.Key.R) and self.active_weapon:
            self.active_weapon.start_reload()

        # ── Switch weapons ────────────────────────────────────────────────────
        if inp.key_pressed("1") and len(self.weapons) >= 1:
            self.active_slot = 0
        if inp.key_pressed("2") and len(self.weapons) >= 2:
            self.active_slot = 1
        scroll = inp.scroll_delta()
        if scroll != 0 and len(self.weapons) > 1:
            self.active_slot = (self.active_slot + (1 if scroll < 0 else -1)) % len(self.weapons)

        # ── Damage flash decay ─────────────────────────────────────────────────
        if self._damage_flash > 0:
            self._damage_flash = max(0.0, self._damage_flash - dt * 2.5)

    # ── Damage ────────────────────────────────────────────────────────────────

    def take_damage(self, amount: float) -> None:
        if not self.is_alive:
            return
        # Armor absorbs 60% of damage
        if self.armor > 0:
            armor_absorb = min(self.armor, amount * 0.60)
            self.armor -= armor_absorb
            amount -= armor_absorb
        self.hp -= amount
        self._damage_flash = 1.0
        if self.hp <= 0:
            self.hp = 0.0
            self.is_alive = False

    # ── Pickup ────────────────────────────────────────────────────────────────

    def pick_up_weapon(self, kind: str) -> bool:
        """Try to add a weapon to inventory. Returns True if picked up."""
        # Don't pick up duplicate kinds
        held_kinds = {w.kind for w in self.weapons}
        if kind in held_kinds:
            return False
        wi = WeaponInstance.spawn(kind)
        if len(self.weapons) < 2:
            self.weapons.append(wi)
            self.active_slot = len(self.weapons) - 1
        else:
            # Replace active weapon
            self.weapons[self.active_slot] = wi
        return True


def create_player(world: f3d.World, position: np.ndarray) -> Player:
    """Spawn the local player at *position* and return its state."""
    cc = world.add_character(
        position=tuple(position),
        height=PLAYER_HEIGHT,
        radius=PLAYER_RADIUS,
        mass=75.0,
        name="player_local",
    )
    cam = FPSCamera()
    cam.yaw = 0.0
    cam.update(0, 0, position, EYE_HEIGHT)

    p = Player(
        cc=cc,
        camera=cam,
        weapons=[WeaponInstance.spawn("pistol")],
    )
    return p
