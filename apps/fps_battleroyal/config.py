"""Game constants — tuned for snappy, fun FPS gameplay."""

# ── Map ───────────────────────────────────────────────────────────────────────
MAP_HALF = 105.0

# ── Player ────────────────────────────────────────────────────────────────────
PLAYER_RADIUS = 0.34
PLAYER_HEIGHT = 1.80
EYE_HEIGHT = 1.65
PLAYER_MAX_HP = 100.0
PLAYER_MAX_ARMOR = 100.0
MOVE_SPEED = 9.0  # m/s  (was 6 — increased for snappier feel)
SPRINT_MULT = 1.65
JUMP_IMPULSE = 9.5  # m/s  (was 7 — higher, snappier jump)
GRAVITY = (0, 0, -18.0)  # stronger gravity for snappier arc

# ── Mouse ─────────────────────────────────────────────────────────────────────
MOUSE_SENSITIVITY = 0.0022  # radians per pixel
MOUSE_SMOOTH = 0.0  # 0=off, 0.2=slight smoothing

# ── Weapons ───────────────────────────────────────────────────────────────────
WEAPON_DATA = {
    "pistol": {
        "display": "Pistol",
        "damage": 25,
        "fire_rate": 5.0,
        "mag_size": 15,
        "reserve": 60,
        "reload_s": 1.2,
        "spread": 0.035,
        "range": 60.0,
        "pellets": 1,
        "auto": False,
    },
    "smg": {
        "display": "SMG",
        "damage": 20,
        "fire_rate": 13.0,
        "mag_size": 30,
        "reserve": 120,
        "reload_s": 1.8,
        "spread": 0.055,
        "range": 45.0,
        "pellets": 1,
        "auto": True,
    },
    "rifle": {
        "display": "Assault Rifle",
        "damage": 35,
        "fire_rate": 5.0,
        "mag_size": 25,
        "reserve": 100,
        "reload_s": 2.2,
        "spread": 0.015,
        "range": 140.0,
        "pellets": 1,
        "auto": True,
    },
    "sniper": {
        "display": "Sniper",
        "damage": 90,
        "fire_rate": 0.8,
        "mag_size": 5,
        "reserve": 20,
        "reload_s": 3.0,
        "spread": 0.002,
        "range": 500.0,
        "pellets": 1,
        "auto": False,
    },
    "shotgun": {
        "display": "Shotgun",
        "damage": 15,
        "fire_rate": 1.5,
        "mag_size": 8,
        "reserve": 32,
        "reload_s": 2.5,
        "spread": 0.10,
        "range": 30.0,
        "pellets": 8,
        "auto": False,
    },
}

# ── Zone ──────────────────────────────────────────────────────────────────────
ZONE_CENTER = (0.0, 0.0)
ZONE_N_PILLARS = 24

# (start_time, initial_radius, target_radius, shrink_duration, dmg_per_sec)
ZONE_PHASES = [
    (0.0, MAP_HALF, MAP_HALF, 0.0, 0.0),
    (55.0, MAP_HALF, 62.0, 30.0, 5.0),
    (120.0, 62.0, 38.0, 25.0, 10.0),
    (190.0, 38.0, 20.0, 20.0, 20.0),
    (255.0, 20.0, 8.0, 15.0, 40.0),
    (310.0, 8.0, 2.0, 30.0, 80.0),
]

# ── Bots ──────────────────────────────────────────────────────────────────────
BOT_COUNT = 19
BOT_MAX_HP = 100.0
BOT_SIGHT_RANGE = 60.0
BOT_SHOOT_RANGE = 42.0
BOT_MOVE_SPEED = 4.2  # slightly faster bots
BOT_SHOOT_INTERVAL = 0.85  # seconds between bot shots
BOT_REACTION_DELAY = 0.55
BOT_PATROL_RADIUS = 35.0
BOT_HIT_RADIUS = 0.55  # sphere radius for player→bot raycast hit
GRACE_PERIOD_SEC = 12.0  # bots don't shoot player for first N seconds

# ── Colors ────────────────────────────────────────────────────────────────────
C_GROUND = (0.20, 0.23, 0.18)
C_DIRT = (0.28, 0.25, 0.20)
C_CONCRETE = (0.50, 0.48, 0.45)
C_CONCRETE_DARK = (0.32, 0.30, 0.28)
C_METAL_STEEL = (0.38, 0.40, 0.43)
C_METAL_RUST = (0.50, 0.24, 0.12)
C_METAL_ORANGE = (0.60, 0.32, 0.10)
C_ASPHALT = (0.22, 0.22, 0.24)
C_GLASS = (0.08, 0.11, 0.18)
C_WOOD_DARK = (0.28, 0.22, 0.15)
C_ENEMY = (0.85, 0.18, 0.10)
C_PICKUP = (0.22, 0.88, 1.00)
C_ZONE_PILLAR = (0.10, 0.38, 1.00)
C_SKY = (0.35, 0.48, 0.65)

# HUD
HUD_WHITE = (1.00, 1.00, 1.00)
HUD_GREEN = (0.25, 0.92, 0.40)
HUD_YELLOW = (1.00, 0.85, 0.10)
HUD_RED = (0.95, 0.22, 0.12)
HUD_BLUE = (0.30, 0.65, 1.00)
HUD_GRAY = (0.55, 0.55, 0.55)
HUD_ORANGE = (1.00, 0.60, 0.10)
