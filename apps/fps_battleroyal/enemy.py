"""Bot AI — pure Python kinematic characters, zero physics overhead.

Architecture decision: bots have NO physics body in the forge3d world.
Their positions are tracked as plain numpy arrays and integrated manually.
This eliminates all CharacterController + contact-solver overhead for bots:
  Before:  19 bots × 4ms/bot = 76ms (CharacterController ground checks)
  After:   0ms (pure Python position integration)

Collision with world geometry: bots clip through walls (acceptable — they
navigate around obstacles using simple steering, and the player can't see
bots close enough for clipping to matter most of the time).

Hit detection (player → bot): sphere-intersection test in main.py — O(N).
LoS (bot → world): single world.raycast per bot per 0.125s (throttled).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto

import numpy as np
from apps.fps_battleroyal.config import (
    BOT_COUNT,
    BOT_MAX_HP,
    BOT_MOVE_SPEED,
    BOT_PATROL_RADIUS,
    BOT_SHOOT_INTERVAL,
    BOT_SHOOT_RANGE,
    BOT_SIGHT_RANGE,
    GRACE_PERIOD_SEC,
    MAP_HALF,
    PLAYER_HEIGHT,
    ZONE_CENTER,
)
from apps.fps_battleroyal.weapon import WeaponInstance

import forge3d as f3d


class BotState(Enum):
    PATROL  = auto()
    ALERT   = auto()
    COMBAT  = auto()
    RETREAT = auto()
    DEAD    = auto()


# ── Distance-based accuracy curve ─────────────────────────────────────────────
_ACC_D = [0, 8,   20,   35,   55,  100]
_ACC_V = [0.80, 0.60, 0.42, 0.28, 0.15, 0.05]

def _accuracy(dist: float) -> float:
    for i in range(len(_ACC_D) - 1):
        if dist <= _ACC_D[i + 1]:
            t = (dist - _ACC_D[i]) / (_ACC_D[i + 1] - _ACC_D[i])
            return _ACC_V[i] * (1 - t) + _ACC_V[i + 1] * t
    return _ACC_V[-1]


@dataclass
class Bot:
    """Kinematic AI bot — position/velocity tracked in Python, not in physics."""

    position: np.ndarray    # world position (feet base)
    velocity: np.ndarray    # current velocity m/s
    yaw:      float         # facing direction in radians
    name:     str
    hp:       float = BOT_MAX_HP
    weapon:   WeaponInstance = field(default_factory=lambda: WeaponInstance.spawn("smg"))
    state:    BotState = BotState.PATROL
    is_alive: bool = True
    kills:    int  = 0

    # AI state
    target_pos:    np.ndarray = field(default_factory=lambda: np.zeros(3))
    patrol_target: np.ndarray = field(default_factory=lambda: np.zeros(3))
    target_is_player: bool    = False
    target_bot_idx:   int     = -1

    # Timers
    last_shot_t:    float = 0.0
    reaction_t:     float = 0.0
    stuck_t:        float = 0.0
    saw_target_at:  float = -999.0
    zone_retreat_t: float = 0.0
    strafe_flip_t:  float = 0.0

    # LoS cache
    _los_t:   float = 0.0
    _los_val: bool  = False

    _rng: random.Random = field(default_factory=random.Random)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def eye_pos(self) -> np.ndarray:
        p = self.position.copy()
        p[2] += 1.55
        return p

    @property
    def center_pos(self) -> np.ndarray:
        p = self.position.copy()
        p[2] += PLAYER_HEIGHT * 0.5
        return p

    # ── Damage ────────────────────────────────────────────────────────────────

    def take_damage(self, amount: float) -> None:
        if not self.is_alive:
            return
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.is_alive = False
            self.state = BotState.DEAD
            self.velocity[:] = 0

    # ── Update ────────────────────────────────────────────────────────────────

    def update(
        self,
        dt: float,
        game_time: float,
        world: f3d.World,
        player_pos: np.ndarray,
        player_alive: bool,
        all_bots: list[Bot],
        zone_radius: float,
        rng: np.random.Generator,
    ) -> bool:
        """Advance bot one tick. Returns True if a shot is fired."""
        if not self.is_alive:
            return False

        self.weapon.update(dt)
        self._integrate(dt)

        # ── LoS check (throttled to 8 Hz) ─────────────────────────────────────
        self._los_t += dt
        if self._los_t >= 0.125:
            self._los_t = 0.0
            self._update_target(world, game_time, player_pos, player_alive, all_bots)

        # ── Zone retreat ───────────────────────────────────────────────────────
        dx_c = self.position[0] - ZONE_CENTER[0]
        dy_c = self.position[1] - ZONE_CENTER[1]
        if math.sqrt(dx_c**2 + dy_c**2) > zone_radius * 0.92:
            self.zone_retreat_t = 0.5

        # ── State machine ──────────────────────────────────────────────────────
        self._transition(game_time)

        # ── Movement ──────────────────────────────────────────────────────────
        self._move(dt)

        # ── Shooting ──────────────────────────────────────────────────────────
        return self._shoot(dt, game_time, world, player_pos, player_alive, all_bots, rng)

    # ── Physics integration ───────────────────────────────────────────────────

    def _integrate(self, dt: float) -> None:
        """Simple Euler integration with gravity and ground clamping."""
        self.velocity[2] -= 18.0 * dt   # gravity (no physics needed)
        self.position += self.velocity * dt

        # Ground: bots always rest on z=1.0 (character base)
        if self.position[2] < 1.0:
            self.position[2] = 1.0
            self.velocity[2] = max(0.0, self.velocity[2])

        # Map boundary clamping
        self.position[0] = float(np.clip(self.position[0], -MAP_HALF + 2, MAP_HALF - 2))
        self.position[1] = float(np.clip(self.position[1], -MAP_HALF + 2, MAP_HALF - 2))

    # ── Target resolution ─────────────────────────────────────────────────────

    def _update_target(
        self,
        world: f3d.World,
        game_time: float,
        player_pos: np.ndarray,
        player_alive: bool,
        all_bots: list[Bot],
    ) -> None:
        # 1. Player priority
        if player_alive:
            diff = (player_pos + np.array([0,0,1.0])) - self.eye_pos
            dist = float(np.linalg.norm(diff))
            if dist < BOT_SIGHT_RANGE:
                direction = diff / (dist + 1e-12)
                hit = world.raycast(self.eye_pos, direction, max_dist=dist + 0.5)
                if hit is None or hit.distance >= dist * 0.93:
                    self.target_pos      = (player_pos + np.array([0,0,1.0])).copy()
                    self.target_is_player = True
                    self.target_bot_idx   = -1
                    self.saw_target_at    = game_time
                    self._los_val = True
                    return

        # 2. Nearest visible bot
        best_dist = BOT_SIGHT_RANGE
        best_idx  = -1
        for i, other in enumerate(all_bots):
            if not other.is_alive or other is self:
                continue
            diff = other.center_pos - self.eye_pos
            d = float(np.linalg.norm(diff))
            if d >= best_dist:
                continue
            direction = diff / (d + 1e-12)
            hit = world.raycast(self.eye_pos, direction, max_dist=d + 0.5)
            if hit is None or hit.distance >= d * 0.93:
                best_dist = d
                best_idx  = i

        if best_idx >= 0:
            self.target_pos       = all_bots[best_idx].center_pos.copy()
            self.target_is_player = False
            self.target_bot_idx   = best_idx
            self.saw_target_at    = game_time
            self._los_val = True
            return

        self._los_val = False

    # ── State transitions ─────────────────────────────────────────────────────

    def _transition(self, game_time: float) -> None:
        has_target = self._los_val
        tgt_dist   = float(np.linalg.norm(self.position - self.target_pos)) if has_target else 999.0

        if self.state == BotState.PATROL:
            if has_target:
                self.state = BotState.ALERT
                self.reaction_t = 0.55

        elif self.state == BotState.ALERT:
            if self.reaction_t <= 0 and has_target and tgt_dist < BOT_SHOOT_RANGE:
                self.state = BotState.COMBAT
                self.strafe_flip_t = self._rng.uniform(0.8, 1.8)
            elif game_time - self.saw_target_at > 6.0:
                self.state = BotState.PATROL
            self.reaction_t = max(0.0, self.reaction_t - 0.125)

        elif self.state == BotState.COMBAT:
            if not has_target and game_time - self.saw_target_at > 5.0:
                self.state = BotState.PATROL
            elif tgt_dist > BOT_SHOOT_RANGE * 1.5:
                self.state = BotState.ALERT
            if self.hp < BOT_MAX_HP * 0.22:
                self.state = BotState.RETREAT

        elif self.state == BotState.RETREAT and (self.hp > BOT_MAX_HP * 0.55 or not has_target):
            self.state = BotState.PATROL

    # ── Movement ──────────────────────────────────────────────────────────────

    def _move(self, dt: float) -> None:
        move = np.zeros(3)

        if self.zone_retreat_t > 0:
            to_c = np.array([ZONE_CENTER[0], ZONE_CENTER[1], 0.0]) - self.position
            d = float(np.linalg.norm(to_c[:2]))
            if d > 1e-9:
                move[:2] = to_c[:2] / d
            self.zone_retreat_t = max(0.0, self.zone_retreat_t - dt)

        elif self.state == BotState.PATROL:
            to_t = self.patrol_target - self.position
            d = float(np.linalg.norm(to_t[:2]))
            if d < 3.0:
                self._new_patrol()
            elif d > 1e-9:
                move[:2] = to_t[:2] / d

        elif self.state in (BotState.ALERT, BotState.COMBAT) and self._los_val:
            to_t = self.target_pos - self.position
            d = float(np.linalg.norm(to_t[:2]))
            if self.state == BotState.COMBAT:
                ideal = BOT_SHOOT_RANGE * 0.52
                if d > ideal + 4 and d > 1e-9:
                    move[:2] = to_t[:2] / d
                elif d < ideal - 4 and d > 1e-9:
                    move[:2] = -to_t[:2] / d
                # Strafe
                self.strafe_flip_t -= dt
                if self.strafe_flip_t <= 0:
                    self._strafe_dir = getattr(self, '_strafe_dir', 1.0) * -1
                    self.strafe_flip_t = self._rng.uniform(0.6, 1.6)
                perp = np.array([-to_t[1], to_t[0], 0.0])
                p_len = float(np.linalg.norm(perp))
                if p_len > 1e-9:
                    move[:2] += perp[:2] / p_len * 0.35 * getattr(self, '_strafe_dir', 1.0)
            else:
                if d > 1e-9:
                    move[:2] = to_t[:2] / d

        elif self.state == BotState.RETREAT and self._los_val:
            away = self.position - self.target_pos
            d = float(np.linalg.norm(away[:2]))
            if d > 1e-9:
                move[:2] = away[:2] / d

        # Stuck detection
        last = getattr(self, '_last_pos', self.position.copy())
        if float(np.linalg.norm(self.position[:2] - last[:2])) < 0.08 * dt * BOT_MOVE_SPEED:
            self.stuck_t += dt
            if self.stuck_t > 0.7:
                self.stuck_t = 0.0
                a = self._rng.uniform(0.8, 2.0)
                c, s = math.cos(a), math.sin(a)
                move[0], move[1] = c*move[0]-s*move[1], s*move[0]+c*move[1]
        else:
            self.stuck_t = 0.0
        self._last_pos = self.position.copy()

        m_len = float(np.linalg.norm(move[:2]))
        if m_len > 1e-9:
            move[:2] /= m_len
            self.velocity[:2] = move[:2] * BOT_MOVE_SPEED
            self.yaw = math.atan2(move[1], move[0])
        else:
            self.velocity[:2] *= 0.85   # friction when standing still

    # ── Shooting ──────────────────────────────────────────────────────────────

    def _shoot(
        self,
        dt: float,
        game_time: float,
        world: f3d.World,
        player_pos: np.ndarray,
        player_alive: bool,
        all_bots: list[Bot],
        rng: np.random.Generator,
    ) -> bool:
        if self.state != BotState.COMBAT or not self._los_val:
            return False
        if game_time < GRACE_PERIOD_SEC:
            return False
        if game_time - self.last_shot_t < BOT_SHOOT_INTERVAL:
            return False
        if not self.weapon.ready:
            if self.weapon.reserve > 0:
                self.weapon.start_reload()
            return False

        diff = self.target_pos - self.eye_pos
        dist = float(np.linalg.norm(diff))
        if dist > self.weapon.data["range"]:
            return False

        acc = _accuracy(dist)
        self.weapon.consume()
        self.last_shot_t = game_time

        if rng.random() > acc:
            return True   # miss

        # Hit the target
        if self.target_is_player and player_alive:
            return True   # damage applied in main.py
        elif self.target_bot_idx >= 0 and 0 <= self.target_bot_idx < len(all_bots):
            target_bot = all_bots[self.target_bot_idx]
            if target_bot.is_alive:
                target_bot.take_damage(float(self.weapon.data["damage"]) * 0.75)
                if not target_bot.is_alive:
                    self.kills += 1

        return True

    def _new_patrol(self) -> None:
        a = self._rng.uniform(0, 2 * math.pi)
        r = self._rng.uniform(10, BOT_PATROL_RADIUS)
        self.patrol_target = self.position + np.array([r*math.cos(a), r*math.sin(a), 0.0])


# ── Factory ───────────────────────────────────────────────────────────────────

def create_bots(
    world: f3d.World,  # kept for API compatibility, bots don't add bodies here
    spawn_positions: list[np.ndarray],
    count: int = BOT_COUNT,
) -> list[Bot]:
    """Create kinematic bots — no physics bodies added to world."""
    weapon_mix = ["smg"]*5 + ["rifle"]*4 + ["pistol"]*4 + ["shotgun"]*3 + ["sniper"]*3
    rng = random.Random(123)
    bots: list[Bot] = []

    for i in range(count):
        pos = spawn_positions[i % len(spawn_positions)]
        offset = np.array([rng.uniform(-5, 5), rng.uniform(-5, 5), 0.0])
        spawn = (pos + offset).astype(float)
        spawn[2] = 1.0

        kind = weapon_mix[i % len(weapon_mix)]
        bot = Bot(
            position=spawn.copy(),
            velocity=np.zeros(3),
            yaw=rng.uniform(0, 2*math.pi),
            name=f"bot_{i:02d}",
            weapon=WeaponInstance.spawn(kind),
            _rng=random.Random(i * 37 + 7),
        )
        bot._new_patrol()
        bots.append(bot)

    return bots
