"""PhysicsProfiler — measure per-step timing breakdown of a World.

Usage::

    with world.profiler:
        world.step(dt)

    p = world.profiler.last
    print(f"total {p.total_ms:.2f} ms  contacts={p.n_contacts}")
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class PhysicsProfile:
    """Timing snapshot for one physics step.

    All times are in milliseconds.
    """

    broad_phase_ms: float = 0.0
    narrow_phase_ms: float = 0.0
    contact_solver_ms: float = 0.0
    integration_ms: float = 0.0
    total_ms: float = 0.0
    n_contacts: int = 0

    def __str__(self) -> str:
        return (
            f"PhysicsProfile("
            f"broad={self.broad_phase_ms:.3f}ms "
            f"narrow={self.narrow_phase_ms:.3f}ms "
            f"solver={self.contact_solver_ms:.3f}ms "
            f"integ={self.integration_ms:.3f}ms "
            f"total={self.total_ms:.3f}ms "
            f"contacts={self.n_contacts})"
        )


class PhysicsProfiler:
    """Context-manager profiler that wraps world.step().

    Attach to a :class:`~forge3d.facade.World` via :attr:`world.profiler`
    (set automatically when first accessed) or create manually::

        world.profiler = PhysicsProfiler(world)

    Use as context manager to measure one step::

        with world.profiler:
            world.step(dt)

        print(world.profiler.last)

    Or measure automatically by replacing ``world.step``::

        # Already handled by world.profiler — just use world.profiler.step(dt)
        world.profiler.step(dt)
    """

    def __init__(self, world: Any) -> None:
        self._world = world
        self.last: PhysicsProfile = PhysicsProfile()
        self._history: list[PhysicsProfile] = []
        self._max_history = 120  # keep ~2 seconds at 60 fps
        self._t_enter: float = 0.0

    # ── Context-manager interface ──────────────────────────────────────────────

    def __enter__(self) -> PhysicsProfiler:
        self._t_enter = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        elapsed_ms = (time.perf_counter() - self._t_enter) * 1000.0
        pw = self._world._physics
        n = len(getattr(pw, "_last_contacts", []))
        self.last = PhysicsProfile(
            total_ms=elapsed_ms,
            n_contacts=n,
        )
        self._history.append(self.last)
        if len(self._history) > self._max_history:
            self._history.pop(0)

    # ── Convenience step ──────────────────────────────────────────────────────

    def step(self, dt: float | None = None) -> None:
        """Call world.step(dt) and record timing."""
        with self:
            self._world.step(dt)

    # ── Statistics ────────────────────────────────────────────────────────────

    def average(self, n: int = 60) -> PhysicsProfile:
        """Return average of the last *n* recorded steps."""
        recent = self._history[-n:] if self._history else []
        if not recent:
            return PhysicsProfile()
        avg_total = sum(p.total_ms for p in recent) / len(recent)
        avg_contacts = sum(p.n_contacts for p in recent) / len(recent)
        return PhysicsProfile(total_ms=avg_total, n_contacts=int(avg_contacts))

    def reset(self) -> None:
        """Clear history."""
        self._history.clear()
        self.last = PhysicsProfile()
