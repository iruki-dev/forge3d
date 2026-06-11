"""Mesh model loaders using Kenney.nl CC0 assets.

All Kenney OBJ files use Y-up convention.  forge3d uses Z-up.
Conversion: (x, y_obj, z_obj) -> (x*sx, -z_obj*sz, y_obj*sy)
This is a proper rotation (det=+1) so normals and winding are preserved.

Packs used (all CC0):
  nature-kit    apps/showcase/assets/kenney/nature/
  castle-kit    apps/showcase/assets/kenney/castle/
  furniture-kit apps/showcase/assets/kenney/furniture/
  holiday-kit   apps/showcase/assets/kenney/holiday/
"""

from __future__ import annotations

import pathlib
from functools import cache

import forge3d as f3d

ASSETS = pathlib.Path(__file__).parent / "assets"
K_NAT = ASSETS / "kenney" / "nature"
K_CASTLE = ASSETS / "kenney" / "castle"
K_FURN = ASSETS / "kenney" / "furniture"
K_HOLIDAY = ASSETS / "kenney" / "holiday"
PROC = ASSETS / "processed"


# ── Y-up -> Z-up OBJ processor ────────────────────────────────────────────────


def _convert(
    src: pathlib.Path, dst: pathlib.Path, sx: float = 1.0, sy: float = 1.0, sz: float = 1.0
) -> None:
    """
    Convert Kenney Y-up OBJ to forge3d Z-up with per-axis scaling.
      sx = scale along world X (OBJ X)
      sy = scale along world Z (OBJ Y = height)
      sz = scale along world Y (OBJ Z = depth)
    """
    out: list[str] = []
    for raw in src.read_text().splitlines(keepends=True):
        p = raw.split()
        # Vertex position — allow "v x y z" or "v x y z r g b" (vertex colour)
        if len(p) >= 4 and p[0] == "v" and p[0] != "vn" and p[0] != "vt":
            x = float(p[1]) * sx
            y = float(p[2]) * sy  # OBJ-Y -> forge3d Z
            z = float(p[3]) * sz  # OBJ-Z -> forge3d -Y
            out.append(f"v {x:.5f} {-z:.5f} {y:.5f}\n")
            continue
        if len(p) == 4 and p[0] == "vn":
            # Normal transform for the same rotation + scale
            # n' = (M^-T) n  where M = diag(sx,-sz,sy)
            nx = float(p[1]) / max(sx, 1e-9)
            ny = float(p[2]) / max(sy, 1e-9)
            nz = float(p[3]) / max(sz, 1e-9)
            # After the axis swap n=(nx,-nz,ny), then divide
            mag = (nx**2 + nz**2 + ny**2) ** 0.5 + 1e-12
            out.append(f"vn {nx / mag:.5f} {-nz / mag:.5f} {ny / mag:.5f}\n")
        else:
            out.append(raw)
    dst.write_text("".join(out))


def _proc(
    src_name: str, pack_dir: pathlib.Path, sx: float = 1.0, sy: float = 1.0, sz: float | None = None
) -> pathlib.Path:
    """Return path to processed OBJ, generating it if needed."""
    if sz is None:
        sz = sx  # square cross-section by default
    PROC.mkdir(exist_ok=True)
    tag = f"{src_name.removesuffix('.obj')}__sx{sx:.3f}_sy{sy:.3f}_sz{sz:.3f}.obj"
    dst = PROC / tag
    if not dst.exists():
        _convert(pack_dir / src_name, dst, sx=sx, sy=sy, sz=sz)
    return dst


def _load(p: pathlib.Path):
    return f3d.io.load_obj(str(p))


# ── Columns (Kenney statue_column) ───────────────────────────────────────────


@cache
def load_column(height: float = 12.0, radius: float = 0.44):
    # Original: 0.30 wide (X), 1.0 tall (Y), 0.30 deep (Z)
    scale_xz = radius / 0.15  # half of 0.30
    scale_y = height / 1.0
    return _load(_proc("statue_column.obj", K_NAT, sx=scale_xz, sy=scale_y, sz=scale_xz))


# ── Trees (Kenney nature) + separate trunks (Kenney castle) ──────────────────

_TREE_CAT = {
    "detailed": ("tree_detailed.obj", 1.33, 0.77),
    "pine_tall": ("tree_pineTallA.obj", 1.53, 0.39),
    "pine_round": ("tree_pineRoundA.obj", 1.16, 0.62),
    "oak": ("tree_oak.obj", 1.53, 0.77),
    "simple": ("tree_simple.obj", 1.23, 0.62),
    "small": ("tree_small.obj", 0.94, 0.48),
}


