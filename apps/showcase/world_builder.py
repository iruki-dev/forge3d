"""Showcase world — Kenney CC0 assets + atmospheric decoration.

Budget: ≤ 225 static bodies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from apps.showcase.models import (
    load_barrel,
    load_bench,
    load_bench_long,
    load_campfire,
    load_column,
    load_crate,
    load_flag,
    load_lamp_post,
    load_obelisk,
    load_potted_plant,
    load_rock_large,
    load_rock_small,
    load_tower_mid,
    load_tower_roof,
    load_tower_section,
    load_tree_crown,
    load_tree_trunk,
    load_wall_section,
    prebuild_all,
)

import forge3d as f3d

# ── Material palette ──────────────────────────────────────────────────────────


def _m(c, r=0.85, me=0.0, em=0.0):
    return f3d.Material(color=c, roughness=r, metallic=me, emissive=em)


M: dict[str, f3d.Material] = {
    # Architecture
    "marble": _m((0.93, 0.91, 0.89), r=0.06),
    "marble_d": _m((0.68, 0.66, 0.63), r=0.08),
    "stone": _m((0.50, 0.47, 0.42), r=0.90),
    "stone_d": _m((0.18, 0.17, 0.15), r=0.93),
    "floor": _m((0.42, 0.39, 0.35), r=0.80),
    "floor_d": _m((0.15, 0.14, 0.13), r=0.91),
    # Metals
    "gold": _m((0.83, 0.68, 0.21), r=0.11, me=0.97),
    "copper": _m((0.72, 0.45, 0.20), r=0.42, me=0.78),
    "steel": _m((0.42, 0.44, 0.46), r=0.28, me=0.88),
    "mirror": _m((0.38, 0.40, 0.42), r=0.05, me=0.97),
    "bronze": _m((0.55, 0.40, 0.18), r=0.55, me=0.70),
    "iron": _m((0.27, 0.26, 0.25), r=0.65, me=0.60),
    "glass_d": _m((0.05, 0.08, 0.13), r=0.04, me=0.94),
    # Nature
    "ground": _m((0.34, 0.32, 0.28), r=0.94),
    "foliage": _m((0.18, 0.48, 0.11), r=0.96),  # medium forest green
    "foliage2": _m((0.24, 0.55, 0.18), r=0.96),  # lighter green
    "foliage_a": _m((0.62, 0.38, 0.10), r=0.92),  # autumn orange-brown
    "bark": _m((0.26, 0.16, 0.08), r=0.94),  # dark brown trunk
    "rock": _m((0.44, 0.42, 0.38), r=0.92),  # grey rock
    "rock_d": _m((0.28, 0.27, 0.24), r=0.94),  # dark rock
    # Furniture
    "wood_lt": _m((0.52, 0.38, 0.20), r=0.82),  # light wood bench
    "iron_lt": _m((0.38, 0.36, 0.34), r=0.60, me=0.70),  # polished iron
    "clay": _m((0.62, 0.42, 0.28), r=0.90),  # terracotta pot
    # Emissive
    "e_b": _m((0.25, 0.55, 1.00), em=3.5),
    "e_c": _m((0.20, 0.90, 0.85), em=3.2),
    "e_a": _m((1.00, 0.70, 0.15), em=2.8),
    "e_r": _m((1.00, 0.22, 0.10), em=3.2),
    "e_g": _m((0.25, 0.95, 0.40), em=3.0),
    "e_v": _m((0.75, 0.20, 1.00), em=3.0),
    "e_w": _m((0.96, 0.96, 1.00), em=4.8),
    "e_p": _m((1.00, 0.38, 0.65), em=3.0),
    "e_l": _m((0.78, 1.00, 0.20), em=2.8),
    "e_fire": _m((1.00, 0.55, 0.05), em=4.0),  # fire orange
    "e_lamp": _m((1.00, 0.90, 0.50), em=3.0),  # warm lamp glow
}

EMISSIVE_9 = ["e_b", "e_c", "e_g", "e_a", "e_w", "e_p", "e_r", "e_v", "e_l"]

PBR_DEMO = [
    ("Marble", _m((0.93, 0.91, 0.89), r=0.06)),
    ("Brushed Steel", _m((0.42, 0.44, 0.46), r=0.28, me=0.88)),
    ("24K Gold", _m((0.83, 0.68, 0.21), r=0.11, me=0.97)),
    ("Dark Glass", _m((0.05, 0.08, 0.13), r=0.04, me=0.94)),
    ("Copper", _m((0.72, 0.45, 0.20), r=0.42, me=0.78)),
    ("Raw Iron", _m((0.27, 0.26, 0.25), r=0.65, me=0.60)),
    ("Polished Stone", _m((0.60, 0.57, 0.52), r=0.22)),
    ("Bronze", _m((0.55, 0.40, 0.18), r=0.55, me=0.70)),
]


# ── Placement helpers ─────────────────────────────────────────────────────────


def _b(w, sx, sy, sz, px, py, pz=None, mat="stone", name=None, dyn=False, mass=1.0):
    z = pz if pz is not None else sz / 2
    km = M[mat] if isinstance(mat, str) else mat
    kw = {"size": (sx, sy, sz), "position": (px, py, z), "material": km}
    kw["mass" if dyn else "static"] = mass if dyn else True
    if name:
        kw["name"] = name
    return w.add_box(**kw)


def _s(w, r, px, py, pz, mat="stone", dyn=False, mass=1.0, name=None):
    km = M[mat] if isinstance(mat, str) else mat
    kw = {"radius": r, "position": (px, py, pz), "material": km}
    kw["mass" if dyn else "static"] = mass if dyn else True
    if name:
        kw["name"] = name
    return w.add_sphere(**kw)


def _col(w, mesh, px, py, mat="marble"):
    w.add_mesh(mesh, position=(px, py, 0), static=True, material=M[mat])


_NO_COLLIDE = {"collision_mask": 0}  # visual-only mesh: skipped in physics broadphase


def _tree(w, crown, trunk, px, py, crown_mat="foliage"):
    """Two-piece tree: thin box trunk (cheap) + mesh crown (visual-only)."""
    _b(w, 0.45, 0.45, 2.8, px, py, pz=1.4, mat="bark")  # box trunk
    w.add_mesh(crown, position=(px, py, 0), static=True, material=M[crown_mat], **_NO_COLLIDE)


def _lamp(w, mesh, px, py, mat="iron_lt", emissive="e_lamp", lamp_h=6.5):
    """Lamp post: visual-only mesh + collidable emissive sphere cap."""
    w.add_mesh(mesh, position=(px, py, 0), static=True, material=M[mat], **_NO_COLLIDE)
    _s(w, 0.30, px, py, lamp_h + 0.2, mat=emissive)  # sphere is collidable (blocks player)


def _bench(w, mesh, px, py, angle=0.0, mat="wood_lt"):
    import numpy as np

    q = np.array([math.cos(angle / 2), 0.0, 0.0, math.sin(angle / 2)])
    w.add_mesh(mesh, position=(px, py, 0), quat=q, static=True, material=M[mat], **_NO_COLLIDE)


def _rock(w, mesh, px, py, pz=0.0, mat="rock"):
    w.add_mesh(mesh, position=(px, py, pz), static=True, material=M[mat], **_NO_COLLIDE)


def _tower(
    w,
    base_m,
    mid_m,
    roof_m,
    flag_m,
    px,
    py,
    section_h=6.06,
    n_mid=3,
    mat_base="stone_d",
    mat_mid="stone",
    mat_roof="marble_d",
):
    """Stack tower: 1 base + n_mid mid sections + roof + flag.

    section_h should match the ACTUAL rendered height of one section
    (OBJ Y_max * scale = 1.01 * 6.0 = 6.06 m) so sections are seamless.
    """
    z = 0.0
    mats = [mat_base] + [mat_mid] * n_mid
    meshes = [base_m] + [mid_m] * n_mid
    for mesh, mat in zip(meshes, mats):
        w.add_mesh(mesh, position=(px, py, z), static=True, material=M[mat], **_NO_COLLIDE)
        z += section_h
    # Roof (OBJ height normalised to same as section_h)
    w.add_mesh(roof_m, position=(px, py, z), static=True, material=M[mat_roof], **_NO_COLLIDE)
    z += section_h  # roof same height as one section
    if flag_m is not None:
        w.add_mesh(flag_m, position=(px, py, z), static=True, material=M["e_r"], **_NO_COLLIDE)


def _castle_wall_row(
    w, wall_m, px, py, count: int, axis: str = "x", mat="stone_d", step: float = 4.5
):
    """Place a row of wall sections along axis 'x' or 'y'."""
    for i in range(count):
        if axis == "x":
            wx, wy = px + i * step, py
        else:
            wx, wy = px, py + i * step
        w.add_mesh(wall_m, position=(wx, wy, 0), static=True, material=M[mat], **_NO_COLLIDE)


# ── Zone 1: Colonnade ─────────────────────────────────────────────────────────


def _colonnade(world, col_lg, bench_m, lamp_m, trunk_m, crown_m):
    _b(world, 24, 36, 0.35, 0, -48, pz=0.17, mat="floor")

    for i in range(10):
        y = -67 + i * 3.8
        _col(world, col_lg, -9, y, mat="marble")
        _col(world, col_lg, 9, y, mat="marble")

    # Grand arch
    _b(world, 4, 1.2, 15, -10.5, -31, mat="marble")
    _b(world, 4, 1.2, 15, 10.5, -31, mat="marble")
    _b(world, 23, 1.2, 2.5, 0, -31, pz=15.75, mat="gold")

    # Emissive floor runners
    _b(world, 14, 0.18, 0.04, 0, -55, pz=0.38, mat="e_b")
    _b(world, 14, 0.18, 0.04, 0, -43, pz=0.38, mat="e_a")

    # Benches between columns (every other pair)
    for i in range(0, 10, 2):
        y = -67 + i * 3.8 + 1.9  # mid-point between column pairs
        _bench(world, bench_m, -13.5, y, mat="wood_lt")
        _bench(world, bench_m, 13.5, y, mat="wood_lt")

    # Lamp posts at colonnade mid-points (with warm glow)
    for y_t in (-57.0, -44.0):
        _lamp(world, lamp_m, 0.0, y_t, lamp_h=6.5)

    # Trees flanking colonnade entrance — placed in FRONT of player start (y > -68)
    _tree(world, crown_m, trunk_m, -7.0, -64, crown_mat="foliage")
    _tree(world, crown_m, trunk_m, 7.0, -64, crown_mat="foliage2")

    # Welcome glow at the very entrance — player sees this immediately on start
    _s(world, 0.35, -9, -67, 3.5, mat="e_b")  # blue on first left column
    _s(world, 0.35, 9, -67, 3.5, mat="e_a")  # amber on first right column


# ── Zone 2: Grand Plaza ───────────────────────────────────────────────────────


def _grand_plaza(world, col_sm, trunk_m, crown_m, lamp_m, bench_lg, plant_m, obe_mesh):
    _b(world, 66, 66, 0.44, 0, 0, pz=0.22, mat="floor")
    _b(world, 68, 68, 0.24, 0, 0, pz=0.12, mat="floor_d")

    # Obelisk
    world.add_mesh(obe_mesh, position=(0, 0, 0), static=True, material=M["marble"])
    _s(world, 0.75, 0, 0, 20.5, mat="e_w")  # crown light

    # Fountain ring: alternating blue/amber emissive orbs
    for i in range(5):
        a = 2 * math.pi * i / 5
        fx, fy = 10 * math.cos(a), 10 * math.sin(a)
        _b(world, 1.0, 1.0, 1.4, fx, fy, mat="stone_d")
        _s(world, 0.65, fx, fy, 2.35, mat="e_b" if i % 2 == 0 else "e_a")

    # 2 floating orbs above fountain centre
    _s(world, 0.28, 3, 3, 5.5, mat="e_c")
    _s(world, 0.28, -3, -3, 5.5, mat="e_l")

    # 4 cardinal shrines
    for angle in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
        sx = 26 * math.cos(angle)
        sy = 26 * math.sin(angle)
        px = math.cos(angle + math.pi / 2)
        py = math.sin(angle + math.pi / 2)
        _col(world, col_sm, sx + 2.0 * px, sy + 2.0 * py, mat="marble")
        _col(world, col_sm, sx - 2.0 * px, sy - 2.0 * py, mat="marble")
        _b(world, 5.5, 0.7, 0.5, sx, sy, pz=9.3, mat="gold")
        # Emissive sphere under lintel
        _s(world, 0.22, sx, sy, 8.5, mat="e_a")

    # 6 trees at outer ring (mix of colours)
    tree_mats = ["foliage", "foliage2", "foliage_a", "foliage", "foliage2", "foliage"]
    for i in range(6):
        a = 2 * math.pi * i / 6 + math.pi / 6
        tx, ty = 30 * math.cos(a), 30 * math.sin(a)
        # For these outer plaza trees we only have one crown mesh loaded;
        # alternate between foliage colours
        _tree(world, crown_m, trunk_m, tx, ty, crown_mat=tree_mats[i])

    # Long benches near fountain (facing inward)
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        bx = 16 * math.cos(a)
        by = 16 * math.sin(a)
        ang = a + math.pi  # face toward centre
        _bench(world, bench_lg, bx, by, angle=ang, mat="wood_lt")

    # Potted plants flanking shrine entrances
    for angle in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
        sx = 23 * math.cos(angle)
        sy = 23 * math.sin(angle)
        _rock(world, plant_m, sx, sy, mat="clay")

    # 4 lamp posts at mid-ring
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        lx = 19 * math.cos(a)
        ly = 19 * math.sin(a)
        _lamp(world, lamp_m, lx, ly, emissive="e_lamp", lamp_h=6.5)


# ── Zone 3: Materials Hall ────────────────────────────────────────────────────


def _materials_hall(world) -> list[tuple[str, tuple]]:
    cx, cy = -60, 0
    _b(world, 34, 34, 0.44, cx, cy, pz=0.22, mat="stone_d")
    _b(world, 34, 1.5, 10.0, cx, cy + 17, mat="stone_d")
    _b(world, 34, 1.5, 10.0, cx, cy - 17, mat="stone_d")
    _b(world, 1.5, 12, 10.0, cx + 17, cy + 11, mat="stone_d")
    _b(world, 1.5, 12, 10.0, cx + 17, cy - 11, mat="stone_d")
    _b(world, 1.5, 34, 10.0, cx - 17, cy, mat="stone_d")
    _b(world, 34, 34, 0.8, cx, cy, pz=10.4, mat="marble_d")

    labels: list[tuple[str, tuple]] = []
    for i, (label, mat) in enumerate(PBR_DEMO):
        a = -math.pi / 2 + i * 2 * math.pi / 8
        px = cx + 9 * math.cos(a)
        py = cy + 9 * math.sin(a)
        _b(world, 1.6, 1.6, 1.5, px, py, mat="stone_d")
        world.add_sphere(
            radius=0.72, position=(px, py, 2.66), static=True, material=mat, name=f"mat_{i}"
        )
        labels.append((label, (px, py)))

    # Hanging emissive orbs at ceiling centre (adds drama)
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        ox = cx + 3.5 * math.cos(a)
        oy = cy + 3.5 * math.sin(a)
        _s(world, 0.25, ox, oy, 9.2, mat="e_w")

    return labels


# ── Zone 4: Physics Stage ─────────────────────────────────────────────────────


def _physics_stage(world, rock_lg, campfire_m, barrel_m, crate_m) -> tuple[list, tuple]:
    cx, cy = 60, 0
    _b(world, 44, 44, 0.44, cx, cy, pz=0.22, mat="stone")

    for k, (oy, pz_) in enumerate([(-18, 1.0), (-13, 1.9), (-8, 2.8)]):
        _b(
            world,
            40 - k * 4,
            4.5,
            1.0,
            cx,
            cy + oy,
            pz=pz_,
            mat="marble" if k % 2 == 0 else "marble_d",
        )

    _b(world, 20, 20, 0.28, cx, cy + 7, pz=0.42, mat="stone_d")

    # Flanking torches
    for dx in (-11, 11):
        _b(world, 0.5, 0.5, 5.0, cx + dx, cy + 7, mat="iron")
        _s(world, 0.60, cx + dx, cy + 7, 5.6, mat="e_a")

    _b(world, 28, 1.8, 16, cx, cy + 22, mat="stone_d")

    # Campfire on stage
    world.add_mesh(campfire_m, position=(cx, cy + 7, 0.42), static=True, material=M["rock_d"])
    _s(world, 0.25, cx, cy + 7, 0.9, mat="e_fire")
    _s(world, 0.18, cx, cy + 7, 1.3, mat="e_a")

    # Barrels and crates — props that fill the stage with life
    for bx, by, bz, use_barrel in [
        (cx - 5, cy - 3, 0.44, True),
        (cx - 7, cy - 3, 0.44, False),
        (cx + 5, cy - 3, 0.44, False),
        (cx + 7, cy - 3, 0.44, True),
        (cx - 5, cy - 3, 1.44, True),  # stacked barrel
        (cx + 5, cy - 3, 1.44, False),  # stacked crate
    ]:
        mesh = barrel_m if use_barrel else crate_m
        mat = "bronze" if use_barrel else "wood_lt"
        world.add_mesh(mesh, position=(bx, by, bz), static=True, material=M[mat], **_NO_COLLIDE)

    # Flanking rocks
    for off_x, off_y in [(-8, -5), (8, -5), (-6, 15), (6, 15)]:
        _rock(world, rock_lg, cx + off_x, cy + off_y, pz=0.0, mat="rock")

    # Tower (static by default)
    tx, ty = cx, cy + 11
    tower_positions = []
    for k in range(8):
        pz_ = 0.5 + k * 0.88
        mat_k = "marble_d" if k % 2 else "marble"
        _b(world, 1.3, 1.3, 0.88, tx, ty, pz=pz_, mat=mat_k, name=f"tower_{k}")
        tower_positions.append((tx, ty, pz_, mat_k))

    return tower_positions, (cx + 13, cy + 11, 4.0)


# ── Zone 5: Emissive Sanctum ──────────────────────────────────────────────────


def _emissive_sanctum(world):
    cx, cy = 0, 70
    _b(world, 46, 46, 0.44, cx, cy, pz=0.22, mat="stone_d")
    _b(world, 1, 46, 16, cx - 23, cy, mat="stone_d")
    _b(world, 1, 46, 16, cx + 23, cy, mat="stone_d")
    _b(world, 16, 1, 16, cx - 15, cy - 23, mat="stone_d")
    _b(world, 16, 1, 16, cx + 15, cy - 23, mat="stone_d")
    _b(world, 46, 1, 16, cx, cy + 23, mat="stone_d")
    _b(world, 46, 46, 0.9, cx, cy, pz=16.5, mat="stone_d")

    sizes = [0.90, 0.72, 0.82, 0.88, 1.15, 0.78, 0.92, 0.82, 0.70]
    for row in range(3):
        for col in range(3):
            idx = row * 3 + col
            px = cx - 10 + col * 10
            py = cy - 10 + row * 10
            r = sizes[idx]
            _b(world, 1.0, 1.0, 4.0, px, py, mat="iron")
            _s(world, r, px, py, 4.5 + r, mat=EMISSIVE_9[idx])

    # Two wall accents
    _s(world, 0.20, cx - 20, cy, 12.0, mat=EMISSIVE_9[0])
    _s(world, 0.20, cx + 20, cy, 12.0, mat=EMISSIVE_9[4])


# ── Zone 6: Cascade Court ─────────────────────────────────────────────────────


def _cascade_court(world, col_med) -> tuple:
    cx, cy = -60, 70
    _b(world, 28, 28, 0.44, cx, cy, pz=0.22, mat="mirror")
    for dx, dy, sx, sy in [(-14.5, 0, 1, 28), (14.5, 0, 1, 28), (0, 14.5, 28, 1)]:
        _b(world, sx, sy, 0.8, cx + dx, cy + dy, mat="steel")

    _b(world, 5, 30, 1.0, cx, cy - 18, pz=20.5, mat="marble_d")
    _b(world, 5, 1.5, 20, cx, cy - 30, mat="marble")
    _b(world, 5, 1.5, 20, cx, cy - 5, mat="marble")
    _b(world, 0.5, 30, 1.2, cx - 3, cy - 18, pz=21.6, mat="gold")
    _b(world, 0.5, 30, 1.2, cx + 3, cy - 18, pz=21.6, mat="gold")
    _b(world, 1.5, 1.5, 0.7, cx, cy - 3, pz=20.2, mat="copper")

    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        _col(world, col_med, cx + 17 * math.cos(a), cy + 17 * math.sin(a), mat="marble")

    _b(world, 1.5, 1.5, 25, cx - 4.5, cy - 3, mat="marble")
    _b(world, 1.5, 1.5, 25, cx + 4.5, cy - 3, mat="marble")
    _b(world, 11, 1.5, 2, cx, cy - 3, pz=25.5, mat="gold")

    # Two emissive reflections in pool
    _s(world, 0.22, cx + 8, cy + 8, 1.8, mat="e_b")
    _s(world, 0.22, cx - 8, cy - 8, 1.8, mat="e_c")

    return (cx, cy - 3, 21.0)


# ── Trees + rocks scattered across paths ─────────────────────────────────────


def _scatter(world, trunk_m, crown_m, rock_lg, rock_sm):
    # Entrance avenue (4 trees = 4 crown mesh + 4 box trunks)
    for x in (-7.0, 7.0):
        _tree(world, crown_m, trunk_m, x, -80.0, crown_mat="foliage")
        _tree(world, crown_m, trunk_m, x, -88.0, crown_mat="foliage2")

    # Corridor trees (5 crown mesh + 5 box trunks)
    for y in (-4.0, 22.0, 42.0):
        _tree(world, crown_m, trunk_m, -34.0, y, crown_mat="foliage" if y < 30 else "foliage_a")
    for y in (-4.0, 22.0):
        _tree(world, crown_m, trunk_m, 34.0, y, crown_mat="foliage2")

    # Sanctum approach (4 crown mesh + 4 box trunks)
    for x in (-8.0, 8.0):
        _tree(world, crown_m, trunk_m, x, 50.0, crown_mat="foliage")
        _tree(world, crown_m, trunk_m, x, 60.0, crown_mat="foliage")

    # Rock clusters — 4 large (box-like AABB, cheap enough)
    for px, py, mat in [
        (15, -80, "rock"),
        (-38, 12, "rock_d"),
        (38, 10, "rock"),
        (-8, 52, "rock_d"),
    ]:
        _rock(world, rock_lg, px, py, pz=0.0, mat=mat)
    for px, py in [(-20, -82), (42, -2)]:
        _rock(world, rock_sm, px, py, pz=0.0, mat="rock")

    # Emissive zone-entry markers (spheres = almost free)
    for px, py, ec in [
        (0, -30, "e_b"),
        (-42, -2, "e_a"),
        (42, -2, "e_g"),
        (0, 46, "e_v"),
        (-42, 62, "e_c"),
    ]:
        _s(world, 0.20, px, py, 0.6, mat=ec)


# ── Paths + boundary ──────────────────────────────────────────────────────────


def _paths_boundary(world):
    _b(world, 14, 28, 0.28, 0, -29, pz=0.14, mat="floor")
    _b(world, 28, 14, 0.28, -44, 0, pz=0.14, mat="floor")
    _b(world, 28, 14, 0.28, 44, 0, pz=0.14, mat="floor")
    _b(world, 14, 30, 0.28, 0, 44, pz=0.14, mat="floor")
    _b(world, 14, 52, 0.28, -60, 38, pz=0.14, mat="floor")
    _b(world, 52, 14, 0.28, -33, 70, pz=0.14, mat="floor")
    for px, py, sx, sy in [
        (0, -104, 214, 2),
        (0, 104, 214, 2),
        (-104, 0, 2, 214),
        (104, 0, 2, 214),
    ]:
        _b(world, sx, sy, 2.8, px, py, mat="stone_d")


# ── Assets dataclass + entry point ───────────────────────────────────────────


@dataclass
class ShowcaseAssets:
    tower_positions: list
    tower_spawn: tuple
    cascade_spout: tuple
    material_labels: list[tuple[str, tuple]]


def _castle_perimeter(world, tw_base, tw_mid, tw_roof, flag_m, wall_m):
    """Castle towers visible from key viewpoints + perimeter wall segments."""
    # Each section is OBJ_Y_max * scale = 1.01 * 6.0 = 6.06 m tall
    tsz = 6.06

    # ── Colonnade gate towers — visible from player start (y=-68, looking +Y) ──
    # Flanking the grand arch at y=-31: straight ahead, 37 m away
    _tower(
        world, tw_base, tw_mid, tw_roof, flag_m, -18, -31, section_h=tsz, n_mid=3, mat_roof="gold"
    )
    _tower(
        world, tw_base, tw_mid, tw_roof, flag_m, 18, -31, section_h=tsz, n_mid=3, mat_roof="gold"
    )

    # ── Plaza corner towers — visible after entering the plaza ──────────────────
    for tx, ty in [(-36, -36), (36, -36), (-36, 36), (36, 36)]:
        _tower(world, tw_base, tw_mid, tw_roof, flag_m, tx, ty, section_h=tsz, n_mid=2)

    # ── Far perimeter — landmark silhouettes on the horizon ────────────────────
    for tx, ty in [(0, -92), (92, 0), (0, 92), (-92, 0)]:
        _tower(world, tw_base, tw_mid, tw_roof, flag_m, tx, ty, section_h=tsz, n_mid=1)

    # ── Wall rows between nearby towers ────────────────────────────────────────
    step = tsz * 0.52
    _castle_wall_row(world, wall_m, -82, -92, count=6, axis="x", mat="stone_d", step=step)
    _castle_wall_row(world, wall_m, -82, 92, count=6, axis="x", mat="stone_d", step=step)
    _castle_wall_row(world, wall_m, -92, -80, count=5, axis="y", mat="stone_d", step=step)
    _castle_wall_row(world, wall_m, 92, -80, count=5, axis="y", mat="stone_d", step=step)


def build_showcase(world: f3d.World) -> ShowcaseAssets:
    print("  Pre-generating Kenney CC0 assets …")
    prebuild_all()

    print("  Loading mesh data …")
    col_lg = load_column(height=12.0, radius=0.44)
    col_sm = load_column(height=8.0, radius=0.28)
    col_med = load_column(height=9.5, radius=0.33)
    trunk = load_tree_trunk(height=2.8, radius=0.28)
    crown = load_tree_crown("detailed", height=8.0, width=3.5)
    bench_m = load_bench()
    bench_lg = load_bench_long()
    lamp_m = load_lamp_post(height=6.5, base_radius=0.18)
    plant_m = load_potted_plant(height=1.2)
    rock_lg = load_rock_large(size=2.0)
    rock_sm = load_rock_small(size=1.2)
    campfire = load_campfire(size=1.5)
    barrel_m = load_barrel(size=1.0)
    crate_m = load_crate(size=1.0)
    tw_base = load_tower_section(size=6.0)
    tw_mid = load_tower_mid(size=6.0)
    tw_roof = load_tower_roof(size=6.0)
    wall_m = load_wall_section(size=6.0)
    flag_m = load_flag(height=5.0)
    obe = load_obelisk()

    world.add_box(size=(220, 220, 0.5), position=(0, 0, -0.25), static=True, material=M["ground"])

    _colonnade(world, col_lg, bench_m, lamp_m, trunk, crown)
    _grand_plaza(world, col_sm, trunk, crown, lamp_m, bench_lg, plant_m, obe)
    mat_labels = _materials_hall(world)
    tower, tspawn = _physics_stage(world, rock_lg, campfire, barrel_m, crate_m)
    _emissive_sanctum(world)
    spout = _cascade_court(world, col_med)
    _scatter(world, trunk, crown, rock_lg, rock_sm)
    _castle_perimeter(world, tw_base, tw_mid, tw_roof, flag_m, wall_m)
    _paths_boundary(world)

    print(f"  World built: {len(world.bodies)} bodies")

    return ShowcaseAssets(
        tower_positions=tower,
        tower_spawn=tspawn,
        cascade_spout=spout,
        material_labels=mat_labels,
    )
