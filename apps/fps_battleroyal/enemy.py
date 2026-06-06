"""Bot AI — direct velocity control, bot-vs-bot combat, calibrated accuracy.

Performance: bots use f3d.Body (capsule) with set_velocity() instead of
CharacterController.  This eliminates ground-detection raycasts for all 19
bots (previously ~79 ms/frame → < 1 ms).

AI changes vs previous version:
  - Accuracy: 0.92 → 0.35 base, falls off further with distance
  - Bots fight each other when player is not visible (true battle royale)
  - Shoot interval: 0.55 → 1.1s  (less bullet-spongey)
  - Reaction delay: 0.30 → 0.65s
  - Bots strafe during combat for better feel
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto

import numpy as np

import forge3d as f3d
from apps.fps_battleroyal.config import (
    BOT_COUNT,
    BOT_MAX_HP,
    BOT_MOVE_SPEED,
    BOT_PATROL_RADIUS,
    BOT_SHOOT_RANGE,
    BOT_SIGHT_RANGE,
    C_ENEMY,
    PLAYER_HEIGHT,
    PLAYER_RADIUS,
    ZONE_CENTER,
)
from apps.fps_battleroyal.weapon import WEAPON_DATA, WeaponInstance, shoot_ray


class BotState(Enum):
    PATROL  = auto()
    ALERT   = auto()
    COMBAT  = auto()
    RETREAT = auto()
    DEAD    = auto()


# Per-distance accuracy table (linear interpolation)
_ACC_DIST  = [0.0,   10.0,  25.0,  40.0,  60.0, 100.0]
_ACC_VALS  = [0.75,  0.55,  0.40,  0.25,  0.15,  0.05]


def _accuracy_at(distance: float) -> float:
    for i in range(len(_ACC_DIST) - 1):
        if distance <= _ACC_DIST[i + 1]:
            t = (distance - _ACC_DIST[i]) / (_ACC_DIST[i + 1] - _ACC_DIST[i])
            return _ACC_VALS[i] + t * (_ACC_VALS[i + 1] - _ACC_VALS[i])
    return _ACC_VALS[-1]


@dataclass
class BotTarget:
    """Resolved combat target (player or another bot)."""

    position: np.ndarray
    is_player: bool
    bot_ref: "Bot | None" = None   # set when targeting another bot


@dataclass
class Bot:
    """One AI-controlled opponent.

    Uses a plain capsule Body (not CharacterController) so there is no
    per-frame ground-detection raycast.  Movement is via body.set_velocity().
    Gravity and ground contacts are handled automatically by the physics engine.
    """

    body:   f3d.Body
    name:   str
    hp:     float = BOT_MAX_HP
    weapon: WeaponInstance = field(default_factory=lambda: WeaponInstance.spawn("pistol"))
    state:  BotState = BotState.PATROL

    # AI internals
    target:           BotTarget | None  = None
    patrol_target:    np.ndarray        = field(default_factory=lambda: np.zeros(3))
    last_shot_t:      float             = 0.0
    reaction_timer:   float             = 0.0
    stuck_timer:      float             = 0.0
    last_pos:         np.ndarray        = field(default_factory=lambda: np.zeros(3))
    saw_target_at:    float             = -999.0
    zone_retreat_t:   float             = 0.0
    strafe_dir:       float             = 1.0   # ±1

    # LoS throttle: 8 Hz
    _los_timer:    float = 0.0
    _los_interval: float = 0.125
    _los_cached:   bool  = False

    is_alive: bool = True
    kills:    int  = 0

    _rng: random.Random = field(default_factory=lambda: random.Random())

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def position(self) -> np.ndarray:
        return np.asarray(self.body.position, dtype=np.float64)

    @property
    def eye_pos(self) -> np.ndarray:
        p = self.position.copy()
        p[2] += 1.55
        return p

    @property
    def health_frac(self) -> float:
        return float(np.clip(self.hp / BOT_MAX_HP, 0.0, 1.0))

    # ── Damage ────────────────────────────────────────────────────────────────

    def take_damage(self, amount: float) -> None:
        if not self.is_alive:
            return
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0.0
            self.is_alive = False
            self.state = BotState.DEAD
            # Zero velocity so corpse stays still
            self.body.set_velocity((0.0, 0.0, 0.0))
            self.body.set_angular_velocity((0.0, 0.0, 0.0))

    # ── Update ────────────────────────────────────────────────────────────────

    def update(
        self,
        dt: float,
        game_time: float,
        world: f3d.World,
        player_pos: np.ndarray,
        player_alive: bool,
        other_bots: list[Bot],
        zone_radius: float,
        np_rng: np.random.Generator,
    ) -> bool:
        """Update AI. Returns True if this bot fired a shot this frame."""
        if not self.is_alive:
            return False

        self.weapon.update(dt)

        # ── LoS / target selection (throttled) ────────────────────────────────
        self._los_timer += dt
        if self._los_timer >= self._los_interval:
            self._los_timer = 0.0
            self._resolve_target(world, player_pos, player_alive, other_bots, game_time)

        # ── Zone survival ─────────────────────────────────────────────────────
        dx_c = self.position[0] - ZONE_CENTER[0]
        dy_c = self.position[1] - ZONE_CENTER[1]
        dist_center = math.sqrt(dx_c * dx_c + dy_c * dy_c)
        outside_zone = dist_center > zone_radius * 0.9
        if outside_zone:
            self.zone_retreat_t = 0.5

        # ── State machine ─────────────────────────────────────────────────────
        self._transition_states(game_time)

        # ── Movement ──────────────────────────────────────────────────────────
        self._move(dt, outside_zone)

        # ── Shooting ──────────────────────────────────────────────────────────
        return self._shoot(dt, game_time, world, np_rng)

    # ── Target resolution ─────────────────────────────────────────────────────

    def _resolve_target(
        self,
        world: f3d.World,
        player_pos: np.ndarray,
        player_alive: bool,
        other_bots: list[Bot],
        game_time: float,
    ) -> None:
        """Find the highest-priority visible target."""
        # 1. Player (highest priority)
        if player_alive:
            if self._can_see(world, self.eye_pos, player_pos, BOT_SIGHT_RANGE):
                self.target = BotTarget(
                    position=player_pos.copy() + np.array([0, 0, 1.0]),
                    is_player=True,
                )
                self.saw_target_at = game_time
                return

        # 2. Nearest visible bot (battle royale — everyone vs everyone)
        nearest_bot: Bot | None = None
        nearest_dist = BOT_SIGHT_RANGE
        for other in other_bots:
            if not other.is_alive or other is self:
                continue
            dist = float(np.linalg.norm(self.position - other.position))
            if dist >= nearest_dist:
                continue
            if self._can_see(world, self.eye_pos, other.position + np.array([0,0,1.0]), BOT_SIGHT_RANGE):
                nearest_bot = other
                nearest_dist = dist

        if nearest_bot is not None:
            self.target = BotTarget(
                position=nearest_bot.position.copy() + np.array([0, 0, 1.0]),
                is_player=False,
                bot_ref=nearest_bot,
            )
            self.saw_target_at = game_time
            return

        # Lost target
        self.target = None

    def _can_see(
        self,
        world: f3d.World,
        from_pos: np.ndarray,
        to_pos: np.ndarray,
        max_range: float,
    ) -> bool:
        diff = to_pos - from_pos
        dist = float(np.linalg.norm(diff))
        if dist > max_range:
            return False
        direction = diff / (dist + 1e-12)
        hit = world.raycast(from_pos, direction, max_dist=dist + 0.5)
        if hit is None:
            return True
        return hit.distance >= dist * 0.92

    # ── State transitions ─────────────────────────────────────────────────────

    def _transition_states(self, game_time: float) -> None:
        if self.state == BotState.DEAD:
            return

        has_target = self.target is not None
        tgt_dist = (
            float(np.linalg.norm(self.position - self.target.position))
            if has_target else 999.0
        )

        if self.state == BotState.PATROL:
            if has_target:
                self.state = BotState.ALERT
                self.reaction_timer = 0.65

        elif self.state == BotState.ALERT:
            if has_target and tgt_dist < BOT_SHOOT_RANGE:
                if self.reaction_timer <= 0:
                    self.state = BotState.COMBAT
                    # Pick strafe direction randomly per engagement
                    self.strafe_dir = 1.0 if self._rng.random() > 0.5 else -1.0
            elif game_time - self.saw_target_at > 6.0:
                self.state = BotState.PATROL
            self.reaction_timer = max(0.0, self.reaction_timer - self._los_interval)

        elif self.state == BotState.COMBAT:
            if not has_target and game_time - self.saw_target_at > 5.0:
                self.state = BotState.PATROL
            elif tgt_dist > BOT_SHOOT_RANGE * 1.4:
                self.state = BotState.ALERT
            if self.hp < BOT_MAX_HP * 0.25:
                self.state = BotState.RETREAT

        elif self.state == BotState.RETREAT:
            if self.hp > BOT_MAX_HP * 0.55 or not has_target:
                self.state = BotState.PATROL

    # ── Movement ──────────────────────────────────────────────────────────────

    def _move(self, dt: float, outside_zone: bool) -> None:
        move_dir = np.zeros(3, dtype=np.float64)

        if self.zone_retreat_t > 0 or outside_zone:
            to_center = np.array([ZONE_CENTER[0], ZONE_CENTER[1], 0.0]) - self.position
            tc_len = float(np.linalg.norm(to_center[:2]))
            if tc_len > 1e-9:
                move_dir[:2] = to_center[:2] / tc_len
            self.zone_retreat_t = max(0.0, self.zone_retreat_t - dt)

        elif self.state == BotState.PATROL:
            to_target = self.patrol_target - self.position
            dist = float(np.linalg.norm(to_target[:2]))
            if dist < 3.0:
                self._pick_patrol_target()
            else:
                move_dir[:2] = to_target[:2] / (dist + 1e-9)

        elif self.state in (BotState.ALERT, BotState.COMBAT) and self.target is not None:
            tgt_pos = self.target.position
            to_tgt = tgt_pos - self.position
            dist = float(np.linalg.norm(to_tgt[:2]))
            if self.state == BotState.COMBAT:
                ideal = BOT_SHOOT_RANGE * 0.55
                if dist > ideal + 4:
                    move_dir[:2] = to_tgt[:2] / (dist + 1e-9)
                elif dist < ideal - 4:
                    move_dir[:2] = -to_tgt[:2] / (dist + 1e-9)
                # Strafe perpendicular to target
                perp = np.array([-to_tgt[1], to_tgt[0], 0.0])
                p_len = float(np.linalg.norm(perp))
                if p_len > 1e-9:
                    move_dir[:2] += perp[:2] / p_len * 0.4 * self.strafe_dir
            else:
                if dist > 1e-9:
                    move_dir[:2] = to_tgt[:2] / dist

        elif self.state == BotState.RETREAT and self.target is not None:
            away = self.position - self.target.position
            a_len = float(np.linalg.norm(away[:2]))
            if a_len > 1e-9:
                move_dir[:2] = away[:2] / a_len

        # Stuck detection
        pos_delta = float(np.linalg.norm(self.position[:2] - self.last_pos[:2]))
        if pos_delta < 0.06 * dt * BOT_MOVE_SPEED:
            self.stuck_timer += dt
            if self.stuck_timer > 0.7:
                self.stuck_timer = 0.0
                angle = self._rng.uniform(0.8, 1.8)
                c, s = math.cos(angle), math.sin(angle)
                ox, oy = move_dir[0], move_dir[1]
                move_dir[0] = c * ox - s * oy
                move_dir[1] = s * ox + c * oy
        else:
            self.stuck_timer = 0.0
        self.last_pos = self.position.copy()

        m_len = float(np.linalg.norm(move_dir[:2]))
        cur_vel = self.body.velocity.copy()
        if m_len > 1e-9:
            move_dir[:2] /= m_len
            target_vel = move_dir * BOT_MOVE_SPEED
            # Keep existing Z velocity (gravity-controlled)
            cur_vel[:2] = target_vel[:2]
        else:
            cur_vel[:2] = [0.0, 0.0]
        self.body.set_velocity(cur_vel)

    # ── Shooting ──────────────────────────────────────────────────────────────

    SHOOT_INTERVAL = 1.1   # seconds between shots

    def _shoot(
        self,
        dt: float,
        game_time: float,
        world: f3d.World,
        np_rng: np.random.Generator,
    ) -> bool:
        if self.state != BotState.COMBAT or self.target is None:
            return False
        if game_time - self.last_shot_t < self.SHOOT_INTERVAL:
            return False
        if self.weapon.ammo <= 0:
            self.weapon.start_reload()
            return False
        if not self.weapon.ready:
            return False

        tgt_pos = self.target.position
        diff = tgt_pos - self.eye_pos
        dist = float(np.linalg.norm(diff))
        if dist < 0.5 or dist > self.weapon.data["range"]:
            return False

        acc = _accuracy_at(dist)
        if self._rng.random() > acc:
            # Miss — still consume shot but don't deal damage
            self.weapon.consume()
            self.last_shot_t = game_time
            return True

        direction = diff / (dist + 1e-12)
        _result = shoot_ray(
            world, self.eye_pos, direction, self.weapon, np_rng,
            exclude_name=self.name,
        )
        self.weapon.consume()
        self.last_shot_t = game_time
        return True

    def _pick_patrol_target(self) -> None:
        angle = self._rng.uniform(0, 2 * math.pi)
        r = self._rng.uniform(8, BOT_PATROL_RADIUS)
        self.patrol_target = self.position + np.array([
            r * math.cos(angle), r * math.sin(angle), 0.0
        ])


# ── Factory ───────────────────────────────────────────────────────────────────

def create_bots(
    world: f3d.World,
    spawn_positions: list[np.ndarray],
    count: int = BOT_COUNT,
) -> list[Bot]:
    """Spawn *count* bots using plain capsule bodies (no CharacterController)."""
    weapon_mix = ["pistol"] * 6 + ["smg"] * 5 + ["rifle"] * 4 + ["shotgun"] * 4
    rng = random.Random(123)
    bots: list[Bot] = []

    for i in range(count):
        pos = spawn_positions[i % len(spawn_positions)]
        offset = np.array([rng.uniform(-4, 4), rng.uniform(-4, 4), 0.0])
        spawn = (pos + offset).astype(float)
        spawn[2] = 1.0

        name = f"bot_{i:02d}"
        kind = weapon_mix[i % len(weapon_mix)]

        # Plain capsule body — no CharacterController overhead
        body = world.add_capsule(
            radius=PLAYER_RADIUS,
            half_length=max(0.01, PLAYER_HEIGHT / 2.0 - PLAYER_RADIUS),
            position=tuple(spawn),
            mass=80.0,
            name=name,
            friction=0.3,
            restitution=0.0,
        )

        bot = Bot(
            body=body,
            name=name,
            weapon=WeaponInstance.spawn(kind),
            _rng=random.Random(i * 37 + 7),
        )
        bot._pick_patrol_target()
        bots.append(bot)

    return bots