@cache
def load_tree_crown(kind: str = "detailed", height: float = 7.0, width: float = 3.0):
    fname, orig_h, orig_w = _TREE_CAT.get(kind, _TREE_CAT["detailed"])
    return _load(_proc(fname, K_NAT, sx=width / orig_w, sy=height / orig_h, sz=width / orig_w))


@cache
def load_tree_trunk(height: float = 2.8, radius: float = 0.28):
    # castle/tree-trunk: 0.396 wide (X), 0.375 tall (Y), 0.343 deep (Z)
    sx = radius / 0.198  # half of 0.396
    sy = height / 0.375
    return _load(_proc("tree-trunk.obj", K_CASTLE, sx=sx, sy=sy, sz=sx))


# ── Bench (furniture + holiday) ───────────────────────────────────────────────


@cache
def load_bench(length: float = 2.2):
    # holiday/bench: X=[-0.56..0.56]=1.12 wide, Y=[0..0.73] tall, Z=[-0.32..0.32]=0.64 deep
    # Centred, base at Y=0.  Scale to a full-size park bench.
    sx = length / 1.12  # length along X
    sy = 0.48 / 0.73  # seat height ~0.48 m
    sz = sx  # keep depth proportional
    return _load(_proc("bench.obj", K_HOLIDAY, sx=sx, sy=sy, sz=sz))


@cache
def load_bench_long(length: float = 2.0):
    sx = length / 1.12
    sy = 0.48 / 0.73
    sz = 0.60 / 0.63
    return _load(_proc("bench.obj", K_HOLIDAY, sx=sx, sy=sy, sz=sz))


# ── Lamp post (furniture) ─────────────────────────────────────────────────────


@cache
def load_lamp_post(height: float = 6.5, base_radius: float = 0.18):
    # furniture/lampRoundFloor: 0.152 wide(X), 0.86 tall(Y), 0.176 deep(Z)
    sx = base_radius / 0.076  # half of 0.152
    sy = height / 0.86
    return _load(_proc("lampRoundFloor.obj", K_FURN, sx=sx, sy=sy, sz=sx))


# ── Potted plant ──────────────────────────────────────────────────────────────


@cache
def load_potted_plant(height: float = 1.2):
    # furniture/pottedPlant: 0.212 wide, 0.654 tall, 0.241 deep
    sy = height / 0.654
    sx = sy * 0.9  # slightly slimmer
    return _load(_proc("pottedPlant.obj", K_FURN, sx=sx, sy=sy, sz=sx))


# ── Rocks (castle + nature) ───────────────────────────────────────────────────


@cache
def load_rock_large(size: float = 2.0):
    # castle/rocks-large: 1.2 wide(X), 0.5 tall(Y), 1.35 deep(Z)
    s = size / 0.5
    return _load(_proc("rocks-large.obj", K_CASTLE, sx=s, sy=s, sz=s))


@cache
def load_rock_small(size: float = 1.2):
    s = size / 0.5
    return _load(_proc("rocks-small.obj", K_CASTLE, sx=s, sy=s, sz=s))


# ── Campfire ──────────────────────────────────────────────────────────────────


@cache
def load_campfire(size: float = 1.5):
    # nature/campfire_stones: 0.54 wide, 0.08 tall, 0.52 deep
    s = size / 0.5
    return _load(_proc("campfire_stones.obj", K_NAT, sx=s, sy=s, sz=s))


# ── Obelisk (procedural — no Kenney equivalent) ───────────────────────────────


def _mk_obelisk(w_base=1.2, w_top=0.14, h_shaft=13.0, h_pyramid=2.2) -> pathlib.Path:
    PROC.mkdir(exist_ok=True)
    name = f"obelisk_wb{w_base:.2f}_h{h_shaft:.1f}.obj"
    p = PROC / name
    if p.exists():
        return p
    hw_b, hw_t = w_base / 2, w_top / 2
    lines = ["# obelisk (Z-up procedural)"]
    for hw, z in [(hw_b, 0.0), (hw_t, h_shaft)]:
        lines += [
            f"v  {hw:.4f}  {hw:.4f} {z:.4f}",
            f"v {-hw:.4f}  {hw:.4f} {z:.4f}",
            f"v {-hw:.4f} {-hw:.4f} {z:.4f}",
            f"v  {hw:.4f} {-hw:.4f} {z:.4f}",
        ]
    lines.append(f"v 0 0 {h_shaft + h_pyramid:.4f}")
    for i in range(4):
        a, b, c, d = 1 + i, 1 + (i + 1) % 4, 1 + (i + 1) % 4 + 4, 1 + i + 4
        lines.append(f"f {a} {b} {c} {d}")
    for i in range(4):
        lines.append(f"f {5 + i} {5 + (i + 1) % 4} 9")
    lines.append("f 1 4 3 2")
    p.write_text("\n".join(lines))
    return p


