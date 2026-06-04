"""VFX 프리셋 — ParticleEmitter.preset() 래퍼."""
from __future__ import annotations

from forge3d.particle.emitter import ParticleEmitter


def sparks(**kwargs: object) -> ParticleEmitter:
    """금속 불꽃 이미터 — 빠르고 단명."""
    return ParticleEmitter.preset("sparks", **kwargs)


def smoke(**kwargs: object) -> ParticleEmitter:
    """연기 이미터 — 느리고 장수명."""
    return ParticleEmitter.preset("smoke", **kwargs)


def debris(**kwargs: object) -> ParticleEmitter:
    """파편 이미터 — 넓게 퍼짐."""
    return ParticleEmitter.preset("debris", **kwargs)


def rain(**kwargs: object) -> ParticleEmitter:
    """빗방울 이미터 — 좁은 원뿔, 빠른 하강."""
    return ParticleEmitter.preset("rain", **kwargs)
