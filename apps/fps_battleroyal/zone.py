"""Battle royale safe zone — timing, shrinking, and damage."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from apps.fps_battleroyal.config import ZONE_CENTER, ZONE_PHASES


@dataclass
class Zone:
    """Tracks the current safe zone state."""

    center: np.ndarray = field(default_factory=lambda: np.array(ZONE_CENTER + (0.0,)))
    current_radius: float = ZONE_PHASES[0][1]
    phase: int = 0
    phase_elapsed: float = 0.0

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        if self.phase >= len(ZONE_PHASES):
            return

        p = ZONE_PHASES[self.phase]
        start_time, r0, r1, shrink_dur, _ = p

        # Advance within phase
        self.phase_elapsed += dt

        # Calculate interpolated radius
        if shrink_dur > 0:
            t = max(0.0, min(1.0, (self.phase_elapsed - start_time) / shrink_dur))
            self.current_radius = r0 + (r1 - r0) * t
        else:
            self.current_radius = r0

        # Advance to next phase when this one expires
        if self.phase + 1 < len(ZONE_PHASES):
            next_p = ZONE_PHASES[self.phase + 1]
            if self.phase_elapsed >= next_p[0]:
                self.phase += 1

    # ── Queries ───────────────────────────────────────────────────────────────

    def is_inside(self, position: np.ndarray) -> bool:
        """True if *position* is within the safe zone."""
        dx = float(position[0]) - ZONE_CENTER[0]
        dy = float(position[1]) - ZONE_CENTER[1]
        return math.sqrt(dx * dx + dy * dy) <= self.current_radius

    def damage_outside(self) -> float:
        """Damage per second for players outside the zone."""
        if self.phase >= len(ZONE_PHASES):
            return ZONE_PHASES[-1][4]
        return ZONE_PHASES[self.phase][4]

    def distance_to_center(self, position: np.ndarray) -> float:
        dx = float(position[0]) - ZONE_CENTER[0]
        dy = float(position[1]) - ZONE_CENTER[1]
        return math.sqrt(dx * dx + dy * dy)

    def time_to_next_shrink(self) -> float | None:
        """Seconds until the next shrink begins. None if no more phases."""
        if self.phase + 1 >= len(ZONE_PHASES):
            return None
        next_start = ZONE_PHASES[self.phase + 1][0]
        return max(0.0, next_start - self.phase_elapsed)

    def shrink_progress(self) -> float:
        """0.0 = not shrinking, 1.0 = fully shrunk to target for this phase."""
        p = ZONE_PHASES[self.phase]
        start_time, r0, r1, shrink_dur, _ = p
        if shrink_dur <= 0 or r0 == r1:
            return 1.0
        t = (self.phase_elapsed - start_time) / shrink_dur
        return float(np.clip(t, 0.0, 1.0))