@cache
def load_obelisk(w_base=1.2, w_top=0.14, h_shaft=13.0, h_pyramid=2.2):
    return _load(_mk_obelisk(w_base, w_top, h_shaft, h_pyramid))


K_PLATFORM = ASSETS / "kenney" / "platformer"
K_ROADS = ASSETS / "kenney" / "roads"


# ── Castle towers (stackable section) ────────────────────────────────────────


@cache
def load_tower_section(size: float = 6.0):
    # castle/tower-square-base: 1.0 wide(X), 1.01 tall(Y), 1.0 deep(Z)
    s = size / 1.0
    return _load(_proc("tower-square-base.obj", K_CASTLE, sx=s, sy=s, sz=s))


@cache
def load_tower_mid(size: float = 6.0):
    # Same as base — ensures ALL sections have identical width so tower is solid-looking
    s = size / 1.0
    return _load(_proc("tower-square-base.obj", K_CASTLE, sx=s, sy=s, sz=s))


@cache
def load_tower_roof(size: float = 6.0):
    # Roof OBJ has Y=[0..2.01]. Normalise height so it equals one section (≈size).
    sx = size / 1.0
    sy = size / 2.01
    return _load(_proc("tower-square-roof.obj", K_CASTLE, sx=sx, sy=sy, sz=sx))


# ── Castle wall section ───────────────────────────────────────────────────────


@cache
def load_wall_section(size: float = 4.0):
    # castle/wall: 1.0 wide(X), 1.31 tall(Y), 1.0 deep(Z)
    s = size / 1.0
    return _load(_proc("wall.obj", K_CASTLE, sx=s, sy=s, sz=s))


# ── Castle flag ───────────────────────────────────────────────────────────────


@cache
def load_flag(height: float = 5.0):
    # castle/flag: 0.11 wide, 0.87 tall, 0.43 deep
    sy = height / 0.87
    sx = sy * 0.8
    return _load(_proc("flag.obj", K_CASTLE, sx=sx, sy=sy, sz=sx))


# ── Barrel / Crate (platformer) ───────────────────────────────────────────────


@cache
def load_barrel(size: float = 1.0):
    # platformer/barrel: 0.52 wide, 0.48 tall, 0.52 deep
    s = size / 0.48
    return _load(_proc("barrel.obj", K_PLATFORM, sx=s, sy=s, sz=s))


@cache
def load_crate(size: float = 1.0):
    # platformer/crate: 0.5 cube
    s = size / 0.5
    return _load(_proc("crate.obj", K_PLATFORM, sx=s, sy=s, sz=s))


# ── Street light (roads kit) ──────────────────────────────────────────────────


@cache
def load_street_light(height: float = 6.0):
    # roads/light-square: 0.05 wide, 0.60 tall, 0.24 deep
    sy = height / 0.60
    sx = sy * 0.5
    return _load(_proc("light-square.obj", K_ROADS, sx=sx, sy=sy, sz=sx))


# ── Prebuild all ──────────────────────────────────────────────────────────────


def prebuild_all() -> None:
    _all = [
        load_column,
        load_tree_crown,
        load_tree_trunk,
        load_bench,
        load_bench_long,
        load_lamp_post,
        load_potted_plant,
        load_rock_large,
        load_rock_small,
        load_campfire,
        load_obelisk,
        load_tower_section,
        load_tower_mid,
        load_tower_roof,
        load_wall_section,
        load_flag,
        load_barrel,
        load_crate,
        load_street_light,
    ]
    for fn in _all:
        fn.cache_clear()
    load_column(height=12.0, radius=0.44)
    load_column(height=8.0, radius=0.28)
    load_column(height=9.5, radius=0.33)
    load_tree_crown("detailed", height=8.0, width=3.5)
    load_tree_crown("pine_tall", height=10.0, width=2.5)
    load_tree_crown("oak", height=7.0, width=3.0)
    load_tree_trunk(height=2.8, radius=0.28)
    load_bench()
    load_bench_long()
    load_lamp_post()
    load_potted_plant()
    load_rock_large()
    load_rock_small()
    load_campfire()
    load_obelisk()
    load_tower_section(size=6.0)
    load_tower_mid(size=6.0)
    load_tower_roof(size=6.0)
    load_wall_section(size=4.5)
    load_flag(height=5.0)
    load_barrel(size=1.0)
    load_crate(size=1.0)
    load_street_light(height=6.0)
    print("  Kenney CC0 assets ready.")
