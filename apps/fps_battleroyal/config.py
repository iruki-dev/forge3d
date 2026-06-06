"""Game-wide constants for FPS Battle Royale."""

# ── Map ───────────────────────────────────────────────────────────────────────
MAP_HALF = 105.0        # playable area: -105 to +105 on both axes (meters)

# ── Player ────────────────────────────────────────────────────────────────────
PLAYER_RADIUS     = 0.34
PLAYER_HEIGHT     = 1.80
EYE_HEIGHT        = 1.65    # from character base (feet)
PLAYER_MAX_HP     = 100.0
PLAYER_MAX_ARMOR  = 100.0
MOVE_SPEED        = 6.0
SPRINT_MULT       = 1.55
JUMP_IMPULSE      = 7.0
GRAVITY           = (0, 0, -14.0)

# ── Weapons ───────────────────────────────────────────────────────────────────
WEAPON_DATA = {
    "pistol": {
        "display":    "Pistol",
        "damage":     28,
        "fire_rate":  4.0,    # shots/second
        "mag_size":   12,
        "reserve":    48,
        "reload_s":   1.4,
        "spread":     0.04,   # half-angle tan
        "range":      50.0,
        "pellets":    1,
        "auto":       False,
    },
    "smg": {
        "display":    "SMG",
        "damage":     18,
        "fire_rate":  11.0,
        "mag_size":   30,
        "reserve":    120,
        "reload_s":   2.0,
        "spread":     0.07,
        "range":      40.0,
        "pellets":    1,
        "auto":       True,
    },
    "rifle": {
        "display":    "Assault Rifle",
        "damage":     38,
        "fire_rate":  4.5,
        "mag_size":   25,
        "reserve":    100,
        "reload_s":   2.4,
        "spread":     0.018,
        "range":      130.0,
        "pellets":    1,
        "auto":       True,
    },
    "sniper": {
        "display":    "Sniper Rifle",
        "damage":     95,
        "fire_rate":  0.75,
        "mag_size":   5,
        "reserve":    20,
        "reload_s":   3.2,
        "spread":     0.003,
        "range":      400.0,
        "pellets":    1,
        "auto":       False,
    },
    "shotgun": {
        "display":    "Shotgun",
        "damage":     16,
        "fire_rate":  1.2,
        "mag_size":   8,
        "reserve":    32,
        "reload_s":   3.0,
        "spread":     0.11,
        "range":      28.0,
        "pellets":    8,
        "auto":       False,
    },
}

# ── Battle Royale Zone ────────────────────────────────────────────────────────
ZONE_CENTER      = (0.0, 0.0)
ZONE_N_PILLARS   = 24

# Phase: (start_time, initial_radius, target_radius, shrink_duration, dmg_per_sec)
ZONE_PHASES = [
    (0.0,    MAP_HALF,  MAP_HALF,  0.0,  0.0),   # phase 0: safe, full map
    (55.0,   MAP_HALF,  62.0,     30.0,  5.0),   # phase 1: shrink
    (120.0,  62.0,      38.0,     25.0, 10.0),   # phase 2
    (190.0,  38.0,      20.0,     20.0, 20.0),   # phase 3
    (255.0,  20.0,       8.0,     15.0, 40.0),   # phase 4: final
    (310.0,   8.0,       2.0,     30.0, 80.0),   # phase 5: kill
]

# ── Bots ──────────────────────────────────────────────────────────────────────
BOT_COUNT         = 19      # + 1 player = 20 total
BOT_MAX_HP        = 100.0
BOT_SIGHT_RANGE   = 65.0
BOT_SHOOT_RANGE   = 45.0
BOT_MOVE_SPEED    = 3.5
BOT_SHOOT_INTERVAL = 0.55   # seconds between bot shots
BOT_ACCURACY_BASE  = 0.92   # fraction of shots that hit given LoS
BOT_REACTION_DELAY = 0.30   # seconds before bot starts shooting after seeing player
BOT_PATROL_RADIUS  = 40.0   # how far bots wander when patrolling

# ── Visual palette ────────────────────────────────────────────────────────────
# All RGB triples in [0, 1]
C_GROUND          = (0.20, 0.23, 0.18)   # dark olive
C_DIRT            = (0.28, 0.25, 0.20)   # dry dirt
C_CONCRETE        = (0.50, 0.48, 0.45)   # weathered concrete
C_CONCRETE_DARK   = (0.32, 0.30, 0.28)   # darker walls
C_METAL_STEEL     = (0.38, 0.40, 0.43)   # brushed steel
C_METAL_RUST      = (0.50, 0.24, 0.12)   # rusted container
C_METAL_ORANGE    = (0.60, 0.32, 0.10)   # orange safety
C_ASPHALT         = (0.22, 0.22, 0.24)   # road/floor
C_GLASS           = (0.08, 0.11, 0.18)   # dark glass window
C_WOOD_DARK       = (0.28, 0.22, 0.15)   # dark wood
C_ENEMY           = (0.85, 0.18, 0.10)   # enemy body
C_PICKUP          = (0.22, 0.88, 1.00)   # weapon pickup
C_ZONE_PILLAR     = (0.10, 0.38, 1.00)   # zone boundary
C_SKY             = (0.38, 0.50, 0.68)   # cooler military sky

# HUD colors
HUD_WHITE   = (1.00, 1.00, 1.00)
HUD_GREEN   = (0.25, 0.92, 0.40)
HUD_YELLOW  = (1.00, 0.85, 0.10)
HUD_RED     = (0.95, 0.22, 0.12)
HUD_BLUE    = (0.30, 0.65, 1.00)
HUD_GRAY    = (0.55, 0.55, 0.55)
HUD_ORANGE  = (1.00, 0.60, 0.10)
