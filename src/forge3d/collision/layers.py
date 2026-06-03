"""Collision layer and mask bit-field constants.

Usage::

    box.collision_layer = forge3d.CollisionLayer.DEFAULT
    box.collision_mask  = forge3d.CollisionLayer.DEFAULT | forge3d.CollisionLayer.PLAYER
"""

from __future__ import annotations


class CollisionLayer:
    """Named bit-field constants for collision layers.

    Collision rule: bodies A and B collide if and only if:
    ``(A.collision_layer & B.collision_mask) != 0``
    and
    ``(B.collision_layer & A.collision_mask) != 0``

    The default is layer 0x0001 with mask 0xFFFF (collide with everything).
    """

    DEFAULT  = 1 << 0   # 0x0001 — default layer for all bodies
    PLAYER   = 1 << 1   # 0x0002
    ENEMY    = 1 << 2   # 0x0004
    BULLET   = 1 << 3   # 0x0008
    TRIGGER  = 1 << 4   # 0x0010
    TERRAIN  = 1 << 5   # 0x0020
    DEBRIS   = 1 << 6   # 0x0040
    SENSOR   = 1 << 7   # 0x0080

    NONE     = 0
    ALL      = 0xFFFF   # collide with all 16 standard layers


def layers_collide(layer_a: int, mask_a: int, layer_b: int, mask_b: int) -> bool:
    """Return True if body a and body b should collide."""
    return bool((layer_a & mask_b) != 0 and (layer_b & mask_a) != 0)
