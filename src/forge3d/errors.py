"""forge3d exception hierarchy and validation utilities."""

from __future__ import annotations

import warnings
from typing import Any


# ── Exception hierarchy ───────────────────────────────────────────────────────


class Forge3dError(Exception):
    """Base exception for all forge3d errors."""


class PhysicsError(Forge3dError):
    """Physics configuration or state error."""


class ValidationError(Forge3dError, ValueError):
    """Invalid argument passed to a forge3d API call.

    The message always follows the pattern:
        ``ClassName.method_name() — description, got value=<value>``
    """


class RenderError(Forge3dError):
    """Renderer configuration or capability error."""


class AssetError(Forge3dError):
    """Asset loading failure (OBJ/texture not found, parse error, etc.)."""


# ── Input validation helpers ───────────────────────────────────────────────────


def require_positive(value: float, name: str, caller: str) -> float:
    """Raise ValidationError if value <= 0."""
    if value <= 0:
        raise ValidationError(
            f"{caller} — {name} must be positive, got {name}={value!r}"
        )
    return value


def require_nonneg(value: float, name: str, caller: str) -> float:
    """Raise ValidationError if value < 0."""
    if value < 0:
        raise ValidationError(
            f"{caller} — {name} must be ≥ 0, got {name}={value!r}"
        )
    return value


def require_range(value: float, lo: float, hi: float, name: str, caller: str) -> float:
    """Raise ValidationError if value not in [lo, hi]."""
    if not (lo <= value <= hi):
        raise ValidationError(
            f"{caller} — {name} must be in [{lo}, {hi}], got {name}={value!r}"
        )
    return value


def require_sequence(value: Any, length: int, name: str, caller: str) -> Any:
    """Raise ValidationError if value is not a sequence of the given length."""
    try:
        seq = tuple(value)
    except TypeError:
        raise ValidationError(
            f"{caller} — {name} must be a {length}-element sequence, "
            f"got {name}={value!r}"
        ) from None
    if len(seq) != length:
        raise ValidationError(
            f"{caller} — {name} must be a {length}-element sequence, "
            f"got {len(seq)} elements"
        )
    return value


def require_all_positive(value: Any, name: str, caller: str) -> None:
    """Raise ValidationError if any component of a size/extents tuple is <= 0."""
    for i, v in enumerate(value):
        if v <= 0:
            raise ValidationError(
                f"{caller} — all {name} components must be positive, "
                f"got {name}[{i}]={v!r}"
            )


# ── Deprecation helper ────────────────────────────────────────────────────────


def deprecated(message: str, stacklevel: int = 2) -> None:
    """Issue a DeprecationWarning with the given message."""
    warnings.warn(message, DeprecationWarning, stacklevel=stacklevel + 1)
