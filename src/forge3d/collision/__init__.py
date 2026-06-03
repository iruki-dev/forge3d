"""forge3d.collision — narrow-phase collision detection.

Exported helpers:
    detect_contacts  — main entry point for world.step()
    gjk              — GJK intersection/distance test
    gjk_contact      — GJK + EPA: returns (depth, normal) for intersecting pairs
    ContactPoint     — per-contact data (pos, normal, depth, body indices)
"""

from forge3d.collision.detection import ContactPoint, detect_contacts
from forge3d.collision.gjk import gjk, gjk_contact, gjk_distance, gjk_intersect

__all__ = [
    "ContactPoint",
    "detect_contacts",
    "gjk",
    "gjk_contact",
    "gjk_distance",
    "gjk_intersect",
]
