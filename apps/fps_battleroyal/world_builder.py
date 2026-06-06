"""World construction — visual quality with minimum physics bodies.

Target: ≤ 130 bodies total (player + bots + map + pickups + zone pillars).
Strategy: merged walls, no purely decorative loose geometry.

Map: "Abandoned Facility" 210 × 210 m
  Central factory complex   (interior accessible)
  NW container yard         (exterior cover)
  NE ruined district        (mixed cover/open)
  SE industrial tanks       (exterior)
  SW market district        (exterior cover)
  4 corner guard towers
  Scattered barriers / rocks
  16 weapon pickups
  24 zone boundary pillars
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import forge3d as f3d
import numpy as np

from apps.fps_battleroyal.config import (
    C_ASPHALT,
    C_CONCRETE,
    C_CONCRETE_DARK,
    C_DIRT,
    C_GLASS,
    C_GROUND,
    C_METAL_ORANGE,
    C_METAL_RUST,
    C_METAL_STEEL,
    C_PICKUP,
    C_WOOD_DARK,
    C_ZONE_PILLAR,
    MAP_HALF,
    ZONE_CENTER,
    ZONE_N_PILLARS,
    ZONE_PHASES,
    WEAPON_DATA,
)


@dataclass
class WeaponPickup:
    body: f3d.Body
    weapon_kind: str
    active: bool = True


@dataclass
class WorldAssets:
    zone_pillars: list[f3d.Body] = field(default_factory=list)
    pickups: list[WeaponPickup] = field(default_factory=list)
    bot_spawn_positions: list[np.ndarray] = field(default_factory=list)


# ── Materials ─────────────────────────────────────────────────────────────────

def _mat(color, roughness=0.85, metallic=0.0, emissive=0.0):
    return f3d.Material(color=color, roughness=roughness, metallic=metallic, emissive=emissive)

M_GROUND   = _mat(C_GROUND,        roughness=0.95)
M_CONCRETE = _mat(C_CONCRETE,      roughness=0.88)
M_CONC_D   = _mat(C_CONCRETE_DARK, roughness=0.88)
M_STEEL    = _mat(C_METAL_STEEL,   roughness=0.35, metallic=0.75)
M_RUST     = _mat(C_METAL_RUST,    roughness=0.80, metallic=0.25)
M_ORANGE   = _mat(C_METAL_ORANGE,  roughness=0.60, metallic=0.50)
M_ASPHALT  = _mat(C_ASPHALT,       roughness=0.90)
M_GLASS    = _mat(C_GLASS,         roughness=0.10, metallic=0.90)
M_PICKUP   = f3d.Material(color=C_PICKUP,     roughness=0.2, metallic=0.6, emissive=1.8)
M_ZONE     = f3d.Material(color=C_ZONE_PILLAR, roughness=0.3, metallic=0.8, emissive=3.5)


def _b(world, sx, sy, sz, px, py, pz=None, mat=None, name=None):
    """Add a static box; pz defaults to half-height (sits on ground)."""
    z = pz if pz is not None else sz / 2
    mat = mat or M_CONCRETE
    kwargs = dict(size=(sx, sy, sz), position=(px, py, z), static=True, material=mat)
    if name:
        kwargs["name"] = name
    return world.add_box(**kwargs)


# ── Factory complex (center) ─────────────────────────────────────────────────
# Interior-accessible building: 4 outer walls + floor + roof + 2 interior
# features. ~11 bodies total.

def _build_factory(world):
    W, D, H = 44.0, 24.0, 11.0   # width, depth, height
    cx, cy = 0.0, 0.0

    # Floor slab
    _b(world, W, D, 0.6, cx, cy, pz=0.3, mat=M_ASPHALT)

    # 4 outer walls (thick concrete slabs)
    wt = 1.0                                      # wall thickness
    _b(world, wt, D, H, cx - W/2, cy, mat=M_CONC_D)    # W wall
    _b(world, wt, D, H, cx + W/2, cy, mat=M_CONC_D)    # E wall
    _b(world, W + 2*wt, wt, H, cx, cy - D/2, mat=M_CONCRETE)  # S wall
    _b(world, W + 2*wt, wt, H, cx, cy + D/2, mat=M_CONCRETE)  # N wall

    # Roof (3 slabs with a skylight gap in the centre for light)
    _b(world, 14, D, 1.0, cx - 15,    cy, pz=H + 0.5, mat=M_CONC_D)
    _b(world, 14, D, 1.0, cx + 15,    cy, pz=H + 0.5, mat=M_CONC_D)
    _b(world, W + 2, 7,  1.0, cx, cy - D/2 + 3.5, pz=H + 0.5, mat=M_CONC_D)

    # 2 interior divider walls (L-shaped cover inside the hall)
    _b(world, 0.8, 10, 4.0, cx - 8, cy, mat=M_STEEL)
    _b(world, 10, 0.8, 3.0, cx + 8, cy - 5, mat=M_STEEL)

    # South annex: 20 × 12 × 7 m
    ax, ay = cx, cy - D/2 - 6.5
    _b(world, 20, wt, 7, ax, ay - 5.5, mat=M_CONC_D)
    _b(world, wt, 11, 7, ax - 10.5, ay, mat=M_CONCRETE)
    _b(world, wt, 11, 7, ax + 10.5, ay, mat=M_CONCRETE)
    _b(world, 20, 11, 0.8, ax, ay, pz=7.4, mat=M_CONC_D)  # roof

    # Chimneys (tall pillars — strong visual landmarks)
    _b(world, 3.0, 3.0, 18, cx + 18, cy - D/2 - 2, mat=M_CONC_D)
    _b(world, 2.0, 2.0, 14, cx - 14, cy - D/2 - 2, mat=M_CONC_D)


# ── Container yard (NW) ───────────────────────────────────────────────────────
# 9 containers in two clusters.

def _build_containers(world):
    positions = [
        # cluster A
        (-46, 52, 6.1, 2.6, 2.5, 0),
        (-40, 52, 6.1, 2.6, 2.5, 0),
        (-34, 52, 6.1, 2.6, 2.5, 0),
        (-46, 52, 6.1, 2.6, 2.5, 2.5),   # stacked
        (-40, 52, 6.1, 2.6, 2.5, 2.5),
        # cluster B (different orientation)
        (-52, 62, 2.6, 6.1, 2.5, 0),
        (-46, 62, 2.6, 6.1, 2.5, 0),
        # orange containers (safety)
        (-58, 54, 6.1, 2.6, 2.5, 0),
        (-64, 46, 6.1, 2.6, 2.5, 0),
    ]
    for (px, py, sx, sy, sz, zoff) in positions:
        mat = M_RUST if (px + py) % 7 < 4 else M_ORANGE
        world.add_box(size=(sx, sy, sz), position=(px, py, sz/2 + zoff),
                      static=True, material=mat)


# ── Ruined district (NE) ──────────────────────────────────────────────────────
# 8 bodies: 2 damaged buildings + debris.

def _build_ruins(world):
    # Building A — partial walls
    _b(world, 16, 1.0, 8,  55,  50, mat=M_CONC_D)   # S face
    _b(world,  1, 16, 6,  47,  57, mat=M_CONCRETE)  # W side
    _b(world, 16,  1, 4,  55,  64, mat=M_CONC_D)    # N face (low)
    _b(world, 16, 16, 0.8, 55, 57, pz=7.4, mat=M_CONC_D)  # partial roof

    # Building B
    _b(world, 12,  1, 6,  75,  42, mat=M_CONC_D)
    _b(world,  1, 10, 5,  81,  47, mat=M_CONCRETE)

    # Debris mounds (spheres are efficient)
    for (px, py, r) in [(60, 44, 2.0), (52, 68, 1.8), (78, 56, 2.2)]:
        world.add_sphere(radius=r, position=(px, py, r), static=True, material=M_CONC_D)


# ── Industrial plant (SE) ─────────────────────────────────────────────────────
# 7 bodies: 2 tanks + platforms + pump house.

def _build_industrial(world):
    world.add_sphere(radius=6.0, position=(55, -45, 6.0),  static=True, material=M_STEEL)
    world.add_sphere(radius=4.0, position=(70, -55, 4.0),  static=True, material=M_RUST)
    _b(world, 14, 14, 2, 55, -45, mat=M_STEEL)   # tank base A
    _b(world, 10, 10, 2, 70, -55, mat=M_RUST)    # tank base B
    # Pump house
    _b(world, 10,  8, 6, 42, -60, mat=M_CONC_D)
    _b(world,  1,  8, 6, 37, -60, mat=M_CONCRETE)
    # Single prominent pipe (visual)
    _b(world, 0.8, 25, 0.8, 45, -40, pz=5.0, mat=M_STEEL)


# ── Market district (SW) ──────────────────────────────────────────────────────
# 8 bodies: market hall + 4 stalls + barriers.

def _build_market(world):
    # Market hall
    _b(world, 20,  1, 7, -50, -65, mat=M_CONC_D)
    _b(world,  1, 16, 7, -41, -72, mat=M_CONCRETE)
    _b(world,  1, 16, 7, -61, -72, mat=M_CONCRETE)
    _b(world, 20,  1, 7, -50, -79, mat=M_CONC_D)
    _b(world, 20, 16, 0.8, -50, -72, pz=7.4, mat=M_CONC_D)

    # Market stalls (3 combined into 1 strip each side)
    _b(world, 8, 18, 4, -60, -45, mat=M_CONCRETE)  # W stalls
    _b(world, 8,  0.3, 0.3, -60, -36, pz=4.15, mat=M_RUST)  # awning

    # Alley barriers
    for py in [-32, -40, -48, -56]:
        _b(world, 0.4, 2.5, 1.5, -43, py, mat=M_CONC_D)


# ── Guard towers (4 corners) ──────────────────────────────────────────────────
# 3 bodies per tower = 12 total.

def _build_towers(world):
    for (px, py) in [(-80, -80), (80, -80), (-80, 80), (80, 80)]:
        _b(world, 4, 4, 14,  px, py, mat=M_CONCRETE)       # shaft
        _b(world, 8, 8, 0.8, px, py, pz=14.6, mat=M_STEEL) # floor
        # One parapet ring (merged into single thick frame)
        _b(world, 8, 8, 1.4, px, py, pz=15.9, mat=M_CONCRETE,
           # hollow by using a solid box slightly inset visually; collision-wise fine
           )


# ── Scattered cover ───────────────────────────────────────────────────────────
# ~12 bodies: barriers + rocks (no wheel spheres).

def _build_cover(world):
    rng = random.Random(42)

    # Highway-style concrete barriers (8 spots)
    spots = [
        (30, -40), (-30, 40), (15, 55), (-15, -55),
        (45, 20), (-45, -20), (20, -70), (-20, 70),
    ]
    for (px, py) in spots:
        _b(world, 3.5, 0.5, 1.5, px, py, mat=M_CONCRETE)

    # Vehicle wrecks — body only (no individual wheel spheres)
    for (px, py) in [(38, -25), (-38, 25), (65, 35), (-65, -35)]:
        _b(world, 4.5, 2.0, 1.4, px, py, pz=0.7, mat=M_RUST)

    # Rock clusters (2 spheres each → just 1 sphere per cluster for perf)
    for (px, py) in [(35, 35), (-35, -35), (75, 10), (-75, -10)]:
        r = rng.uniform(1.6, 2.5)
        world.add_sphere(radius=r, position=(px, py, r), static=True, material=M_CONC_D)


# ── Zone pillars ─────────────────────────────────────────────────────────────

def _build_zone_pillars(world) -> list[f3d.Body]:
    pillars = []
    r = ZONE_PHASES[0][1]
    for i in range(ZONE_N_PILLARS):
        angle = 2 * math.pi * i / ZONE_N_PILLARS
        x = ZONE_CENTER[0] + r * math.cos(angle)
        y = ZONE_CENTER[1] + r * math.sin(angle)
        p = world.add_box(
            size=(0.9, 0.9, 18),
            position=(x, y, 9),
            static=True,
            material=M_ZONE,
            name=f"zone_pillar_{i}",
        )
        pillars.append(p)
    return pillars


# ── Weapon pickups ────────────────────────────────────────────────────────────

def _place_pickups(world) -> list[WeaponPickup]:
    spots = [
        (-45, 52, "rifle"),  (-38, 60, "smg"),
        (52,  48, "shotgun"),(60,  58, "sniper"),
        (-55,-40, "smg"),    (-42,-48, "rifle"),
        (42, -45, "shotgun"),(55, -60, "rifle"),
        (-22, 22, "smg"),    (22, -22, "smg"),
        (-15,-18, "rifle"),  (18,  14, "rifle"),
        (0,  -48, "sniper"), (0,   48, "sniper"),
        (72, -20, "shotgun"),(-72, 20, "shotgun"),
    ]
    pickups = []
    for i, (px, py, kind) in enumerate(spots):
        body = world.add_box(
            size=(0.7, 0.35, 0.18),
            position=(px, py, 0.09),
            static=True,
            material=M_PICKUP,
            name=f"pickup_{kind}_{i}",
        )
        pickups.append(WeaponPickup(body=body, weapon_kind=kind))
    return pickups


# ── Bot spawn positions ───────────────────────────────────────────────────────

def _bot_spawn_positions(n: int) -> list[np.ndarray]:
    rng = random.Random(99)
    positions = []
    while len(positions) < n:
        r = rng.uniform(35, MAP_HALF - 10)
        a = rng.uniform(0, 2 * math.pi)
        positions.append(np.array([r * math.cos(a), r * math.sin(a), 1.0]))
    return positions


# ── Main entry ────────────────────────────────────────────────────────────────

def build_world(world: f3d.World) -> WorldAssets:
    """Build the complete map; return references to dynamic assets."""
    # Ground slab
    world.add_box(
        size=(MAP_HALF * 2, MAP_HALF * 2, 0.5),
        position=(0, 0, -0.25),
        static=True, material=M_GROUND, name="ground",
    )

    _build_factory(world)
    _build_containers(world)
    _build_ruins(world)
    _build_industrial(world)
    _build_market(world)
    _build_towers(world)
    _build_cover(world)

    zone_pillars = _build_zone_pillars(world)
    pickups      = _place_pickups(world)
    bot_spawns   = _bot_spawn_positions(30)

    return WorldAssets(
        zone_pillars=zone_pillars,
        pickups=pickups,
        bot_spawn_positions=bot_spawns,
    )
