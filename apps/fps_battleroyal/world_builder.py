"""Procedural world construction for the battle royale map.

Map name: "Abandoned Facility"
Layout (200 × 200 m):
  - Central factory complex (main hall + 2 annexes)
  - Storage yard with rusted containers (NW quadrant)
  - Ruined residential block (NE)
  - Industrial plant / pipes (SE)
  - Market alley (SW)
  - 4 guard towers at corners
  - Scattered debris, barriers, and rock outcrops
  - 16 weapon pickup spots
  - 36 zone boundary pillars
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


# ── Material helpers ──────────────────────────────────────────────────────────

def _mat(color, roughness=0.85, metallic=0.0, emissive=0.0):
    return f3d.Material(
        color=color, roughness=roughness, metallic=metallic, emissive=emissive
    )


M_GROUND    = _mat(C_GROUND,        roughness=0.95)
M_DIRT      = _mat(C_DIRT,          roughness=0.95)
M_CONCRETE  = _mat(C_CONCRETE,      roughness=0.88)
M_CONC_D    = _mat(C_CONCRETE_DARK, roughness=0.88)
M_STEEL     = _mat(C_METAL_STEEL,   roughness=0.35, metallic=0.75)
M_RUST      = _mat(C_METAL_RUST,    roughness=0.80, metallic=0.25)
M_ORANGE    = _mat(C_METAL_ORANGE,  roughness=0.60, metallic=0.50)
M_ASPHALT   = _mat(C_ASPHALT,       roughness=0.90)
M_GLASS     = _mat(C_GLASS,         roughness=0.10, metallic=0.90)
M_WOOD      = _mat(C_WOOD_DARK,     roughness=0.92)
M_PICKUP    = f3d.Material(color=C_PICKUP, roughness=0.2, metallic=0.6, emissive=1.8)
M_ZONE      = f3d.Material(color=C_ZONE_PILLAR, roughness=0.3, metallic=0.8, emissive=3.5)


# ── Box helpers ───────────────────────────────────────────────────────────────

def _box(world, size, pos, mat=M_CONCRETE, static=True, name=None):
    return world.add_box(
        size=size, position=pos, static=static, material=mat,
        **({"name": name} if name else {}),
    )


def _box_at(world, sx, sy, sz, px, py, pz=None, mat=M_CONCRETE, name=None):
    z = pz if pz is not None else sz / 2
    return _box(world, (sx, sy, sz), (px, py, z), mat=mat, name=name)


# ── Sub-builders ──────────────────────────────────────────────────────────────

def _build_central_factory(world):
    """Large factory complex in the center of the map."""
    # Main hall: 44×22×11 m
    _box_at(world, 44, 22, 0.8, 0, 0, pz=0.4, mat=M_ASPHALT)        # floor slab
    _box_at(world, 1.2, 22, 11, -22.6, 0, mat=M_CONCRETE)            # W wall
    _box_at(world, 1.2, 22, 11,  22.6, 0, mat=M_CONCRETE)            # E wall
    _box_at(world, 44, 1.2, 11, 0, -11.6, mat=M_CONC_D)              # S wall
    _box_at(world, 44, 1.2, 11, 0,  11.6, mat=M_CONC_D)              # N wall
    # Roof with hole (3 panels)
    _box_at(world, 14, 22, 1.0, -15, 0, pz=11.5, mat=M_CONC_D)
    _box_at(world, 14, 22, 1.0,  15, 0, pz=11.5, mat=M_CONC_D)
    _box_at(world, 44,  7, 1.0, 0, -7.5, pz=11.5, mat=M_CONC_D)
    # Interior pillars (4×4 grid pattern)
    for px in [-12, -4, 4, 12]:
        for py in [-4, 4]:
            _box_at(world, 1.2, 1.2, 10, px, py, mat=M_CONCRETE)
    # Elevated platform / catwalk along N wall
    _box_at(world, 40, 4, 0.4, 0, 9, pz=5.2, mat=M_STEEL)
    # Ramp up to catwalk
    _box_at(world, 1.5, 4.5, 0.3, -18, 7.5, pz=4.85, mat=M_STEEL)
    # Windows (dark glass insets, flush with walls)
    for py in [-6, 0, 6]:
        _box_at(world, 0.3, 3.5, 4.0, -23.3, py, pz=6.5, mat=M_GLASS)
        _box_at(world, 0.3, 3.5, 4.0,  23.3, py, pz=6.5, mat=M_GLASS)

    # South annex: 20×12×7m
    _box_at(world, 20, 0.8, 7, 0, -18.4, mat=M_CONC_D)
    _box_at(world, 0.8, 12, 7, -10.4, -24, mat=M_CONCRETE)
    _box_at(world, 0.8, 12, 7,  10.4, -24, mat=M_CONCRETE)
    _box_at(world, 20, 0.8, 7, 0, -29.6, mat=M_CONC_D)
    _box_at(world, 20, 12, 0.8, 0, -24, pz=7.4, mat=M_CONC_D)        # roof

    # North annex: 16×10×6m
    _box_at(world, 16, 0.8, 6, 0, 16.4, mat=M_CONC_D)
    _box_at(world, 0.8, 10, 6, -8.4, 21, mat=M_CONCRETE)
    _box_at(world, 0.8, 10, 6,  8.4, 21, mat=M_CONCRETE)
    _box_at(world, 16, 0.8, 6, 0, 25.6, mat=M_CONC_D)
    _box_at(world, 16, 10, 0.8, 0, 21, pz=6.4, mat=M_CONC_D)

    # Chimneys
    _box_at(world, 3, 3, 18,  18, -22, mat=M_CONC_D)
    _box_at(world, 2, 2, 14, -14, -22, mat=M_CONC_D)
    _box_at(world, 1.4, 1.4, 3, 18, -22, pz=19.5, mat=M_STEEL)       # chimney cap

    # Pipe runs (horizontal)
    _box_at(world, 25, 0.8, 0.8, 4, -15, pz=8.0, mat=M_STEEL)
    _box_at(world, 0.8, 12, 0.8, -9, -20, pz=5.0, mat=M_STEEL)


def _build_container_yard(world):
    """NW quadrant: stacked shipping containers for CQC cover."""
    containers = [
        # (x,  y,  z_base, rotation_z)
        (-48, 50, 0, 0), (-42, 50, 0, 0), (-36, 50, 0, 0),
        (-48, 57, 0, 0), (-42, 57, 0, 0),
        # stacked layer
        (-48, 50, 2.5, 0), (-42, 50, 2.5, 0),
        # cross-oriented
        (-50, 62, 0, 90), (-44, 62, 0, 90), (-38, 62, 0, 90),
        (-30, 55, 0, 45),
        # separate cluster further NW
        (-70, 45, 0, 0), (-65, 45, 0, 0),
        (-70, 45, 2.5, 0),
    ]
    for (cx, cy, cz, rot) in containers:
        if rot == 90:
            world.add_box(
                size=(2.6, 6.1, 2.5),
                position=(cx, cy, cz + 1.25),
                static=True, material=M_RUST,
            )
        else:
            world.add_box(
                size=(6.1, 2.6, 2.5),
                position=(cx, cy, cz + 1.25),
                static=True, material=M_RUST,
            )

    # Orange safety containers (accent)
    for pos in [(-55, 52, 0), (-62, 58, 0)]:
        world.add_box(
            size=(6.1, 2.6, 2.5),
            position=(pos[0], pos[1], pos[2] + 1.25),
            static=True, material=M_ORANGE,
        )


def _build_ruins(world):
    """NE quadrant: bombed-out residential ruins."""
    # Ruined block A: walls of different heights
    _box_at(world, 16, 0.8, 8, 55, 50, mat=M_CONC_D)
    _box_at(world, 16, 0.8, 5, 55, 66, mat=M_CONC_D)    # shorter front
    _box_at(world, 0.8, 16, 8, 47, 58, mat=M_CONCRETE)
    _box_at(world, 0.8, 16, 3, 63, 58, mat=M_CONC_D)    # broken wall
    _box_at(world, 16, 16, 0.8, 55, 58, pz=5.5, mat=M_CONC_D)  # partial roof

    # Ruined block B (slightly rotated feel — use offset)
    _box_at(world, 12, 0.8, 6, 75, 42, mat=M_CONC_D)
    _box_at(world, 0.8, 10, 4, 69, 47, mat=M_CONCRETE)
    _box_at(world, 0.8, 10, 6, 81, 47, mat=M_CONC_D)

    # Debris mounds (rounded sphere-like piles)
    for (px, py) in [(60, 45), (52, 70), (78, 55), (65, 60)]:
        world.add_sphere(
            radius=1.8, position=(px, py, 1.8), static=True, material=M_CONC_D
        )
        world.add_box(
            size=(3, 2, 1.2), position=(px + 1, py - 1, 0.6),
            static=True, material=M_CONCRETE,
        )

    # Broken walls (half-height)
    for (px, py, sx, sy) in [
        (48, 42, 4, 0.4), (58, 42, 3, 0.4), (72, 65, 0.4, 5),
        (82, 60, 5, 0.4),
    ]:
        _box_at(world, sx, sy, 1.2, px, py, mat=M_CONC_D)


def _build_industrial(world):
    """SE quadrant: industrial plant with tanks and pipes."""
    # Main tank (sphere)
    world.add_sphere(radius=6.0, position=(55, -45, 6.0), static=True, material=M_STEEL)
    world.add_sphere(radius=4.0, position=(70, -55, 4.0), static=True, material=M_RUST)
    # Tank platforms / bases
    _box_at(world, 14, 14, 2, 55, -45, mat=M_STEEL)
    _box_at(world, 10, 10, 2, 70, -55, mat=M_RUST)

    # Pipe structures
    _box_at(world, 0.8, 25, 0.8, 45, -40, pz=5.0, mat=M_STEEL)
    _box_at(world, 20, 0.8, 0.8, 55, -28, pz=7.0, mat=M_STEEL)
    _box_at(world, 0.8, 0.8, 12, 40, -28, mat=M_STEEL)   # vertical pipe
    _box_at(world, 0.8, 0.8, 10, 65, -28, mat=M_STEEL)

    # Pump house
    _box_at(world, 10, 8, 6, 42, -60, mat=M_CONC_D)
    _box_at(world, 0.8, 8, 6, 37, -60, mat=M_CONCRETE)

    # Machinery / barriers
    for x_off in [-3, 0, 3]:
        _box_at(world, 2, 2, 3, 45 + x_off, -50, mat=M_ORANGE)


def _build_market(world):
    """SW quadrant: market district with alleys and low buildings."""
    # Row of market stalls / small buildings
    stalls = [(-60, -35), (-60, -45), (-60, -55), (-70, -30), (-70, -40), (-70, -50)]
    for (px, py) in stalls:
        _box_at(world, 8, 6, 4, px, py, mat=M_CONCRETE)
        # Awning
        _box_at(world, 9, 2, 0.3, px, py - 4, pz=4.15, mat=M_RUST)

    # Market hall (larger)
    _box_at(world, 20, 0.8, 7, -50, -65, mat=M_CONC_D)
    _box_at(world, 0.8, 16, 7, -41, -72, mat=M_CONCRETE)
    _box_at(world, 0.8, 16, 7, -61, -72, mat=M_CONCRETE)
    _box_at(world, 20, 0.8, 7, -50, -79, mat=M_CONC_D)
    _box_at(world, 20, 16, 0.8, -50, -72, pz=7.4, mat=M_CONC_D)

    # Barricades and planters along market street
    for y_off in [-30, -38, -46, -54, -62]:
        _box_at(world, 0.4, 2.5, 1.5, -43, y_off, mat=M_WOOD)
    for y_off in [-34, -42, -50, -58]:
        _box_at(world, 0.4, 2.5, 1.5, -52, y_off, mat=M_WOOD)


def _build_towers(world):
    """4 guard towers near the map corners."""
    positions = [
        (-80, -80), (80, -80), (-80, 80), (80, 80)
    ]
    for (px, py) in positions:
        _box_at(world, 4, 4, 14, px, py, mat=M_CONCRETE)     # shaft
        _box_at(world, 8, 8, 0.6, px, py, pz=14.6, mat=M_STEEL)  # floor
        # Parapet walls
        for (ox, oy, sx, sy) in [
            (0, 4.4, 8, 0.4), (0, -4.4, 8, 0.4),
            (4.4, 0, 0.4, 8), (-4.4, 0, 0.4, 8),
        ]:
            _box_at(world, sx, sy, 1.2, px + ox, py + oy, pz=15.5, mat=M_CONCRETE)
        # Ladder suggestion (thin box)
        _box_at(world, 0.1, 0.6, 14, px + 2.2, py, mat=M_STEEL)


def _build_open_areas(world):
    """Scatter cover objects across open areas."""
    rng = random.Random(42)

    # Concrete barriers (highway-style) across the map
    barrier_spots = [
        (30, -40), (-30, 40), (15, 55), (-15, -55),
        (45, 20), (-45, -20), (20, -70), (-20, 70),
        (60, 5), (-60, -5), (5, 60), (-5, -60),
    ]
    for (px, py) in barrier_spots:
        _box_at(world, 3.5, 0.5, 1.4, px, py, mat=M_CONCRETE)

    # Rock outcrops (sphere clusters)
    rock_spots = [
        (35, 35), (-35, -35), (75, 10), (-75, -10),
        (10, -75), (-10, 75), (50, -70), (-50, 70),
    ]
    for (px, py) in rock_spots:
        world.add_sphere(
            radius=rng.uniform(1.5, 2.8),
            position=(px, py, rng.uniform(1.5, 2.8)),
            static=True, material=M_CONC_D,
        )

    # Low walls scattered in mid-map for cross-fire cover
    walls = [
        (35, 0, 6, 0.4, 1.5), (-35, 0, 6, 0.4, 1.5),
        (0, 35, 0.4, 6, 1.5), (0, -35, 0.4, 6, 1.5),
        (25, 15, 5, 0.4, 1.2), (-25, -15, 5, 0.4, 1.2),
        (-20, 35, 0.4, 5, 1.2), (20, -35, 0.4, 5, 1.2),
    ]
    for (px, py, sx, sy, sz) in walls:
        _box_at(world, sx, sy, sz, px, py, mat=M_CONC_D)

    # Vehicle wrecks: flat box body + 4 sphere wheels
    wrecks = [(38, -25), (-38, 25), (65, 35), (-65, -35)]
    for (px, py) in wrecks:
        _box_at(world, 4.5, 2.0, 1.4, px, py, pz=0.7, mat=M_RUST)
        for (ox, oy) in [(-1.5, 0.9), (1.5, 0.9), (-1.5, -0.9), (1.5, -0.9)]:
            world.add_sphere(
                radius=0.38, position=(px + ox, py + oy, 0.38),
                static=True, material=M_STEEL,
            )


def _build_zone_pillars(world) -> list[f3d.Body]:
    """36 emissive blue pillars that form the zone boundary ring."""
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


def _place_pickups(world, rng: random.Random) -> list[WeaponPickup]:
    """Scatter weapon pickups at fixed strategic spots."""
    pickup_spots = [
        # (x, y, weapon_kind)
        (-45, 52, "rifle"),    (-38, 60, "smg"),
        (52, 48, "shotgun"),   (60, 58, "sniper"),
        (-55, -40, "smg"),     (-42, -48, "rifle"),
        (42, -45, "shotgun"),  (55, -60, "rifle"),
        (-22, 22, "smg"),      (22, -22, "smg"),
        (-15, -18, "rifle"),   (18, 14, "rifle"),
        (0, -48, "sniper"),    (0, 48, "sniper"),
        (72, -20, "shotgun"),  (-72, 20, "shotgun"),
    ]
    pickups = []
    for (px, py, kind) in pickup_spots:
        body = world.add_box(
            size=(0.7, 0.35, 0.18),
            position=(px, py, 0.09),
            static=True,
            material=M_PICKUP,
            name=f"pickup_{kind}_{len(pickups)}",
        )
        pickups.append(WeaponPickup(body=body, weapon_kind=kind))
    return pickups


def _bot_spawn_positions(n: int) -> list[np.ndarray]:
    """Deterministic spread of spawn positions around the map perimeter."""
    rng = random.Random(99)
    positions = []
    while len(positions) < n:
        # Random position inside map, away from center
        r = rng.uniform(35, MAP_HALF - 10)
        a = rng.uniform(0, 2 * math.pi)
        x = r * math.cos(a)
        y = r * math.sin(a)
        positions.append(np.array([x, y, 1.0]))
    return positions


# ── Main entry point ──────────────────────────────────────────────────────────

def build_world(world: f3d.World) -> WorldAssets:
    """Construct the full map and return references to dynamic assets."""
    rng = random.Random(7)

    # Ground plane (large flat slab)
    world.add_box(
        size=(MAP_HALF * 2, MAP_HALF * 2, 0.5),
        position=(0, 0, -0.25),
        static=True,
        material=M_GROUND,
        name="ground",
    )

    # Sections
    _build_central_factory(world)
    _build_container_yard(world)
    _build_ruins(world)
    _build_industrial(world)
    _build_market(world)
    _build_towers(world)
    _build_open_areas(world)

    # Dynamic assets
    zone_pillars = _build_zone_pillars(world)
    pickups = _place_pickups(world, rng)

    # Bot spawn positions (keep them from overlapping structures)
    bot_spawns = _bot_spawn_positions(25)

    return WorldAssets(
        zone_pillars=zone_pillars,
        pickups=pickups,
        bot_spawn_positions=bot_spawns,
    )
