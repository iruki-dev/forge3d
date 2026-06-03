"""Collision event system for forge3d.

Provides per-frame collision callbacks (begin / stay / end) and
pair-specific collision handlers, similar to Unity's OnCollision* API
and Pymunk's collision handler system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

import numpy as np

if TYPE_CHECKING:
    pass

# Type alias for callback functions
CollisionCallback = Callable[["CollisionEvent"], None]


@dataclass
class CollisionEvent:
    """Data describing a single collision contact.

    Attributes:
        body_a: First body involved in the collision.
        body_b: Second body involved in the collision.
        contact_point: Approximate world-frame contact point (3,).
        normal: Contact normal pointing from body_b toward body_a (3,).
        impulse: Estimated contact impulse magnitude (N·s).
        relative_speed: Relative normal speed at contact (m/s, unsigned).
    """

    body_a: Any  # forge3d.facade.Body
    body_b: Any  # forge3d.facade.Body
    contact_point: np.ndarray
    normal: np.ndarray
    impulse: float
    relative_speed: float


@dataclass
class CollisionHandler:
    """Callbacks for a specific pair of bodies.

    Attributes:
        on_begin: Called once when contact first appears.
        on_stay:  Called every step while contact persists.
        on_end:   Called once when contact disappears.
    """

    on_begin: CollisionCallback | None = None
    on_stay: CollisionCallback | None = None
    on_end: CollisionCallback | None = None


@dataclass
class TriggerZone:
    """Pure-data trigger zone — no physics body, no collision geometry.

    Detects bodies entering / exiting a box region each step.
    The zone does NOT generate physics contacts.

    Attributes:
        position: World-space centre (3,).
        half_extents: Box half-extents (3,).
    """

    position: np.ndarray
    half_extents: np.ndarray
    _prev_inside: set[int] = field(default_factory=set)
    _on_enter: list[Callable[[Any], None]] = field(default_factory=list)
    _on_exit: list[Callable[[Any], None]] = field(default_factory=list)

    def on_enter(self, fn: Callable[[Any], None]) -> Callable[[Any], None]:
        """Register a callback (or use as decorator) for when a body enters this zone."""
        self._on_enter.append(fn)
        return fn

    def on_exit(self, fn: Callable[[Any], None]) -> Callable[[Any], None]:
        """Register a callback for when a body exits this zone."""
        self._on_exit.append(fn)
        return fn


# Backward-compatible alias
_TriggerZone = TriggerZone


class EventDispatcher:
    """Manages collision event state and dispatches callbacks.

    Attached to ``PhysicsWorld`` and updated every ``step()``.
    """

    def __init__(self) -> None:
        # Global listeners
        self._on_begin: list[CollisionCallback] = []
        self._on_stay: list[CollisionCallback] = []
        self._on_end: list[CollisionCallback] = []

        # Per-pair handlers — key = frozenset({id_a, id_b})
        self._pair_handlers: dict[frozenset[int], CollisionHandler] = {}

        # Contact state tracking — set of frozenset({id_a, id_b})
        self._prev_contacts: set[frozenset[int]] = set()

        # Body-id → Body facade handle (set by World)
        self._bodies: dict[int, Any] = {}

        # Trigger zones
        self._triggers: list[_TriggerZone] = []

    # ── Listener registration ─────────────────────────────────────────────────

    def add_begin_listener(self, fn: CollisionCallback) -> None:
        self._on_begin.append(fn)

    def add_stay_listener(self, fn: CollisionCallback) -> None:
        self._on_stay.append(fn)

    def add_end_listener(self, fn: CollisionCallback) -> None:
        self._on_end.append(fn)

    def add_pair_handler(self, id_a: int, id_b: int) -> CollisionHandler:
        key = frozenset({id_a, id_b})
        if key not in self._pair_handlers:
            self._pair_handlers[key] = CollisionHandler()
        return self._pair_handlers[key]

    def add_trigger_zone(
        self,
        position: np.ndarray,
        half_extents: np.ndarray,
    ) -> TriggerZone:
        """Create and register a trigger zone (pure-data, no physics body)."""
        zone = TriggerZone(
            position=np.asarray(position, dtype=float),
            half_extents=np.asarray(half_extents, dtype=float),
        )
        self._triggers.append(zone)
        return zone

    def ignore_pair(self, id_a: int, id_b: int) -> None:
        """Ignore all events and collisions between two bodies (handled at broad-phase)."""
        key = frozenset({id_a, id_b})
        self._pair_handlers[key] = CollisionHandler()  # empty handler (no callbacks)

    # ── Per-step dispatch ─────────────────────────────────────────────────────

    def dispatch(self, contacts: list[Any]) -> None:
        """Compare current contacts with previous; fire begin/stay/end callbacks.

        Args:
            contacts: List of contact data objects from the physics step.
                Each contact has ``.body_id_a``, ``.body_id_b``,
                ``.contact_point``, ``.normal``, ``.impulse``.
        """
        curr_contacts: set[frozenset[int]] = set()
        contact_map: dict[frozenset[int], Any] = {}

        for c in contacts:
            key = frozenset({c.body_id_a, c.body_id_b})
            curr_contacts.add(key)
            contact_map[key] = c

        began = curr_contacts - self._prev_contacts
        stayed = curr_contacts & self._prev_contacts
        ended = self._prev_contacts - curr_contacts

        for key in began:
            event = self._make_event(key, contact_map[key])
            if event is None:
                continue
            for fn in self._on_begin:
                fn(event)
            handler = self._pair_handlers.get(key)
            if handler and handler.on_begin:
                handler.on_begin(event)

        for key in stayed:
            event = self._make_event(key, contact_map[key])
            if event is None:
                continue
            for fn in self._on_stay:
                fn(event)
            handler = self._pair_handlers.get(key)
            if handler and handler.on_stay:
                handler.on_stay(event)

        for key in ended:
            # No contact data available for ended contacts; create minimal event
            ids = list(key)
            ba = self._bodies.get(ids[0])
            bb = self._bodies.get(ids[1])
            if ba is None or bb is None:
                continue
            event = CollisionEvent(
                body_a=ba, body_b=bb,
                contact_point=np.zeros(3),
                normal=np.zeros(3),
                impulse=0.0,
                relative_speed=0.0,
            )
            for fn in self._on_end:
                fn(event)
            handler = self._pair_handlers.get(key)
            if handler and handler.on_end:
                handler.on_end(event)

        self._prev_contacts = curr_contacts

        # Trigger zones
        self._dispatch_triggers()

    def _make_event(self, key: frozenset[int], contact: Any) -> CollisionEvent | None:
        ids = list(key)
        ba = self._bodies.get(contact.body_id_a) or self._bodies.get(ids[0])
        bb = self._bodies.get(contact.body_id_b) or self._bodies.get(ids[1])
        if ba is None or bb is None:
            return None
        cp = np.asarray(contact.contact_point, dtype=float)
        n = np.asarray(contact.normal, dtype=float)
        imp = float(getattr(contact, "impulse", 0.0))
        spd = float(getattr(contact, "relative_speed", 0.0))
        return CollisionEvent(body_a=ba, body_b=bb, contact_point=cp,
                               normal=n, impulse=imp, relative_speed=spd)

    def _dispatch_triggers(self) -> None:
        """Check which bodies are inside each trigger zone (AABB check)."""
        for zone in self._triggers:
            curr_inside: set[int] = set()
            for bid, body in self._bodies.items():
                try:
                    bpos = body.position
                    diff = np.abs(bpos - zone.position)
                    if np.all(diff <= zone.half_extents):
                        curr_inside.add(bid)
                except Exception:
                    pass

            entered = curr_inside - zone._prev_inside
            exited = zone._prev_inside - curr_inside

            for bid in entered:
                body = self._bodies.get(bid)
                if body is not None:
                    for fn in zone._on_enter:
                        fn(body)

            for bid in exited:
                body = self._bodies.get(bid)
                if body is not None:
                    for fn in zone._on_exit:
                        fn(body)

            zone._prev_inside = curr_inside

    def register_body(self, body_id: int, body: Any) -> None:
        self._bodies[body_id] = body

    def unregister_body(self, body_id: int) -> None:
        self._bodies.pop(body_id, None)
        # Remove from trigger zone tracking
        for zone in self._triggers:
            zone._prev_inside.discard(body_id)
