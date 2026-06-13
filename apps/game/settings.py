"""FORGE RUNNER — central tuning constants.

Every gameplay number lives here so the feel of the game can be tweaked
without touching logic code.
"""

# ── Window ────────────────────────────────────────────────────────────────
WIDTH = 1280
HEIGHT = 720
TITLE = "FORGE RUNNER"
SHADOW_RESOLUTION = 2048
SKY_COLOR = (0.32, 0.46, 0.62)

# ── Physics ───────────────────────────────────────────────────────────────
GRAVITY = (0.0, 0.0, -22.0)  # snappier-than-earth platformer gravity
PHYSICS_SUBSTEPS = 2
MAX_DT = 1 / 25  # clamp frame spikes so physics stays sane

# ── Player ────────────────────────────────────────────────────────────────
PLAYER_HEIGHT = 1.5
PLAYER_RADIUS = 0.34
PLAYER_MASS = 70.0
RUN_SPEED = 7.2
AIR_SPEED = 6.0
JUMP_IMPULSE = 9.5
DOUBLE_JUMP_IMPULSE = 8.5
COYOTE_TIME = 0.12  # grace period after leaving a ledge
GLIDE_FALL_SPEED = -2.2  # hold SPACE while falling
DASH_SPEED = 17.0
DASH_TIME = 0.18
DASH_COOLDOWN = 1.1
MAX_HP = 100
SENTRY_DAMAGE = 25
LAVA_DAMAGE = 25
FALL_DAMAGE = 10
INVULN_TIME = 1.0
KILL_Z = -8.0  # respawn below this height

# ── Camera ────────────────────────────────────────────────────────────────
CAM_DISTANCE = 9.0
CAM_MIN_DIST = 4.0
CAM_MAX_DIST = 16.0
CAM_ELEVATION = 22.0
CAM_MIN_ELEV = -5.0
CAM_MAX_ELEV = 70.0
CAM_MOUSE_SENS = 0.25
CAM_KEY_DEG_PER_S = 130.0
CAM_TARGET_SMOOTH_HZ = 10.0

# ── Enemies ───────────────────────────────────────────────────────────────
SENTRY_PATROL_SPEED = 2.4
SENTRY_CHASE_SPEED = 4.6
SENTRY_SIGHT_RANGE = 11.0
SENTRY_HIT_RANGE = 1.15
SENTRY_KNOCKBACK = 11.0

# ── VFX ───────────────────────────────────────────────────────────────────
DEBRIS_LIFETIME = 1.1
DEBRIS_MAX = 60

# ── Scoring ───────────────────────────────────────────────────────────────
CORE_SCORE = 100
TIME_BONUS_BASE = 500  # max(0, TIME_BONUS_BASE - seconds*5) at win
