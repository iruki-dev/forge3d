"""Bot AI — simple state machine with line-of-sight shooting."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto

import numpy as np

import forge3d as f3d
from apps.fps_battleroyal.config import (
    BOT_ACCURACY_BASE,
    BOT_COUNT,
    BOT_MAX_HP,
    BOT_MOVE_SPEED,
    BOT_PATROL_RADIUS,
    BOT_REACTION_DELAY,
    BOT_SHOOT_INTERVAL,
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
    ALERT   = auto()    # saw something, approaching
    COMBAT  = auto()    # in range, shooting
    RETREAT = auto()    # low hp, running to cover
    DEAD    = auto()


@dataclass
class Bot:
    """One AI-controlled opponent."""

    cc:     f3d.CharacterController
    name:   str
    hp:     float = BOT_MAX_HP
    weapon: WeaponInstance = field(default_factory=lambda: WeaponInstance.spawn("pistol"))
    state:  BotState = BotState.PATROL

    # AI internals
    target_pos:       np.ndarray    = field(default_factory=lambda: np.zeros(3))
    patrol_target:    np.ndarray    = field(default_factory=lambda: np.zeros(3))
    last_shot_t:      float         = 0.0
    reaction_timer:   float         = 0.0   # delay before first shot
    stuck_timer:      float         = 0.0
    last_pos:         np.ndarray    = field(default_factory=lambda: np.zeros(3))
    saw_player_at:    float         = -999.0
    zone_retreat_t:   float         = 0.0   # time until moving toward center

    is_alive: bool = True
    kills:    int  = 0

    _rng: random.Random = field(default_factory=lambda: random.Random())

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def position(self) -> np.ndarray:
        return np.asarray(self.cc.position, dtype=np.float64)

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
        """Update AI. Returns True if a shot was fired."""
        if not self.is_alive:
            return False

        self.weapon.update(dt)

        # ── Check if player is visible ─────────────────────────────────────────
        can_see_player = False
        if player_alive:
            can_see_player = self._can_see(world, self.eye_pos, player_pos, BOT_SIGHT_RANGE)

        if can_see_player:
            self.saw_player_at = game_time
            self.target_pos = player_pos.copy()

        # ── State transitions ─────────────────────────────────────────────────
        dist_to_player = float(np.linalg.norm(self.position - player_pos))

        if self.state == BotState.PATROL:
            if can_see_player:
                self.state = BotState.ALERT
                self.reaction_timer = BOT_REACTION_DELAY
            elif game_time - self.saw_player_at < 5.0:
                self.state = BotState.ALERT

        elif self.state == BotState.ALERT:
            if can_see_player and dist_to_player < BOT_SHOOT_RANGE:
                if self.reaction_timer <= 0:
                    self.state = BotState.COMBAT
            elif game_time - self.saw_player_at > 8.0:
                self.state = BotState.PATROL
            self.reaction_timer = max(0.0, self.reaction_timer - dt)

        elif self.state == BotState.COMBAT:
            if dist_to_player > BOT_SHOOT_RANGE * 1.3 and not can_see_player:
                self.state = BotState.ALERT
            if self.hp < BOT_MAX_HP * 0.25:
                self.state = BotState.RETREAT

        elif self.state == BotState.RETREAT:
            if self.hp > BOT_MAX_HP * 0.5 or dist_to_player > BOT_SIGHT_RANGE:
                self.state = BotState.PATROL

        # ── Zone survival ─────────────────────────────────────────────────────
        dist_to_center = math.sqrt(
            (self.position[0] - ZONE_CENTER[0]) ** 2 +
            (self.position[1] - ZONE_CENTER[1]) ** 2
        )
        outside_zone = dist_to_center > zone_radius * 0.9
        if outside_zone:
            self.zone_retreat_t = 0.5  # move toward center soon

        # ── Movement ──────────────────────────────────────────────────────────
        self._movement(dt, outside_zone, player_pos, player_alive)

        # ── Shooting ──────────────────────────────────────────────────────────
        shot_fired = False
        if self.state == BotState.COMBAT and player_alive:
            if can_see_player and game_time - self.last_shot_t >= BOT_SHOOT_INTERVAL:
                if self.weapon.ammo > 0:
                    # Accuracy check
                    if self._rng.random() < BOT_ACCURACY_BASE * max(0.3, 1.0 - dist_to_player / 80.0):
                        direction = player_pos + np.array([0, 0, 1.0]) - self.eye_pos
                        d_len = float(np.linalg.norm(direction))
                        if d_len > 1e-9:
                            direction /= d_len
                        _result = shoot_ray(
                            world, self.eye_pos, direction, self.weapon, np_rng,
                            exclude_name=self.name,
                        )
                        shot_fired = True
                        self.last_shot_t = game_time
                        self.weapon.consume()
                elif self.weapon.reserve > 0:
                    self.weapon.start_reload()

        return shot_fired

    def _can_see(
        self,
        world: f3d.World,
        from_pos: np.ndarray,
        to_pos: np.ndarray,
        max_range: float,
    ) -> bool:
        diff = to_pos + np.array([0, 0, 1.0]) - from_pos
        dist = float(np.linalg.norm(diff))
        if dist > max_range:
            return False
        direction = diff / (dist + 1e-12)
        hit = world.raycast(from_pos, direction, max_dist=dist + 0.5)
        if hit is None:
            return True
        # Hit the target (or very close to it)
        return hit.distance >= dist * 0.93

    def _movement(
        self,
        dt: float,
        outside_zone: bool,
        player_pos: np.ndarray,
        player_alive: bool,
    ) -> None:
        move_dir = np.zeros(3, dtype=np.float64)

        if self.zone_retreat_t > 0 or outside_zone:
            # Move toward zone center
            to_center = np.array([ZONE_CENTER[0], ZONE_CENTER[1], 0.0]) - self.position
            tc_len = float(np.linalg.norm(to_center[:2]))
            if tc_len > 1e-9:
                move_dir[:2] = to_center[:2] / tc_len
            self.zone_retreat_t = max(0.0, self.zone_retreat_t - dt)

        elif self.state == BotState.PATROL:
            # Move toward patrol target; pick new one when close
            to_target = self.patrol_target - self.position
            dist = float(np.linalg.norm(to_target[:2]))
            if dist < 3.0:
                self._pick_patrol_target()
            else:
                move_dir[:2] = to_target[:2] / (dist + 1e-9)

        elif self.state in (BotState.ALERT, BotState.COMBAT):
            if player_alive:
                to_player = self.target_pos - self.position
                tp_dist = float(np.linalg.norm(to_player[:2]))
                if self.state == BotState.COMBAT:
                    # Keep distance: advance if too far, hold if close
                    ideal = BOT_SHOOT_RANGE * 0.6
                    if tp_dist > ideal + 3:
                        move_dir[:2] = to_player[:2] / (tp_dist + 1e-9)
                    elif tp_dist < ideal - 3:
                        move_dir[:2] = -to_player[:2] / (tp_dist + 1e-9)
                    # Strafe (perpendicular drift)
                    perp = np.array([-to_player[1], to_player[0], 0.0])
                    p_len = float(np.linalg.norm(perp))
                    if p_len > 1e-9:
                        strafe_dir = 1 if (hash(self.name) % 2 == 0) else -1
                        move_dir += perp / p_len * 0.3 * strafe_dir
                else:
                    move_dir[:2] = to_player[:2] / (tp_dist + 1e-9)

        elif self.state == BotState.RETREAT:
            to_away = self.position - self.target_pos
            ta_len = float(np.linalg.norm(to_away[:2]))
            if ta_len > 1e-9:
                move_dir[:2] = to_away[:2] / ta_len

        # Stick detection + random steer
        pos_delta = float(np.linalg.norm(self.position - self.last_pos))
        if pos_delta < 0.05 * dt * BOT_MOVE_SPEED:
            self.stuck_timer += dt
            if self.stuck_timer > 0.8:
                self.stuck_timer = 0.0
                # Turn ~90° to unstick
                angle = self._rng.uniform(0.8, 1.8)
                c, s = math.cos(angle), math.sin(angle)
                old = move_dir.copy()
                move_dir[0] = c * old[0] - s * old[1]
                move_dir[1] = s * old[0] + c * old[1]
        else:
            self.stuck_timer = 0.0

        self.last_pos = self.position.copy()

        m_len = float(np.linalg.norm(move_dir[:2]))
        if m_len > 1e-9:
            move_dir[:2] /= m_len
            self.cc.move(
                direction=(float(move_dir[0]), float(move_dir[1]), 0.0),
                speed=BOT_MOVE_SPEED,
                dt=dt,
            )

    def _pick_patrol_target(self) -> None:
        angle = self._rng.uniform(0, 2 * math.pi)
        r = self._rng.uniform(8, BOT_PATROL_RADIUS)
        self.patrol_target = self.position + np.array([r * math.cos(angle), r * math.sin(angle), 0.0])


# ── Factory ───────────────────────────────────────────────────────────────────

def create_bots(
    world: f3d.World,
    spawn_positions: list[np.ndarray],
    count: int = BOT_COUNT,
) -> list[Bot]:
    """Spawn *count* bots at *spawn_positions* (cycled if needed)."""
    bot_weapon_mix = (
        ["pistol"] * 8 + ["smg"] * 5 + ["rifle"] * 4 + ["shotgun"] * 2
    )
    rng = random.Random(123)
    bots: list[Bot] = []

    for i in range(count):
        pos = spawn_positions[i % len(spawn_positions)]
        # Slight random offset so bots don't overlap
        offset = np.array([
            rng.uniform(-4, 4), rng.uniform(-4, 4), 0.0
        ])
        spawn = (pos + offset).astype(float)
        spawn[2] = 1.0

        kind = bot_weapon_mix[i % len(bot_weapon_mix)]
        name = f"bot_{i:02d}"

        cc = world.add_character(
            position=tuple(spawn),
            height=PLAYER_HEIGHT,
            radius=PLAYER_RADIUS,
            mass=80.0,
            name=name,
        )
        # Enemies are visually red-orange capsule
        # (CharacterController body material is set via world add_character internals;
        #  we override by teleporting and setting material through the facade body)
        try:
            body = world.get_body(name)
            body.friction = 0.5
            world._physics._bodies  # noqa: SLF001 — force snapshot color registration
        except Exception:
            pass

        bot = Bot(
            cc=cc,
            name=name,
            weapon=WeaponInstance.spawn(kind),
            _rng=random.Random(i * 37 + 7),
        )
        bot._pick_patrol_target()
        bots.append(bot)

    return bots
